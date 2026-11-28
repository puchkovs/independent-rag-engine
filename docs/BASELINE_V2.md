# Retrieval baseline on dataset version 2

Measured on 2026-11-28 on the reference machine (4 vCPU, 7.8 GiB, Linux, Python 3.12) with the
pinned `multilingual-e5-small` ONNX model and the **existing** retrieval configuration: `top_k` 10,
`candidate_k` 40, default fusion and thresholds, nothing tuned. The datasets are `retrieval-hard@v2`
(141 questions) and `retrieval-mini@v2` (44 questions); all labels are still **unreviewed**, so
every number here is exploratory and none can decide a default. The held-out gate set
(`gate-heldout@v2`) was not used. The tables are produced by
[`eval/scripts/baseline_report.py`](../eval/scripts/baseline_report.py) from runs of
[`retrieval_eval.py`](../eval/scripts/retrieval_eval.py) and
[`rerank_bakeoff.py`](../eval/scripts/rerank_bakeoff.py); the runs themselves live in `eval_runs/`
(outside Git).

## Summary

- **Dense retrieval is the best default on both sets.** On the hard set it reaches hit@5 0.925 (dev)
  and 0.948 (test), nDCG@10 0.826 and 0.859. **Hybrid is worse than dense** (hit@5 0.642 and 0.810; the
  paired difference excludes zero on both splits) and lexical alone is worse still, because half of the
  questions are asked in the other language than their document. This is the conclusion of
  [ADR 0018](adr/0018-hard-set-gate-and-reranker.md) again, now on corrected labels.
- **The mini set cannot separate dense from hybrid**: both score 1.000 on every metric (saturated).
- **Reranking is not re-measured on version 2.** The resource gate refused it: both models together
  peak at about 2.5 GiB and the rule is "peak plus 1 GiB of headroom" (3.5 GiB available), while the
  machine had about 2.7 GiB. The earlier measurement on version 1 is reproduced below (+0.16 nDCG@10 on
  dense, +0.37 on hybrid, hard dev) and is clearly marked as version 1.
- **The label corrections moved the numbers by at most a few hundredths**, and every bit of the
  movement is explained by the questions that were corrected (see below). Retrieval itself did not change.

## What was measured, and how

| | |
|---|---|
| Modes | dense (exact cosine), lexical (BM25), hybrid (RRF) |
| Metrics | hit@1, hit@5, recall@5, MRR@10, nDCG@10, evidence@5 (share of gold quotes found in the top 5); 95 % bootstrap intervals; paired differences between modes |
| Splits | `dev` for every comparison; `test` read once per dataset version through the counted guard (`--final`) |
| Latency | per-stage p50 / p95 over the questions of the run (stages as the search service reports them) |
| Memory | peak resident set of the process that ingests the corpus and runs all three modes |
| Counted test reads | `retrieval-hard@v1`: 2 (one earlier research read, one here), `retrieval-hard@v2`: 1, `retrieval-mini@v1`: 1, `retrieval-mini@v2`: 1 |

Only answerable questions are scored for retrieval (53 + 58 on the hard set, 22 + 14 on the mini
set); the unanswerable ones belong to the gate, not to retrieval.

## Results

#### hard v2, dev: 53 answerable questions

Peak resident memory of the run (ingestion and all three modes): 1531 MiB.

| mode | n | hit@1 | hit@5 | recall@5 | mrr@10 | ndcg@10 | evidence@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 53 | 0.698 [0.57, 0.81] | 0.925 [0.85, 0.98] | 0.915 [0.84, 0.98] | 0.788 [0.69, 0.87] | 0.826 [0.74, 0.90] | 0.915 [0.84, 0.98] |
| hybrid | 53 | 0.528 [0.40, 0.66] | 0.642 [0.51, 0.77] | 0.632 [0.50, 0.75] | 0.581 [0.46, 0.71] | 0.625 [0.51, 0.74] | 0.632 [0.50, 0.75] |
| lexical | 53 | 0.528 [0.40, 0.66] | 0.528 [0.40, 0.66] | 0.519 [0.39, 0.65] | 0.528 [0.40, 0.66] | 0.521 [0.39, 0.66] | 0.519 [0.39, 0.65] |

