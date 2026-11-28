# Evaluation protocol

What is measured, how a run is recorded, and what a result is allowed to claim. The numbers that
exist today are in [RETRIEVAL_EVALUATION.md](RETRIEVAL_EVALUATION.md), [EMBEDDING_BAKEOFF.md](EMBEDDING_BAKEOFF.md)
and [TESTING.md](TESTING.md); this page is the method.

## Rules

1. **A label is not true until a person accepted it.** Metrics count only `accepted` and `edited`
   records. A run that uses unreviewed records needs `--include-unreviewed` and is marked
   *exploratory* everywhere it is shown. No tool here marks a record as reviewed.
2. **Every number has an interval.** 95 % percentile bootstrap over questions (seed from the dataset
   hash); questions that share a gold document can be resampled as clusters
   (`stats.cluster_bootstrap`). Comparisons are paired: the bootstrap of the difference, the sign
   test, McNemar's exact test for binary metrics, Holm's correction across metrics.
3. **Warnings travel with the numbers.** Fewer than 30 questions is *anecdotal*. A metric at 0.98
   or above whose interval reaches 1.0 is *saturated*: it cannot show an improvement.
4. **The test split is held out.** `rag eval run --split test` is refused without `--final`; each
   read is counted in `eval_runs/test_access.json`, and a run whose split was read more than once
   says *not held out any more*.
5. **A run is reproducible.** Its manifest holds the dataset and corpus hashes, the configuration
   hash, the embedding and language models, the index generation, the seed, the engine version, the
   git commit and the resources at the time.

## Commands

`rag eval validate DATASET` checks the schema, the anchors against the corpus, the splits and the
reviewers. `rag eval run --dataset D --split dev|test [--final] --mode dense|lexical|hybrid
--output RUN.json` scores retrieval against the configured index. `rag eval report RUN` prints a run
as Markdown. `rag eval compare A B` prints the paired comparison. `rag eval gate RUN BASELINE`
exits 12 when a metric is worse than the baseline by more than `--delta` (0.03): the mean must stay
above the baseline mean minus delta, and, when the same questions were scored, the lower bound of
the paired difference must not fall below minus delta.

## Baselines

`baselines/mini_hashing_dev_v1.json` is the retrieval run of the public mini corpus with the
deterministic hashing embedder. It is checked in the test suite (`tests/e2e/test_eval_cli.py`): the
current code must pass the gate, and a deliberately shallower search must fail it. It tests the code
and the pipeline; it says nothing about the quality of a real model, and its labels are unreviewed.

## Generation metrics

`evaluation/generation_metrics.py` and `evaluation/judge.py` define the metrics of an answer:
faithfulness (a deterministic proxy of numbers and names, and a claim judge), hallucination rate
(share of answered replies with an unsupported claim), citation precision and recall, correctness
and completeness against the reference, and the answerable-by-answered matrix with refusal
precision and recall, false-refusal rate and false-answer rate. A judge is **calibrated** only when
it agrees with a human-labelled sample at 90 % or more with Cohen's kappa of 0.8 or more
(`calibrate_judge`); until then its verdicts are not evidence. The lexical judge is a baseline, and
no language-model judge has been calibrated: that needs a human-labelled sample that does not
exist yet and a judge model that fits in memory beside the generator.

## The harder set (`retrieval-hard@v1`; corrected in v2)

> The numbers below were measured on version 1. Version 2 (`retrieval_hard_v2.json`) corrects labelling
> errors found by the question audit and leaves the corpus unchanged; version 1 stays frozen. See
> [DATASET_REVIEW.md](DATASET_REVIEW.md) for what changed. The retrieval results were recomputed on
> version 2 in [BASELINE_V2.md](BASELINE_V2.md), with a question-by-question comparison.

`eval/corpus/hard_v1` (26 short documents, English and Russian) and `eval/datasets/retrieval_hard_v1.json`
(141 questions, 68 on dev and 73 on test) are built by `eval/scripts/build_hard_dataset.py` from one
fact table and checked in the tests. They are meant to be hard: hard negatives (pairs with the same
structure and other numbers: database and laptop backups, travel and meal expenses), two pairs of
contradictory policy versions (`conflicting`), every fact asked in its own language and in the other
one (97 paraphrases, most of them across languages), five multi-document questions and 30
unanswerable questions about topics next to the corpus. **Every record is `unreviewed`** (drafted by
an AI language model, not by a person), so everything measured on it is exploratory.

### Sufficiency gate research (`eval/scripts/gate_research.py`)

