# Baselines

A baseline is a run kept in the repository so that a change which makes retrieval worse fails a
test. `mini_hashing_dev_v1.json` is the retrieval run of the public mini corpus
(`eval/corpus/mini_v1`) with the deterministic hashing embedder, hybrid mode, the `dev` split and
**unreviewed** labels: it checks that the code and the pipeline still behave, it says nothing about
the quality of a real model. Real-model runs live in `eval_runs/` (outside Git).

Regenerate only on purpose, and say why in the commit:

```bash
rag eval run --dataset eval/datasets/retrieval_mini_v1.json --split dev --mode hybrid \
    --include-unreviewed --output baselines/mini_hashing_dev_v1.json   # with the hashing embedder
```

The gate (`rag eval gate RUN BASELINE`, exit 12) fails when a metric is more than 0.03 below the
baseline, or when the paired interval of the difference reaches below -0.03.

## Version 2 of the datasets

`mini_hashing_dev_v2.json` and `hard_hashing_dev_v2.json` are the same kind of run on the corrected
dataset versions (`retrieval-mini@v2`, `retrieval-hard@v2`; see `docs/DATASET_REVIEW.md`). They are
regenerated with the same command and a corpus of the same name; the version 1 baseline stays for
the version 1 dataset. The hard baseline is for a deterministic pipeline check only: a hashing
embedder cannot match across languages, so its numbers say nothing about a real model.