language:en

| mode | n | hit@1 | hit@5 | recall@5 | mrr@10 | ndcg@10 | evidence@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 26 | 0.692 [0.54, 0.85] | 0.885 [0.77, 1.00] | 0.885 [0.77, 1.00] | 0.770 [0.64, 0.90] | 0.807 [0.69, 0.92] | 0.885 [0.77, 1.00] |
| hybrid | 26 | 0.538 [0.35, 0.73] | 0.577 [0.38, 0.77] | 0.577 [0.38, 0.77] | 0.564 [0.39, 0.75] | 0.593 [0.42, 0.77] | 0.577 [0.38, 0.77] |
| lexical | 26 | 0.538 [0.35, 0.73] | 0.538 [0.35, 0.73] | 0.538 [0.35, 0.73] | 0.538 [0.35, 0.73] | 0.538 [0.35, 0.73] | 0.538 [0.35, 0.73] |

language:ru

| mode | n | hit@1 | hit@5 | recall@5 | mrr@10 | ndcg@10 | evidence@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 27 | 0.704 [0.52, 0.85] | 0.963 [0.89, 1.00] | 0.944 [0.85, 1.00] | 0.805 [0.68, 0.91] | 0.844 [0.75, 0.93] | 0.944 [0.85, 1.00] |
| hybrid | 27 | 0.519 [0.33, 0.70] | 0.704 [0.52, 0.89] | 0.685 [0.52, 0.85] | 0.597 [0.43, 0.75] | 0.657 [0.52, 0.79] | 0.685 [0.52, 0.85] |
| lexical | 27 | 0.519 [0.33, 0.70] | 0.519 [0.33, 0.70] | 0.500 [0.31, 0.69] | 0.519 [0.33, 0.70] | 0.504 [0.32, 0.69] | 0.500 [0.31, 0.69] |

Paired differences (first minus second):

| pair | hit@5 | mrr@10 | ndcg@10 | evidence@5 |
|---|---:|---:|---:|---:|
| dense - lexical | +0.396 [+0.26, +0.53] \* | +0.259 [+0.15, +0.37] \* | +0.305 [+0.20, +0.41] \* | +0.396 [+0.26, +0.53] \* |
| hybrid - dense | -0.283 [-0.42, -0.17] \* | -0.207 [-0.31, -0.11] \* | -0.200 [-0.29, -0.11] \* | -0.283 [-0.42, -0.17] \* |
| hybrid - lexical | +0.113 [+0.04, +0.21] \* | +0.053 [+0.03, +0.08] \* | +0.104 [+0.06, +0.15] \* | +0.113 [+0.04, +0.21] \* |

Latency per stage, p50 / p95:

| mode | query (ms) | dense (ms) | lexical (ms) | fuse (ms) |
|---|---:|---:|---:|---:|
| dense | 0.1 / 0.1 | 15.1 / 22.1 | 0.0 / 0.0 | 0.1 / 0.1 |
| hybrid | 0.1 / 0.1 | 18.6 / 25.4 | 2.0 / 4.2 | 0.1 / 0.4 |
| lexical | 0.0 / 0.1 | 0.0 / 0.0 | 1.2 / 1.8 | 0.0 / 0.0 |

#### hard v2, test: 58 answerable questions

Peak resident memory of the run (ingestion and all three modes): 1516 MiB.

| mode | n | hit@1 | hit@5 | recall@5 | mrr@10 | ndcg@10 | evidence@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 58 | 0.724 [0.60, 0.83] | 0.948 [0.88, 1.00] | 0.948 [0.88, 1.00] | 0.822 [0.74, 0.90] | 0.859 [0.79, 0.92] | 0.948 [0.88, 1.00] |
| hybrid | 58 | 0.586 [0.47, 0.71] | 0.810 [0.71, 0.90] | 0.810 [0.71, 0.90] | 0.678 [0.57, 0.78] | 0.730 [0.64, 0.82] | 0.810 [0.71, 0.90] |
| lexical | 58 | 0.517 [0.38, 0.64] | 0.586 [0.45, 0.71] | 0.586 [0.45, 0.71] | 0.551 [0.43, 0.67] | 0.568 [0.44, 0.69] | 0.586 [0.45, 0.71] |

