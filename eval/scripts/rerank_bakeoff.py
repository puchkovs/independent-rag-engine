"""Compare retrieval with and without the cross-encoder, with the product pipeline.

The corpus is ingested with the real ``rag ingest``; every question is searched in dense and
hybrid mode with reranking off and on (the same pool, the same questions), and the scores are
compared pairwise. The report also gives the latency of the rerank stage and the peak memory of the
process. As with the other evaluations, unreviewed labels only give an exploratory result, and a
saturated set cannot show a gain.

    uv run python eval/scripts/rerank_bakeoff.py --embed-dir <e5 model directory> \\
        --rerank-dir <reranker model directory> --include-unreviewed
"""

from __future__ import annotations

import argparse
import asyncio
import json
import resource
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import resource_guard
from retrieval_eval import ROOT, percentile, write_config

from rag_engine.cli.main import main as rag
from rag_engine.cli.search import load_details
from rag_engine.container import DefaultContainer
from rag_engine.domain import RerankMode, RetrievalMode, RetrievalQuery
from rag_engine.embedding.onnx import model_directory_digest
from rag_engine.evaluation.dataset import (
    Question,
    accepted_questions,
    load_dataset,
    validate_dataset,
)
from rag_engine.evaluation.protocol import TestSplitGuard
from rag_engine.evaluation.runner import QuestionScore, RankedChunk, compare, score_question

METRICS = ("hit@1", "mrr@10", "ndcg@10", "evidence@5")
NAME = "BAAI/bge-reranker-v2-m3-int8"
PEAK_GIB = 2.5  # peak resident memory measured with both models loaded (ADR 0014)


def run(
    container: DefaultContainer,
    config: Path,
    db: Path,
    questions: list[Question],
    mode: RetrievalMode,
    rerank: RerankMode,
) -> tuple[list[QuestionScore], list[float], list[float], list[str]]:
    scores: list[QuestionScore] = []
    totals: list[float] = []
    stage: list[float] = []
    notes: list[str] = []
    with container.search(config, db) as searcher:
        for question in questions:
            request = RetrievalQuery(
                request_id=searcher.ids.request_id(),
                text=question.question,
                mode=mode,
                top_k=10,
                candidate_k=40,
                rerank=rerank,
            )
            began = time.perf_counter()
            outcome = asyncio.run(searcher.retrieval.search(request))
            totals.append((time.perf_counter() - began) * 1000)
            if "rerank" in outcome.diagnostics.timings_ms:
                stage.append(outcome.diagnostics.timings_ms["rerank"])
            notes.extend(n for n in outcome.result.fallbacks if n.startswith("rerank_skipped"))
            ranked = [
                RankedChunk(detail.path, detail.text)
                for detail in load_details(searcher.store, outcome.result)
            ]
            scores.append(score_question(question, ranked))
    return scores, totals, stage, notes


def latency(values: list[float]) -> dict[str, float]:
    return {"p50": statistics.median(values), "p95": percentile(values, 0.95)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--embed-dir", type=Path, required=True)
    parser.add_argument("--rerank-dir", type=Path, required=True)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "eval/datasets/retrieval_mini_v1.json"
    )
    parser.add_argument("--include-unreviewed", action="store_true")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--final", action="store_true", help="read the held-out test split")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    corpus_dir = ROOT / dataset.corpus
    corpus = {p.name: p.read_text(encoding="utf-8") for p in corpus_dir.glob("*.md")}
    if not validate_dataset(dataset, corpus).ok:
        sys.exit("dataset invalid")
    pool = (
        [q for q in dataset.questions if q.review.status != "rejected"]
        if args.include_unreviewed
        else accepted_questions(dataset)
    )
    questions = [q for q in pool if q.answerable and q.split == args.split]
    if (
        args.split == "test"
    ):  # the held-out split is read only on request, and every read is counted
        TestSplitGuard(ROOT / "eval_runs" / "test_access.json").read(
            dataset.identifier, final=args.final
        )
    if not questions:
        sys.exit("no accepted answerable questions; review the dataset or use --include-unreviewed")
    seed = int(dataset.manifest_hash[:8], 16)
    resource_guard.require(PEAK_GIB, what="the embedding model and the cross-encoder")
    resource_guard.watchdog()
    rerank_dir = args.rerank_dir.resolve()
    fingerprint = model_directory_digest(rerank_dir)
    section = (
        'mode = "hybrid"\n[rerank]\nenabled = true\n'
        f'model = "{NAME}"\nmodel_dir = "{rerank_dir}"\nrevision = "{fingerprint}"\n'
        "pool_size = 30\ntimeout_s = 120.0\nthreads = 4\n"
    )
    container = DefaultContainer()
    report: dict[str, Any] = {"modes": {}, "comparisons": {}}
    with tempfile.TemporaryDirectory(prefix="rag-rerank-") as folder:
        work = Path(folder)
        config, db = work / "rag.toml", work / "rag.db"
        write_config(config, args.embed_dir.resolve(), section)
        prefix = ["--config", str(config), "--db", str(db)]
        for step in (["source", "add", "corpus", str(corpus_dir)], ["ingest", "corpus", "--json"]):
            if rag([*prefix, *step], container=container) != 0:
                sys.exit(f"rag {step[0]} failed")
        for mode in (RetrievalMode.DENSE, RetrievalMode.HYBRID):
            off, off_ms, _, _ = run(container, config, db, questions, mode, RerankMode.OFF)
            on, on_ms, stage_ms, notes = run(container, config, db, questions, mode, RerankMode.ON)
            report["modes"][mode.value] = {
                "questions": len(questions),
                "off_mean": {m: statistics.mean(s.metrics[m] for s in off) for m in METRICS},
                "on_mean": {m: statistics.mean(s.metrics[m] for s in on) for m in METRICS},
                "search_ms_off": latency(off_ms),
                "search_ms_on": latency(on_ms),
                "rerank_stage_ms": latency(stage_ms) if stage_ms else None,
                "skipped": sorted(set(notes)),
            }
            report["comparisons"][mode.value] = {}
            for metric in METRICS:
                interval = compare(on, off, metric, seed=seed)
                report["comparisons"][mode.value][metric] = {
                    "mean": interval.mean,
                    "low": interval.low,
                    "high": interval.high,
                    "excludes_zero": interval.excludes_zero,
                }
    report["peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    report["exploratory"] = args.include_unreviewed
    report["dataset"] = dataset.identifier
    report["split"] = args.split
    report["model"] = {"name": NAME, "fingerprint": fingerprint}
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
