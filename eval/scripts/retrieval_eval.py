"""Compare dense, lexical and hybrid retrieval on the mini corpus with the product pipeline.

The corpus is ingested with the real ``rag ingest`` and every question runs through the same
search service as ``rag search``; nothing here re-implements retrieval. Metrics count only
accepted or edited questions. ``--include-unreviewed`` lets an exploratory run use drafts; its
report says so, and it cannot decide a default.

    uv run python eval/scripts/retrieval_eval.py --model-dir data/models/multilingual-e5-small/<rev>
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import platform
import resource
import statistics
import sys
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import resource_guard

from rag_engine.cli.main import main as rag
from rag_engine.cli.search import load_details
from rag_engine.container import DefaultContainer
from rag_engine.domain import RetrievalMode, RetrievalQuery
from rag_engine.embedding.onnx import model_directory_digest
from rag_engine.evaluation.dataset import (
    Question,
    accepted_questions,
    load_dataset,
    validate_dataset,
)
from rag_engine.evaluation.protocol import TestSplitGuard
from rag_engine.evaluation.runner import (
    QuestionScore,
    RankedChunk,
    compare,
    score_question,
    summarize,
)

ROOT = Path(__file__).resolve().parents[2]
MODES = (RetrievalMode.DENSE, RetrievalMode.LEXICAL, RetrievalMode.HYBRID)
SHOWN = ("hit@1", "hit@5", "recall@5", "mrr@10", "ndcg@10", "evidence@5", "all_gold@5")
COMPARED = ("hit@5", "mrr@10", "ndcg@10", "evidence@5")


def write_config(path: Path, model_dir: Path, retrieval: str) -> None:
    path.write_text(
        "[parsing]\nisolate = []\n"
        '[embedding]\nenabled = true\nprovider = "onnx"\n'
        'model = "intfloat/multilingual-e5-small"\n'
        f'revision = "{model_directory_digest(model_dir)}"\n'
        f'dimension = 384\nmax_input_tokens = 512\nmodel_dir = "{model_dir}"\n'
        'query_prefix = "query: "\ndocument_prefix = "passage: "\n'
        f"[retrieval]\n{retrieval}\n",
        encoding="utf-8",
    )


def corpus_manifest(corpus: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(corpus.glob("*.md"))}


def run_mode(
    container: DefaultContainer,
    config: Path,
    db: Path,
    questions: list[Question],
    mode: RetrievalMode,
) -> tuple[list[QuestionScore], dict[str, list[float]], int, str | None]:
    scores: list[QuestionScore] = []
    timings: dict[str, list[float]] = defaultdict(list)
    generation, model = 0, None
    with container.search(config, db) as searcher:
        for question in questions:
            request = RetrievalQuery(
                request_id=searcher.ids.request_id(),
                text=question.question,
                mode=mode,
                top_k=10,
                candidate_k=40,
            )
            outcome = asyncio.run(searcher.retrieval.search(request))
            generation = outcome.result.index_generation
            model = (
                None
                if outcome.result.embedding_model_id is None
                else str(outcome.result.embedding_model_id)
            )
            for stage, value in outcome.diagnostics.timings_ms.items():
                timings[stage].append(value)
            ranked = [
                RankedChunk(detail.path, detail.text)
                for detail in load_details(searcher.store, outcome.result)
            ]
            scores.append(score_question(question, ranked))
    return scores, timings, generation, model


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.5))]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "eval/datasets/retrieval_mini_v1.json"
    )
    parser.add_argument("--split", choices=("dev", "test", "all"), default="dev")
    parser.add_argument("--include-unreviewed", action="store_true")
    parser.add_argument("--final", action="store_true", help="read the held-out test split")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    corpus_dir = ROOT / dataset.corpus
    corpus = {p.name: p.read_text(encoding="utf-8") for p in corpus_dir.glob("*.md")}
    validation = validate_dataset(dataset, corpus)
    if not validation.ok:
        sys.exit("dataset invalid:\n" + "\n".join(validation.errors))
    pool = (
        [q for q in dataset.questions if q.review.status != "rejected"]
        if args.include_unreviewed
        else accepted_questions(dataset)
    )
    questions = [q for q in pool if q.answerable and args.split in {"all", q.split}]
    if not questions:
        sys.exit("no accepted answerable questions; review the dataset or use --include-unreviewed")
    seed = args.seed if args.seed is not None else int(dataset.manifest_hash[:8], 16)
    test_reads: int | None = None
    if args.split in {"test", "all"}:  # the held-out split is read only on request, and counted
        test_reads = TestSplitGuard(ROOT / "eval_runs" / "test_access.json").read(
            dataset.identifier, final=args.final
        )
    resource_guard.require(1.2, what="the E5 embedding model")
    resource_guard.watchdog()

    container = DefaultContainer()
    results: dict[str, Any] = {}
    all_scores: dict[str, list[QuestionScore]] = {}
    with tempfile.TemporaryDirectory(prefix="rag-eval-") as folder:
        work = Path(folder)
        config, db = work / "rag.toml", work / "rag.db"
        write_config(config, args.model_dir.resolve(), 'mode = "hybrid"')
        prefix = ["--config", str(config), "--db", str(db)]
        for step in (["source", "add", "corpus", str(corpus_dir)], ["ingest", "corpus", "--json"]):
            if rag([*prefix, *step], container=container) != 0:
                sys.exit(f"rag {step[0]} failed")
        for mode in MODES:
            scores, timings, generation, model = run_mode(container, config, db, questions, mode)
            all_scores[mode.value] = scores
            results[mode.value] = {
                "summary": {
                    group: {m: vars_of(s) for m, s in metrics.items()}
                    for group, metrics in summarize(scores, seed=seed).items()
                },
                "latency_ms": {
                    stage: {"p50": statistics.median(values), "p95": percentile(values, 0.95)}
                    for stage, values in timings.items()
                },
                "per_question": {s.question_id: dict(s.metrics) for s in scores},
            }
    comparisons = {
        f"{a} - {b}": {
            metric: vars_of_interval(compare(all_scores[a], all_scores[b], metric, seed=seed))
            for metric in COMPARED
        }
        for a, b in (("hybrid", "dense"), ("hybrid", "lexical"), ("dense", "lexical"))
    }
    reviewed = len(accepted_questions(dataset))
    report = {
        "manifest": {
            "dataset": dataset.identifier,
            "dataset_sha256": dataset.manifest_hash,
            "corpus_sha256": corpus_manifest(corpus_dir),
            "split": args.split,
            "questions": len(questions),
            "reviewed_questions_in_dataset": reviewed,
            "exploratory": args.include_unreviewed and reviewed < len(questions),
            "seed": seed,
            "top_k": 10,
            "candidate_k": 40,
            "embedding_model": model,
            "index_generation": generation,
            "python": platform.python_version(),
            "test_reads": test_reads,
            "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
            "created": datetime.now(UTC).isoformat(timespec="seconds"),
        },
        "modes": results,
        "comparisons": comparisons,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(render(report))


def vars_of(summary: Any) -> dict[str, float | int | bool]:
    return {
        "n": summary.n,
        "mean": summary.mean,
        "low": summary.low,
        "high": summary.high,
        "saturated": summary.saturated,
        "anecdotal": summary.anecdotal,
    }


def vars_of_interval(interval: Any) -> dict[str, float | bool]:
    return {
        "mean": interval.mean,
        "low": interval.low,
        "high": interval.high,
        "excludes_zero": interval.excludes_zero,
    }


def render(report: dict[str, Any]) -> str:
    manifest = report["manifest"]
    lines = [
        f"# Retrieval evaluation: {manifest['dataset']} "
        f"({manifest['split']}, {manifest['questions']} questions)",
        "",
        f"dataset sha256 `{manifest['dataset_sha256'][:16]}`; "
        f"model `{manifest['embedding_model']}`; "
        f"seed {manifest['seed']}; index generation {manifest['index_generation']}",
    ]
    if manifest["exploratory"]:
        lines += [
            "",
            "**EXPLORATORY: labels are unreviewed drafts. This run cannot decide a default.**",
        ]
    for group in (
        "all",
        "language:en",
        "language:ru",
        "type:keyword",
        "type:paraphrase",
        "type:multi_doc",
    ):
        lines += ["", f"## {group}", "", "| mode | n | " + " | ".join(SHOWN) + " |"]
        lines.append("|---|---:|" + "---:|" * len(SHOWN))
        for mode, data in report["modes"].items():
            cells = data["summary"].get(group)
            if cells is None:
                continue
            flags = [f"{m}: saturated" for m in SHOWN if cells[m]["saturated"]]
            row = " | ".join(
                f"{cells[m]['mean']:.3f} [{cells[m]['low']:.2f}, {cells[m]['high']:.2f}]"
                for m in SHOWN
            )
            lines.append(
                f"| {mode} | {cells[SHOWN[0]]['n']} | {row} |"
                + (f" <!-- {', '.join(flags)} -->" if flags else "")
            )
    lines += ["", "## Paired differences (first minus second, 95 % bootstrap interval)", ""]
    lines.append("| pair | " + " | ".join(COMPARED) + " |")
    lines.append("|---|" + "---:|" * len(COMPARED))
    for pair, metrics in report["comparisons"].items():
        row = " | ".join(
            f"{metrics[m]['mean']:+.3f} [{metrics[m]['low']:+.3f}, {metrics[m]['high']:+.3f}]"
            + (" *" if metrics[m]["excludes_zero"] else "")
            for m in COMPARED
        )
        lines.append(f"| {pair} | {row} |")
    lines += ["", "`*` the interval excludes zero.", "", "## Latency per stage (ms, p50 / p95)", ""]
    lines.insert(2, f"peak resident memory of the process: {manifest['peak_rss_mib']} MiB")
    for mode, data in report["modes"].items():
        stages = ", ".join(
            f"{s} {v['p50']:.1f}/{v['p95']:.1f}" for s, v in data["latency_ms"].items()
        )
        lines.append(f"- {mode}: {stages}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