language:en

| mode | n | hit@1 | hit@5 | recall@5 | mrr@10 | ndcg@10 | evidence@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 29 | 0.759 [0.59, 0.90] | 0.966 [0.90, 1.00] | 0.966 [0.90, 1.00] | 0.841 [0.73, 0.94] | 0.879 [0.79, 0.95] | 0.966 [0.90, 1.00] |
| hybrid | 29 | 0.552 [0.38, 0.72] | 0.724 [0.55, 0.86] | 0.724 [0.55, 0.86] | 0.637 [0.49, 0.79] | 0.690 [0.55, 0.82] | 0.724 [0.55, 0.86] |
| lexical | 29 | 0.552 [0.38, 0.72] | 0.586 [0.41, 0.76] | 0.586 [0.41, 0.76] | 0.569 [0.40, 0.74] | 0.573 [0.40, 0.75] | 0.586 [0.41, 0.76] |

language:ru

| mode | n | hit@1 | hit@5 | recall@5 | mrr@10 | ndcg@10 | evidence@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 29 | 0.690 [0.52, 0.86] | 0.931 [0.83, 1.00] | 0.931 [0.83, 1.00] | 0.802 [0.68, 0.91] | 0.839 [0.74, 0.93] | 0.931 [0.83, 1.00] |
| hybrid | 29 | 0.621 [0.45, 0.79] | 0.897 [0.76, 1.00] | 0.897 [0.76, 1.00] | 0.718 [0.58, 0.85] | 0.770 [0.65, 0.88] | 0.897 [0.76, 1.00] |
| lexical | 29 | 0.483 [0.31, 0.69] | 0.586 [0.41, 0.76] | 0.586 [0.41, 0.76] | 0.533 [0.37, 0.71] | 0.562 [0.40, 0.73] | 0.586 [0.41, 0.76] |

Paired differences (first minus second):

| pair | hit@5 | mrr@10 | ndcg@10 | evidence@5 |
|---|---:|---:|---:|---:|
| dense - lexical | +0.362 [+0.24, +0.48] \* | +0.271 [+0.18, +0.36] \* | +0.291 [+0.20, +0.38] \* | +0.362 [+0.24, +0.48] \* |
| hybrid - dense | -0.138 [-0.22, -0.05] \* | -0.144 [-0.22, -0.08] \* | -0.129 [-0.20, -0.07] \* | -0.138 [-0.22, -0.05] \* |
| hybrid - lexical | +0.224 [+0.12, +0.33] \* | +0.127 [+0.08, +0.18] \* | +0.162 [+0.10, +0.22] \* | +0.224 [+0.12, +0.33] \* |

Latency per stage, p50 / p95:

| mode | query (ms) | dense (ms) | lexical (ms) | fuse (ms) |
|---|---:|---:|---:|---:|
| dense | 0.1 / 0.2 | 15.2 / 22.0 | 0.0 / 0.0 | 0.1 / 0.1 |
| hybrid | 0.1 / 0.1 | 14.9 / 20.9 | 1.6 / 2.6 | 0.1 / 0.2 |
| lexical | 0.0 / 0.1 | 0.0 / 0.0 | 1.3 / 1.9 | 0.0 / 0.0 |

#### mini v2, dev: 22 answerable questions

Peak resident memory of the run (ingestion and all three modes): 1534 MiB.

