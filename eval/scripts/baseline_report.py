# ruff: noqa: E501  (Markdown table rows are long lines)
"""Turn the baseline runs of ``eval_runs/baseline_v2`` into the tables of ``docs/BASELINE_V2.md``.

The runs themselves are made by ``retrieval_eval.py`` (dense, lexical, hybrid) and
``rerank_bakeoff.py`` (reranking) and are not committed; this script only reads them and prints
Markdown, so every number in the document can be regenerated from a run. It also lines version 1 of
a dataset up with version 2, question by question, and checks that the whole movement of a mean is
explained by the questions whose labels were changed.

    uv run python eval/scripts/baseline_report.py > /tmp/tables.md
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "eval_runs" / "baseline_v2"
SHOWN = ("hit@1", "hit@5", "recall@5", "mrr@10", "ndcg@10", "evidence@5")
EFFECT = ("hit@1", "mrr@10", "ndcg@10", "evidence@5")
MODES = ("dense", "hybrid", "lexical")
STAGES = ("query", "dense", "lexical", "fuse")


def load(name: str, split: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((RUNS / f"{name}_{split}.json").read_text(encoding="utf-8"))
    return data


def metrics_table(report: Mapping[str, Any], group: str = "all") -> list[str]:
    lines = ["| mode | n | " + " | ".join(SHOWN) + " |", "|---|---:|" + "---:|" * len(SHOWN)]
    for mode in MODES:
        cells = report["modes"][mode]["summary"].get(group)
        if cells is None:
            continue
        row = " | ".join(
            f"{cells[m]['mean']:.3f} [{cells[m]['low']:.2f}, {cells[m]['high']:.2f}]" for m in SHOWN
        )
        lines.append(f"| {mode} | {cells[SHOWN[0]]['n']} | {row} |")
    return lines


def paired_table(report: Mapping[str, Any]) -> list[str]:
    metrics = ("hit@5", "mrr@10", "ndcg@10", "evidence@5")
    lines = ["| pair | " + " | ".join(metrics) + " |", "|---|" + "---:|" * len(metrics)]
    for pair, cells in report["comparisons"].items():
        row = " | ".join(
            f"{cells[m]['mean']:+.3f} [{cells[m]['low']:+.2f}, {cells[m]['high']:+.2f}]"
            + (" \\*" if cells[m]["excludes_zero"] else "")
            for m in metrics
        )
        lines.append(f"| {pair} | {row} |")
    return lines


def latency_table(report: Mapping[str, Any]) -> list[str]:
    lines = [
        "| mode | " + " | ".join(f"{s} (ms)" for s in STAGES) + " |",
        "|---|" + "---:|" * len(STAGES),
    ]
    for mode in MODES:
        stages = report["modes"][mode]["latency_ms"]
        cells = [
            f"{stages[s]['p50']:.1f} / {stages[s]['p95']:.1f}" if s in stages else "-"
            for s in STAGES
        ]
        lines.append(f"| {mode} | " + " | ".join(cells) + " |")
    return lines


def version_effect(
    old: Mapping[str, Any], new: Mapping[str, Any], changed: Sequence[str], mode: str
) -> dict[str, Any]:
    """Per question and in total: how the metrics moved from version 1 to version 2.

    Returns the movement of each mean, the part of it that the questions in ``changed`` account
    for, and the per-question deltas that are not zero. ``unexplained`` is what is left over (it
    should be zero: an unchanged question is scored identically in both versions).
    """
    a, b = old["modes"][mode]["per_question"], new["modes"][mode]["per_question"]
    common = sorted(set(a) & set(b))
    out: dict[str, Any] = {"n": len(common), "metrics": {}, "questions": {}}
    metrics: dict[str, Any] = out["metrics"]
    for metric in EFFECT:
        deltas = {i: b[i][metric] - a[i][metric] for i in common}
        total = sum(deltas.values()) / len(common)
        explained = sum(d for i, d in deltas.items() if i in changed) / len(common)
        metrics[metric] = {
            "old": sum(a[i][metric] for i in common) / len(common),
            "new": sum(b[i][metric] for i in common) / len(common),
            "delta": total,
            "from_changed": explained,
            "unexplained": total - explained,
        }
        for i, d in deltas.items():
            if abs(d) > 1e-9:
                out["questions"].setdefault(i, {})[metric] = d
    return out


def effect_table(effects: Mapping[str, Mapping[str, Any]]) -> list[str]:
    lines = ["| mode | " + " | ".join(f"{m}: v1 → v2 (Δ)" for m in EFFECT) + " |",
             "|---|" + "---:|" * len(EFFECT)]  # fmt: skip
    for mode, effect in effects.items():
        cells = [
            f"{effect['metrics'][m]['old']:.3f} → {effect['metrics'][m]['new']:.3f} "
            f"({effect['metrics'][m]['delta']:+.3f})"
            for m in EFFECT
        ]
        lines.append(f"| {mode} | " + " | ".join(cells) + " |")
    return lines


def question_table(
    effects: Mapping[str, Mapping[str, Any]], reasons: Mapping[str, str]
) -> list[str]:
    ids = sorted({i for e in effects.values() for i in e["questions"]})
    lines = ["| question | change | " + " | ".join(MODES) + " |", "|---|---|" + "---|" * len(MODES)]
    for identifier in ids:
        cells = []
        for mode in MODES:
            moved = effects[mode]["questions"].get(identifier, {})
            cells.append(
                ", ".join(f"{m.split('@')[0]} {d:+.2f}" for m, d in moved.items()) or "no change"
            )
        lines.append(
            f"| `{identifier}` | {reasons.get(identifier, 'unchanged: tie-breaking between equal scores')} | "
            + " | ".join(cells)
            + " |"
        )
    return lines


def rerank_table(path: Path) -> list[str]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = ["| mode | n | metric | reranking off | reranking on | difference [95 % CI] |",
             "|---|---:|---|---:|---:|---|"]  # fmt: skip
    for mode, block in data["modes"].items():
        for metric in ("hit@1", "mrr@10", "ndcg@10", "evidence@5"):
            c = data["comparisons"][mode][metric]
            lines.append(
                f"| {mode} | {block['questions']} | {metric} | {block['off_mean'][metric]:.3f} | "
                f"{block['on_mean'][metric]:.3f} | {c['mean']:+.3f} [{c['low']:+.3f}, {c['high']:+.3f}]"
                + (" \\*" if c["excludes_zero"] else "")
                + " |"
            )
    lines.append("")
    lines.append(
        "| mode | search p50 / p95 off (ms) | search p50 / p95 on (ms) | rerank stage p50 / p95 (ms) |"
    )
    lines.append("|---|---:|---:|---:|")
    for mode, block in data["modes"].items():
        stage = block["rerank_stage_ms"]
        lines.append(
            f"| {mode} | {block['search_ms_off']['p50']:.0f} / {block['search_ms_off']['p95']:.0f} | "
            f"{block['search_ms_on']['p50']:.0f} / {block['search_ms_on']['p95']:.0f} | "
            + (f"{stage['p50']:.0f} / {stage['p95']:.0f}" if stage else "-")
            + " |"
        )
    lines.append("")
    lines.append(
        f"Peak resident memory of the process with both models loaded: {data['peak_rss_mib']:.0f} MiB."
    )
    return lines


def main() -> None:
    changes = json.loads((ROOT / "eval/datasets/CHANGES_v2.json").read_text(encoding="utf-8"))
    out: list[str] = []
    for name, label in (("retrieval_hard", "hard"), ("retrieval_mini", "mini")):
        for split in ("dev", "test"):
            new = load(f"{name}_v2", split)
            manifest = new["manifest"]
            out.extend([
                f"### {label} v2, {split}: {manifest['questions']} answerable questions", "",
                f"Peak resident memory of the run (ingestion and all three modes): "
                f"{manifest['peak_rss_mib']:.0f} MiB.", "", *metrics_table(new), "",
            ])  # fmt: skip
            if label == "hard":
                for group in ("language:en", "language:ru"):
                    out.extend([group, "", *metrics_table(new, group), ""])
            out.extend(["Paired differences (first minus second):", "", *paired_table(new), ""])
            out.extend(["Latency per stage, p50 / p95:", "", *latency_table(new), ""])
    key = {"retrieval_hard": "retrieval-hard", "retrieval_mini": "retrieval-mini"}
    for name, label in (("retrieval_hard", "hard"), ("retrieval_mini", "mini")):
        block = changes["datasets"][key[name]]["changes"]
        changed = [c["id"] for c in block if c["kind"] != "absence"]
        reasons = {c["id"]: c["kind"] for c in block}
        for split in ("dev", "test"):
            old, new = load(f"{name}_v1", split), load(f"{name}_v2", split)
            effects = {m: version_effect(old, new, changed, m) for m in MODES}
            left = max(
                abs(e["metrics"][m]["unexplained"]) for e in effects.values() for m in EFFECT
            )
            out.extend([
                f"### {label}: version 1 to version 2, {split}", "", *effect_table(effects), "",
                *question_table(effects, reasons), "",
                f"Movement not explained by a changed question: at most {left:.4f}.", "",
            ])  # fmt: skip
    reranking = (
        ("hard v2, dev (this baseline)", RUNS / "rerank_retrieval_hard_v2_dev.json"),
        ("mini v2, dev (this baseline)", RUNS / "rerank_retrieval_mini_v2_dev.json"),
        (
            "hard v1, dev (earlier measurement, version 1 labels)",
            ROOT / "eval_runs" / "rerank_hard_dev.json",
        ),
        (
            "mini v1, dev (earlier measurement, version 1 labels)",
            ROOT / "eval_runs" / "rerank_bakeoff.json",
        ),
    )
    for title, path in reranking:
        table = rerank_table(path)
        out.extend(
            [
                f"### reranking, {title}",
                "",
                *(table or ["not run: the resource gate refused it"]),
                "",
            ]
        )
    print("\n".join(out))


if __name__ == "__main__":
    main()
