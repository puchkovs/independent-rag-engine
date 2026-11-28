# ruff: noqa: E501
"""A preliminary automatic audit of evaluation questions (nothing is changed, nothing is reviewed).

    uv run python eval/scripts/audit_questions.py                      # lexical layer only
    uv run python eval/scripts/audit_questions.py --embed-dir <e5 dir> # plus the semantic layer

The report (``eval_runs/question_audit.json``) sorts every question into correct, doubtful or
incorrect. ``review_kit.py build --audit`` puts it into the review page. The semantic layer loads the
embedding model, so it refuses to start unless the machine has the memory for it, and a watchdog
stops it if free memory falls too low while it runs.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
from collections.abc import Sequence
from pathlib import Path

import resource_guard
from retrieval_eval import ROOT

from rag_engine.config import load_settings
from rag_engine.container import build_embedding
from rag_engine.embedding.onnx import model_directory_digest
from rag_engine.evaluation.question_audit import audit_source, summarize
from rag_engine.evaluation.review_kit import load_source
from rag_engine.system import SystemClock

DEFAULT = ("retrieval_hard_v2", "retrieval_mini_v2")
MODEL_GIB = 1.2  # resident memory measured for the E5 model


class E5Encoder:
    """The pinned local E5 model through the product's embedding adapter (prefixes applied here)."""

    def __init__(self, model_dir: Path) -> None:
        config = Path(model_dir.parent / "audit.toml")
        del config
        digest = model_directory_digest(model_dir)
        text = (
            '[embedding]\nenabled = true\nprovider = "onnx"\nmodel = "intfloat/multilingual-e5-small"\n'
            f'revision = "{digest}"\ndimension = 384\nmax_input_tokens = 512\nmodel_dir = "{model_dir}"\n'
            'query_prefix = "query: "\ndocument_prefix = "passage: "\n'
        )
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rag.toml"
            path.write_text(text, encoding="utf-8")
            settings = load_settings(path)
        self._built = build_embedding(settings.embedding, SystemClock())
        self._provider = self._built.provider

    def _embed(self, texts: Sequence[str], prefix: str) -> list[list[float]]:
        out: list[list[float]] = []
        for start in range(0, len(texts), 8):
            batch = [prefix + t for t in texts[start : start + 8]]
            out.extend(asyncio.run(self._provider.embed_documents(batch)).tolist())
        return out

    def queries(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(texts, self._built.model.query_prefix)

    def passages(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed(texts, self._built.model.document_prefix)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", action="append", type=Path)
    parser.add_argument("--embed-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=ROOT / "eval_runs/question_audit.json")
    args = parser.parse_args()
    paths = args.dataset or [ROOT / "eval/datasets" / f"{n}.json" for n in DEFAULT]
    encoder: E5Encoder | None = None
    if args.embed_dir is not None:
        resource_guard.require(MODEL_GIB, what="the E5 embedding model")
        resource_guard.watchdog()
        encoder = E5Encoder(args.embed_dir.resolve())
    report: dict[str, object] = {
        "semantic_layer": encoder is not None,
        "datasets": {},
        "audits": [],
    }
    audits = []
    questions = {}
    for path in paths:
        source = load_source(path, ROOT)
        questions.update({f"{source.name}:{q.id}": q for q in source.dataset.questions})
        results = audit_source(source, encoder)
        audits.extend(results)
        report["datasets"][source.name] = summarize(results)  # type: ignore[index]
    report["summary"] = summarize(audits)
    report["audits"] = [a.as_dict() for a in audits]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    with args.output.with_suffix(".csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["key", "verdict", "type", "split", "question", "expected_answer", "findings", "hint"]
        )
        for audit in audits:
            q = questions[audit.key]
            findings = " ".join(f.id for f in audit.flags if f.severity != "info")
            writer.writerow(
                [audit.key, audit.verdict.value, q.type, q.split, q.question,
                 q.reference_answer or "", findings, audit.hint]
            )  # fmt: skip
    print(json.dumps({k: v for k, v in report.items() if k != "audits"}, indent=2))


if __name__ == "__main__":
    main()
