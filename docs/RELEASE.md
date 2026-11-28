# Release checklist

No release has been cut. This page lists what is ready, what a release needs, and the decisions
that belong to the owner. Nothing here tags, publishes or licenses anything.

## Ready

| Item | Evidence |
|---|---|
| Quality gates | ruff, format, mypy (strict), import contracts, tests on Python 3.12 and 3.13 in CI |
| Reproducible install | `uv.lock` checked in CI; the Docker image installs from hashes |
| Docker image | `Dockerfile`, `scripts/docker_smoke.sh`, a CI job; about 80 MB |
| Package | `scripts/package_smoke.sh` in CI |
| Backup and restore | `rag backup`, `rag verify`, `rag restore`; the drill is a test; runbook in [OPERATIONS.md](OPERATIONS.md) |
| Dependency audit | `pip-audit` and a licence check in CI; no forbidden licences ([THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)) |
| SBOM | `sbom.cdx.json` (CycloneDX 1.5), checked against the lock file in CI |
| Secret scan | gitleaks in CI |
| API contract | `docs/openapi.json`, compared in the tests |
| Documentation | README, architecture, API, CLI, operations, evaluation, testing, ADRs, security policy, provenance |

## Blockers for v0.1.0 Alpha (2026-11-28)

An Alpha is a statement that the engine works and is installable, not that its quality is proven.
Nothing technical stops the tag; what stops a *quality claim* is below, and the release notes must
carry the open items as known limitations.

**Needed from the owner before the tag** (none is technical):

1. The decision to tag `v0.1.0` and to call it an Alpha / pre-release, and to publish (repository
   visibility, description, topics, whether to publish the image or the package).
2. A read of the open items below, so the release notes say exactly what is and is not proven.

**Open criteria, none closed and none weakened** (they block claims, not the tag):

| # | Item | State |
|---|---|---|
| 1 | Sufficiency gate quality | 72.5 % correct refusals at 4.2 % false refusals on an independent held-out set, with the reranker; 32.5 % with dense alone; targets 90 % and 10 % ([EVALUATION.md](EVALUATION.md), [AUDIT.md](AUDIT.md)). A user can calibrate their own gate (`rag calibrate`, [CALIBRATION.md](CALIBRATION.md)); until then it is open and says so |
| 2 | Real language model | never run through the pipeline: the memory gate refused the 4B model (needs 4.1 GiB, 3.2 available); [LLM_VERIFICATION.md](LLM_VERIFICATION.md) says how to run it elsewhere |
| 3 | Human review of labels | none of the 185 questions of version 2 is reviewed (170 correct, 15 doubtful and 0 incorrect by the automatic audit); the 100-reviewed-questions criterion is unmet and no judge is calibrated; the page is `eval_runs/review_kit/review_kit.html` ([DATASET_REVIEW.md](DATASET_REVIEW.md)) |
| 4 | Retrieval baseline | measured on version 2 for dense, hybrid and lexical ([BASELINE_V2.md](BASELINE_V2.md)); **reranking on version 2 not measured** (resource gate: 3.5 GiB needed, about 2.7 available); version 1 figures stand and are marked as such |
| 5 | Soak | one hour of search passed; the harder variant (`--workers`, `--churn-every`) is written and not run (needs 2.5 GiB free; 1.9 to 2.7 available) |
| 6 | Database size | 5.6× the source text without vectors against about 3×; migration planned after the release ([ADR 0022](adr/0022-slimmer-storage.md)); say so in the release notes |
| 7 | Platforms | Linux and Python 3.12 / 3.13 verified in CI; macOS not verified |

## Decisions for the owner

- **Licence.** MIT (`LICENSE`, `pyproject.toml` and the README agree). Dependency licences are
  listed in `THIRD_PARTY_NOTICES.md`.
- **Version and tag.** The package says `0.0.1`. Whether the first release is `v0.1.0` and whether
  it is called a pre-release is the owner's call.
- **Publication.** Making the repository public, publishing the image or the package, and the
  repository's description and topics.
- **Review of the datasets** (`docs/DATASET_REVIEW.md`), which is what would make the evaluation
  numbers more than exploratory.

### Version: a recommendation, not a choice

- **Licence.** Decided by the owner (MIT). The model weights have their own licences and are not
  part of the repository.
- **Version.** Because the quality criteria are open (gate, real model, reviewed labels), `0.1.0`
  described as a pre-release fits better than `1.0.0`.

## Steps once those are decided

1. Merge everything; `main` green.
2. Set the version in `src/rag_engine/__init__.py`, move `CHANGELOG.md`'s Unreleased section under
   the version and date.
3. Regenerate the notices (`scripts/generate_notices.py`); the `LICENSE` file is already in place.
4. Run the Docker, package and soak checks on the exact commit.
5. Tag, create the GitHub release with the wheel, the SBOM and the notices attached.
6. Publish the image or the package only if the owner chose to.