| mode | n | hit@1 | hit@5 | recall@5 | mrr@10 | ndcg@10 | evidence@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 22 | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] |
| hybrid | 22 | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] |
| lexical | 22 | 0.955 [0.86, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 0.977 [0.93, 1.00] | 0.983 [0.95, 1.00] | 1.000 [1.00, 1.00] |

Paired differences (first minus second):

| pair | hit@5 | mrr@10 | ndcg@10 | evidence@5 |
|---|---:|---:|---:|---:|
| dense - lexical | +0.000 [+0.00, +0.00] | +0.023 [+0.00, +0.07] | +0.017 [+0.00, +0.05] | +0.000 [+0.00, +0.00] |
| hybrid - dense | +0.000 [+0.00, +0.00] | +0.000 [+0.00, +0.00] | +0.000 [+0.00, +0.00] | +0.000 [+0.00, +0.00] |
| hybrid - lexical | +0.000 [+0.00, +0.00] | +0.023 [+0.00, +0.07] | +0.017 [+0.00, +0.05] | +0.000 [+0.00, +0.00] |

Latency per stage, p50 / p95:

| mode | query (ms) | dense (ms) | lexical (ms) | fuse (ms) |
|---|---:|---:|---:|---:|
| dense | 0.1 / 0.1 | 16.8 / 22.3 | 0.0 / 0.0 | 0.0 / 0.1 |
| hybrid | 0.1 / 0.1 | 18.6 / 25.9 | 1.7 / 3.8 | 0.1 / 0.1 |
| lexical | 0.1 / 0.1 | 0.0 / 0.0 | 1.2 / 2.0 | 0.0 / 0.0 |

#### mini v2, test: 14 answerable questions

Peak resident memory of the run (ingestion and all three modes): 1527 MiB.

| mode | n | hit@1 | hit@5 | recall@5 | mrr@10 | ndcg@10 | evidence@5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| dense | 14 | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] |
| hybrid | 14 | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] | 1.000 [1.00, 1.00] |
| lexical | 14 | 0.714 [0.50, 0.93] | 0.929 [0.79, 1.00] | 0.929 [0.79, 1.00] | 0.820 [0.65, 0.96] | 0.858 [0.74, 0.97] | 0.929 [0.79, 1.00] |

Paired differences (first minus second):

| pair | hit@5 | mrr@10 | ndcg@10 | evidence@5 |
|---|---:|---:|---:|---:|
| dense - lexical | +0.071 [+0.00, +0.21] | +0.180 [+0.04, +0.35] \* | +0.142 [+0.04, +0.27] \* | +0.071 [+0.00, +0.21] |
| hybrid - dense | +0.000 [+0.00, +0.00] | +0.000 [+0.00, +0.00] | +0.000 [+0.00, +0.00] | +0.000 [+0.00, +0.00] |
| hybrid - lexical | +0.071 [+0.00, +0.21] | +0.180 [+0.04, +0.35] \* | +0.142 [+0.04, +0.27] \* | +0.071 [+0.00, +0.21] |

Latency per stage, p50 / p95:

| mode | query (ms) | dense (ms) | lexical (ms) | fuse (ms) |
|---|---:|---:|---:|---:|
| dense | 0.1 / 0.1 | 18.8 / 25.6 | 0.0 / 0.0 | 0.1 / 0.1 |
| hybrid | 0.1 / 0.1 | 22.3 / 40.8 | 1.6 / 2.8 | 0.1 / 0.2 |
| lexical | 0.1 / 0.1 | 0.0 / 0.0 | 1.2 / 1.7 | 0.0 / 0.0 |

`\*` the interval of the paired difference excludes zero.

## Reranking

#### reranking, hard v2, dev (this baseline)

not run: the resource gate refused it

#### reranking, mini v2, dev (this baseline)

not run: the resource gate refused it

#### reranking, hard v1, dev (earlier measurement, version 1 labels)

| mode | n | metric | reranking off | reranking on | difference [95 % CI] |
|---|---:|---|---:|---:|---|
| dense | 53 | hit@1 | 0.698 | 0.943 | +0.245 [+0.132, +0.358] \* |
| dense | 53 | mrr@10 | 0.779 | 0.972 | +0.193 [+0.115, +0.278] \* |
| dense | 53 | ndcg@10 | 0.811 | 0.970 | +0.159 [+0.094, +0.236] \* |
| dense | 53 | evidence@5 | 0.906 | 0.994 | +0.088 [+0.013, +0.182] \* |
| hybrid | 53 | hit@1 | 0.509 | 0.943 | +0.434 [+0.302, +0.566] \* |
| hybrid | 53 | mrr@10 | 0.562 | 0.972 | +0.410 [+0.299, +0.533] \* |
| hybrid | 53 | ndcg@10 | 0.604 | 0.970 | +0.366 [+0.266, +0.480] \* |
| hybrid | 53 | evidence@5 | 0.623 | 0.994 | +0.371 [+0.239, +0.509] \* |