Every rule is fitted on dev only; the test split was read once (`--final`, counter: 1, still
held out) and each fitted rule applied to it without refitting. Target: at most 10 % false refusals
and at least 90 % correct refusals.

| Rule (refuse below a threshold) | dev, fitted: false · correct | test: false refusals | test: correct refusals |
|---|---|---|---|
| dense cosine | 4/53 · 10/15 | 5/58 (8.6 %) | 11/15 (73.3 %) |
| best lexical score | 5/53 · 10/15 | 9/58 (15.5 %) | 9/15 (60.0 %) |
| dense margin | 4/53 · 6/15 | 7/58 (12.1 %) | 4/15 (26.7 %) |
| lexical coverage | 5/53 · 3/15 | 9/58 (15.5 %) | 3/15 (20.0 %) |
| dense OR coverage | 2/53 · 2/15 | 0/58 (0.0 %) | 2/15 (13.3 %) |
| logistic regression | 4/53 · 14/15 | 11/58 (19.0 %) | 10/15 (66.7 %) |

Five-fold cross-validation of the logistic rule on dev alone gave 4/53 false refusals and 12/15 correct refusals (80 %), against 14/15 when fitted and scored on the same data: the in-sample figure was overfitting.

What this shows, with the limits stated. **No rule reached 90 % correct refusals on held-out data.** The
dense cosine alone is the best of the simple rules (73.3 % correct, 8.6 % false refusals: the false-refusal
target is met, the other is not). Combining signals did not help on held-out data: the logistic rule
looked best on dev and was worse on test. A rule that accepts when either the dense or the coverage
signal passes refuses almost nothing (2 of 15), so such an OR must not be used with a coverage
threshold fitted this way. The unanswerable questions of this set are near misses, and a cosine
between a question and a passage about a neighbouring topic is high. With 15 unanswerable
questions per split one question is 6.7 percentage points, so even a good result here could not
confirm a 90 % target. **The criterion stays open.** It needs a larger reviewed set and probably a
signal that looks at the passage itself (the reranker's logit was not evaluated as a gate signal here).

### Reranker on the harder set (dev, 53 answerable questions, pool of 30)

Paired differences with 95 % intervals (`eval/scripts/rerank_bakeoff.py --split dev`):

| | dense, without → with | hybrid, without → with |
|---|---|---|
| hit@1 | 0.698 → 0.943 (+0.245, [+0.132, +0.358]) | 0.509 → 0.943 (+0.434, [+0.302, +0.566]) |
| MRR@10 | 0.779 → 0.972 (+0.193, [+0.115, +0.278]) | 0.562 → 0.972 (+0.410, [+0.299, +0.533]) |
| nDCG@10 | 0.811 → 0.970 (+0.159, [+0.094, +0.236]) | 0.604 → 0.970 (+0.366, [+0.266, +0.480]) |
| evidence@5 | 0.906 → 0.994 (+0.088, [+0.013, +0.182]) | 0.623 → 0.994 (+0.371, [+0.239, +0.509]) |

On this set the cross-encoder improves every metric significantly, unlike on the saturated mini set
(ADR 0014). The cost is unchanged: rerank stage p50 3.2 s and p95
4.0 s against the 1.5 s limit, and a process peak of
2.43 GiB. The numbers also show that hybrid retrieval is much worse than
dense here (hit@1 0.509 against 0.698 before reranking), because the lexical channel cannot match a
question to a document in the other language and its noise enters the fusion.

## What is not established

- No metric over a *reviewed* dataset exists; the owner has not reviewed any label.
- No real language model has been run through the pipeline (the memory gate refused it), so no
  faithfulness, hallucination rate or generation latency is measured.
- The sufficiency gate does not meet its target: best held-out result 73.3 % correct refusals at 8.6 % false refusals on an unreviewed set of 15 unanswerable test questions (above).
- The reranker's gain on the harder set is on dev only and on unreviewed labels; it was not confirmed on test (reading the test split again would end its held-out status).

## Independent gate check (2026-11-28)

`eval/scripts/gate_research_v2.py` with the set built by `eval/scripts/build_gate_set.py`
(`gate-heldout@v2`: 136 questions, 40 unanswerable, unreviewed). The rule (reranker logit alone) was
fixed on the calibration data before the set was read, once, through the counted guard.

| Signal | Correct refusals | False refusals |
|---|---|---|
| reranker logit | 72.5 % (29/40) | 4.2 % (4/96) |
| best dense cosine | 32.5 % (13/40) | 6.3 % (6/96) |

The target (90 % / 10 %) is not met; see [ADR 0020](adr/0020-gate-signal-precedence.md) and
[AUDIT.md](AUDIT.md). The set must not be used for tuning again.