| mode | search p50 / p95 off (ms) | search p50 / p95 on (ms) | rerank stage p50 / p95 (ms) |
|---|---:|---:|---:|
| dense | 16 / 21 | 3220 / 4015 | 3182 / 3975 |
| hybrid | 18 / 24 | 3266 / 3951 | 3247 / 3927 |

Peak resident memory of the process with both models loaded: 2492 MiB.

#### reranking, mini v1, dev (earlier measurement, version 1 labels)

| mode | n | metric | reranking off | reranking on | difference [95 % CI] |
|---|---:|---|---:|---:|---|
| dense | 36 | hit@1 | 1.000 | 0.944 | -0.056 [-0.139, +0.000] |
| dense | 36 | mrr@10 | 1.000 | 0.972 | -0.028 [-0.069, +0.000] |
| dense | 36 | ndcg@10 | 1.000 | 0.979 | -0.021 [-0.051, +0.000] |
| dense | 36 | evidence@5 | 1.000 | 1.000 | +0.000 [+0.000, +0.000] |
| hybrid | 36 | hit@1 | 1.000 | 0.917 | -0.083 [-0.194, +0.000] |
| hybrid | 36 | mrr@10 | 1.000 | 0.958 | -0.042 [-0.097, +0.000] |
| hybrid | 36 | ndcg@10 | 1.000 | 0.969 | -0.031 [-0.072, +0.000] |
| hybrid | 36 | evidence@5 | 1.000 | 1.000 | +0.000 [+0.000, +0.000] |

| mode | search p50 / p95 off (ms) | search p50 / p95 on (ms) | rerank stage p50 / p95 (ms) |
|---|---:|---:|---:|
| dense | 16 / 21 | 3254 / 4154 | 3229 / 4115 |
| hybrid | 17 / 24 | 3097 / 4120 | 3077 / 4100 |

Peak resident memory of the process with both models loaded: 2513 MiB.

The reranker (`bge-reranker-v2-m3-int8`) stays **off by default** ([ADR 0014](adr/0014-reranker-off-by-default.md)).
On version 1 labels it raised the hard dev scores a great deal and slowed a search from about 20 ms to
about 3.3 s (p50) with a 2.5 GiB peak; on the saturated mini set it could only lose. Nothing here
changes that decision, and the version 2 run is a blocker only for restating the numbers, not for the
release.

## Version 1 against version 2, and why they differ

Version 2 corrects the labels of 14 retrievable questions (the list and the reasons are in
[`eval/datasets/CHANGES_v2.json`](../eval/datasets/CHANGES_v2.json)); the corpus and the retrieval code
are the same. Because the same code scored the same corpus, an unchanged question must score the same
in both versions, and does: the table's last line is the part of the movement that no changed question
accounts for (0.0000 on the hard set; 0.0017 on the mini test split, one question whose scores tie and
whose order differs from run to run).

#### hard: version 1 to version 2, dev

| mode | hit@1: v1 → v2 (Δ) | mrr@10: v1 → v2 (Δ) | ndcg@10: v1 → v2 (Δ) | evidence@5: v1 → v2 (Δ) |
|---|---:|---:|---:|---:|
| dense | 0.698 → 0.698 (+0.000) | 0.779 → 0.788 (+0.009) | 0.811 → 0.826 (+0.014) | 0.906 → 0.915 (+0.009) |
| hybrid | 0.509 → 0.528 (+0.019) | 0.562 → 0.581 (+0.019) | 0.604 → 0.625 (+0.022) | 0.623 → 0.632 (+0.009) |
| lexical | 0.509 → 0.528 (+0.019) | 0.509 → 0.528 (+0.019) | 0.503 → 0.521 (+0.018) | 0.509 → 0.519 (+0.009) |

| question | change | dense | hybrid | lexical |
|---|---|---|---|---|
| `en_travel-1-cross` | ambiguity | mrr +0.36, ndcg +0.30, evidence +1.00 | hit +1.00, mrr +1.00, ndcg +1.00, evidence +1.00 | hit +1.00, mrr +1.00, ndcg +1.00, evidence +1.00 |
| `multi_doc-3` | gold | ndcg +0.18, evidence -0.50 | ndcg +0.15, evidence -0.50 | ndcg -0.06, evidence -0.50 |
| `ru_travel-1-cross` | ambiguity | mrr +0.10, ndcg +0.29 | no change | no change |

Movement not explained by a changed question: at most 0.0000.

#### hard: version 1 to version 2, test

| mode | hit@1: v1 → v2 (Δ) | mrr@10: v1 → v2 (Δ) | ndcg@10: v1 → v2 (Δ) | evidence@5: v1 → v2 (Δ) |
|---|---:|---:|---:|---:|
| dense | 0.707 → 0.724 (+0.017) | 0.810 → 0.822 (+0.011) | 0.844 → 0.859 (+0.015) | 0.943 → 0.948 (+0.006) |
| hybrid | 0.586 → 0.586 (+0.000) | 0.680 → 0.678 (-0.003) | 0.725 → 0.730 (+0.004) | 0.805 → 0.810 (+0.006) |
| lexical | 0.517 → 0.517 (+0.000) | 0.549 → 0.551 (+0.002) | 0.556 → 0.568 (+0.011) | 0.586 → 0.586 (+0.000) |

| question | change | dense | hybrid | lexical |
|---|---|---|---|---|
| `en_release-1-cross` | ambiguity | mrr +0.17, ndcg +0.13 | mrr +0.33, ndcg +0.50, evidence +1.00 | mrr +0.12, ndcg +0.32 |
| `multi_doc-5` | gold | ndcg +0.40, evidence +0.33 | ndcg +0.39, evidence +0.33 | ndcg +0.35 |
| `ru_it-2-cross` | ambiguity | hit +1.00, mrr +0.50, ndcg +0.37 | no change | no change |
| `ru_release-1-cross` | ambiguity | no change | mrr -0.50, ndcg -0.63, evidence -1.00 | no change |

Movement not explained by a changed question: at most 0.0000.

#### mini: version 1 to version 2, dev

| mode | hit@1: v1 → v2 (Δ) | mrr@10: v1 → v2 (Δ) | ndcg@10: v1 → v2 (Δ) | evidence@5: v1 → v2 (Δ) |
|---|---:|---:|---:|---:|
| dense | 1.000 → 1.000 (+0.000) | 1.000 → 1.000 (+0.000) | 1.000 → 1.000 (+0.000) | 1.000 → 1.000 (+0.000) |
| hybrid | 1.000 → 1.000 (+0.000) | 1.000 → 1.000 (+0.000) | 1.000 → 1.000 (+0.000) | 1.000 → 1.000 (+0.000) |
| lexical | 0.955 → 0.955 (+0.000) | 0.977 → 0.977 (+0.000) | 0.983 → 0.983 (+0.000) | 1.000 → 1.000 (+0.000) |

| question | change | dense | hybrid | lexical |
|---|---|---|---|---|

Movement not explained by a changed question: at most 0.0000.

#### mini: version 1 to version 2, test

| mode | hit@1: v1 → v2 (Δ) | mrr@10: v1 → v2 (Δ) | ndcg@10: v1 → v2 (Δ) | evidence@5: v1 → v2 (Δ) |
|---|---:|---:|---:|---:|
| dense | 1.000 → 1.000 (+0.000) | 1.000 → 1.000 (+0.000) | 1.000 → 1.000 (+0.000) | 1.000 → 1.000 (+0.000) |
| hybrid | 1.000 → 1.000 (+0.000) | 1.000 → 1.000 (+0.000) | 1.000 → 1.000 (+0.000) | 1.000 → 1.000 (+0.000) |
| lexical | 0.714 → 0.714 (+0.000) | 0.821 → 0.820 (-0.002) | 0.860 → 0.858 (-0.002) | 0.929 → 0.929 (+0.000) |

| question | change | dense | hybrid | lexical |
|---|---|---|---|---|
| `en-p5` | unchanged: tie-breaking between equal scores | no change | no change | mrr -0.02, ndcg -0.02 |

Movement not explained by a changed question: at most 0.0017.

How to read it:

- **`en_travel-1-cross`, `ru_travel-1-cross`, `en_release-1-cross`, `ru_it-2-cross`** (ambiguity fixes):
  the old wording was also answered by a document in the question's own language, so the right document
  was out-ranked. With a cue only the gold document has, it is found: this is where most of the gain on
  dense and hybrid comes from (for example `en_travel-1-cross`, hit@1 0 to 1 on hybrid and lexical).
- **`ru_release-1-cross`** goes the other way on hybrid (MRR -0.50): the English question now names the
  Moscow time, which makes it harder for the hybrid fusion, not easier. Making a question unambiguous does
  not make it easy, and that is not tuned away.
- **`multi_doc-3`, `multi_doc-5`** (the root-cause fix, checked by looking at the top 5): in version 1
  the unrelated filler quote of `multi_doc-3` (office hours) happened to be among the top 5, so the
  question looked 3/3 covered; in version 2 its second real quote lives in a document in the other
  language (`en_db_backup.md`), which the top 5 does not reach, so `evidence@5` falls by 0.5 on every
  mode. For `multi_doc-5` it is the opposite: the filler (`ru_it.md`, critical requests) had nothing to
  do with the release question and was never retrieved (2/3), while the new question really asks about
  it and finds it (2/2), so `evidence@5` rises by 0.33. Neither movement is a change in the system.
- **Answer completeness (`conflicting-7`, `-9`), longer quotes, split facts and absence terms** change
  nothing a retrieval metric sees, and show no movement, as they should.
- Net effect on the means: dense nDCG@10 +0.014 (dev) and +0.015 (test), hybrid +0.022 and +0.004,
  lexical +0.018 and +0.011. These are inside the bootstrap intervals of the tables above; the correction
  made the labels truer, it did not make the system better.

## Latency and memory

- A dense search takes about 15 ms (p50; 22 ms p95) and a hybrid one about 17 to 19 ms of dense plus
  2 to 4 ms of lexical and 0.1 ms of fusion, with a warm model on this CPU. The query embedding is
  included in the dense stage.
- The process that ingested a corpus, loaded the model and ran all three modes peaked at **1.5 GiB**
  (1516 to 1546 MiB across the runs). The one-hour search soak of [TESTING.md](TESTING.md) stayed between
  1.10 and 1.16 GiB for the serving process alone.
- Reranking: 2.5 GiB peak and about 3.3 s per search on this CPU (version 1 run above).

## Limits of this evidence

1. **Labels are unreviewed** (drafted with an AI language model, then audited automatically). Nothing
   here is a quality claim until a person has reviewed them.
2. The hard set is small (53 and 58 scored questions per split) and artificial: 26 short documents in
   two languages built from one fact table, half of the questions asked in the other language.
3. The mini set is **saturated** for dense and hybrid; it can only detect a regression, not a gain.
4. The same code scored both versions; the comparison tells what the labels did, not what the system does
   on real documents.
5. Reranking on version 2 was not measured (resource gate); the version 1 figures are not restated.
6. The test splits were read through the counted guard; no parameter, threshold or algorithm was
   changed after seeing them.

## Reproducing it

```bash
E5=data/models/multilingual-e5-small/<revision>
for name in retrieval_mini_v2 retrieval_hard_v2; do
  uv run python eval/scripts/retrieval_eval.py --model-dir $E5 --dataset eval/datasets/$name.json \
      --split dev --include-unreviewed --output eval_runs/baseline_v2/${name}_dev.json
done                                 # add --split test --final for the counted test read
uv run python eval/scripts/rerank_bakeoff.py --embed-dir $E5 --rerank-dir data/models/bge-reranker-v2-m3-int8/<revision> \
    --dataset eval/datasets/retrieval_hard_v2.json --include-unreviewed --split dev   # needs 3.5 GiB free
uv run python eval/scripts/baseline_report.py          # the tables above
```

The regression baselines for the hashing embedder (`baselines/mini_hashing_dev_v2.json`,
`baselines/hard_hashing_dev_v2.json`) are checked in CI by `tests/e2e/test_eval_cli.py`.
