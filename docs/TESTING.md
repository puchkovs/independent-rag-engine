# Testing

All tests run without network access (`pytest-socket`), without models and without real AI
providers. Time and identifiers are injected (`FakeClock`, `make_ids`); Hypothesis uses a
fixed, derandomised profile.

| Directory | Marker | What it proves |
|---|---|---|
| `tests/unit` | `unit` | Pure logic: domain models and invariants, glob rules, MIME table (UTF-8, cp1251, koi8-r, UTF-16, binaries), guard and retry rules, exit codes, errors, config, CLI basics |
| `tests/contract` | `contract` | One suite per port, run against every adapter (`SourceAdapter` runs against the in-memory and the filesystem source) |
| `tests/architecture` | `architecture` | The import contracts reject violations |
| `tests/integration` | `integration` | Real SQLite and real directories: unit of work, migrations (including an upgrade of a real v1 database), WAL and single-writer behaviour, change detection, identity and rebase, mass-delete protection, job queue, repository operations, ingest log events |
| `tests/e2e` | `e2e` | The `rag` command in-process (injected container, fake clock) and as a real process |
| `tests/chaos` | `chaos` | `SIGKILL` at every stage (below) |
| `tests/integrity` | `integrity` | Data-model invariants and a model-based test of ingestion |
| `tests/perf` | `perf` | NFR-04 on 1000 files and the Phase 3 parsing and chunking budgets, measured; **not** part of the pull-request CI |

The pull-request CI runs `pytest -m "not perf"`. `make test-all` does the same with coverage.
`make perf` runs the budgets separately.

Phase 4's real-model probe and detailed exact dense-search measurements are opt-in local
commands in `eval/scripts/bakeoff_embedders.py` and `eval/scripts/benchmark_dense.py`. The
model probe is not a CI quality gate; it needs installed model weights and its small synthetic
dataset cannot establish a default. Measurements and limits are in
[`EMBEDDING_BAKEOFF.md`](EMBEDDING_BAKEOFF.md).

Tests marked `external` need locally provisioned model files and are skipped when they are
absent, so the standard CI needs neither weights nor a network. Run the real multilingual-e5-small
inference checks (identity digest, 384-d unit vectors, ranking in each language, determinism and
batch invariance, prefixes, the 512-token window counted with special tokens, refusal of a
concurrent call) with `RAG_TEST_E5_DIR=<model snapshot directory> uv run pytest tests/external`.
Sockets stay disabled, so a successful run also shows that nothing is fetched.

## Phase 4 acceptance: criteria and evidence

| Criterion | Evidence |
|---|---|
| NFR-01 memory: search over 10⁴ chunks ≤ 300 MiB, over 10⁵ (1024-d fp16) ≤ 600 MiB | `eval/scripts/benchmark_refresh.py` loads a real schema-v3 database through `FlatVectorIndex.refresh` in a fresh process: 10⁴ chunks peak 80.7 MiB, 10⁵ chunks peak 275.9 MiB (see [`EMBEDDING_BAKEOFF.md`](EMBEDDING_BAKEOFF.md)) |
| NFR-03 dense search p95 ≤ 100 ms at 10⁴ and ≤ 400 ms at 10⁵ (4 vCPU) | `eval/scripts/benchmark_dense.py` (two runs: 10⁴ p95 25.4 and 53.8 ms; 10⁵ p95 216.1 and 255.4 ms) and the CI-excluded budget test `tests/perf/test_flat_vector_index.py` |
| NFR-05 one edited paragraph in a 100-chunk document re-embeds ≤ 3 chunks | `tests/e2e/test_indexed_ingest_cli.py::test_one_paragraph_edit_reembeds_at_most_three_of_hundred_chunks`, with and without section headings; counts the inputs the provider actually receives |
| NFR-06 `kill -9` at any point leaves a database that opens, passes `doctor --integrity`, and a rerun completes | `tests/chaos/test_kill_points.py` (every ingestion stage), `tests/chaos/test_index_publication_kill.py` (inside publication), `tests/chaos/model_switch_child.py` via the e2e test (inside the model switch) |
| Atomic publication | `tests/integration/test_index_publication.py`, `tests/integration/test_publication_guards.py` (every fencing guard refuses and leaves no version) |
| `doctor --integrity` finds corruption and never writes | `tests/integration/test_integrity_corruption.py` (16 injected corruptions, each reported by name, file hash unchanged; damaged vectors and model metadata are also refused when the flat index loads), `tests/e2e/test_indexed_ingest_cli.py` |
| `doctor --integrity` clean after 1000 random operations | the e2e test applies 1000 lexical, rebuild, GC and search operations drawn from a seeded `random.Random(4)` and checks the database after them; `tests/integrity/test_ingestion_model.py` is the model-based Hypothesis test that checks the invariants after every step. The 1000-operation sequence is seeded pseudo-random, not Hypothesis |
| Model switching, GC, FTS consistency | the e2e test (`index switch-model`, interrupted switch, retention GC, `index rebuild --lexical`), `tests/contract/test_sqlite_lexical_index.py`, `tests/integration/test_migrations.py::test_v3_fts_uses_stable_chunk_rowids` |
| Embedding service (batches, cache, retry, limits, norms) and providers | `tests/unit/test_embedding_service.py`, `tests/contract/test_embedding_provider_contract.py`, `tests/contract/test_ollama_embedder.py`, `tests/contract/test_onnx_embedder.py`, real weights in `tests/external/` |
| End-to-end ingestion | `tests/e2e/test_indexed_ingest_cli.py::test_configured_ingest_publishes_current_version` |
| D-03 decision recorded | [ADR 0012](adr/0012-embedding-default-evaluation.md) |

Total statement-and-branch coverage is 94 % (93 % before the failure-path tests of this phase,
96–97 % at the end of Phase 3). The remaining gap is code that only runs with real weights
(`embedding/onnx.py`, covered by the opt-in `external` tests), the isolated parser worker (its
process is not measured by coverage) and CLI error branches.

**Known limit: native HTML allocation failures.** When the memory cap of the parser worker is
exhausted inside the native HTML library, the library raises `SelectolaxError("Can't parse
HTML.")`. That is indistinguishable from malformed input, so the worker reports `corrupt`
instead of `memory`. Measured with a 400 MB data limit: the data segment was full (400 of 400 MB)
in one case and at 345 MB in another, and the worker starts with a baseline of its own, so no
threshold separates the two cases reliably. The classifier is unchanged; isolation still contains
the failure.

## Phase 5 acceptance: criteria and evidence

| Criterion | Evidence |
|---|---|
| Retrieval evaluation is reproducible (manifest) | `eval/scripts/retrieval_eval.py` records dataset and corpus SHA-256, embedding model identity, index generation, seed, depths and Python version; the seed derives from the dataset hash and resampling is seeded (`tests/unit/test_retrieval_metrics.py`, `tests/unit/test_eval_runner.py`) |
| Choice of dense or hybrid justified by a paired interval (RETRIEVAL_DESIGN §5) | [`RETRIEVAL_EVALUATION.md`](RETRIEVAL_EVALUATION.md) and [ADR 0013](adr/0013-default-retrieval-mode.md): the available set is saturated and unreviewed, so the default stays `dense`; this criterion is met as a documented decision, not as a measured preference |
| Search p95 at 10⁴ chunks at most 100 ms | `eval/scripts/benchmark_search.py 10000`: hybrid p95 30.2 ms, dense 22.9 ms, lexical 9.0 ms (query embedding excluded) |
| Filters without raw SQL | `tests/integration/test_chunk_filters.py`: bound parameters only, hostile values (quote, `%`, `_`, NUL, `DROP TABLE`) are data, value lists are capped, a malformed glob is `E_FILTER_INVALID` |
| Deterministic ranking | `tests/unit/test_fusion.py` (ties by chunk id), `tests/unit/test_search_service.py` and `tests/e2e/test_search_cli.py` (the same query returns the same hits) |
| Duplicate suppression | `tests/unit/test_diversity.py`, `tests/unit/test_search_service.py` |
| Query processing and the model prefix | `tests/unit/test_query_processor.py`, `tests/unit/test_search_service.py` |
| `rag search` end to end | `tests/e2e/test_search_cli.py` over a real index built by `rag ingest` |

Not met: the labels of the question set are unreviewed (owner action), so no quality figure from
it is an acceptance result; MVP-0 is reached functionally and awaits that review.

## Phase 6 acceptance: criteria and evidence

| Criterion | Evidence |
|---|---|
| No silent truncation or dropping of context on 1000 random cases (NFR-07) | `tests/unit/test_context_properties.py`: 1000 random corpora, budgets and policies; the budget is never exceeded, every retrieved chunk is shown, merged or dropped with a reason exactly once, evidence equals the document slice at its locator, every cut is declared, the only failure is `E_CONTEXT_BUDGET` with a hint |
| `tokens_used <= budget` | the same property, and `tests/unit/test_context_builder.py` with hand-computed budgets |
| Reranker enabled only with a proven gain, otherwise an ADR "off" | [ADR 0014](adr/0014-reranker-off-by-default.md): measured with the real `bge-reranker-v2-m3-int8`: no gain on a saturated set, a small loss, p95 4.1 s against a 1.5 s limit, so it stays off. Real-weights tests: `RAG_TEST_RERANK_DIR=<dir> uv run pytest tests/external` |
| Reranker failure never fails a query | `tests/unit/test_rerank_stage.py`, `tests/unit/test_search_service.py`, `tests/e2e/test_search_cli.py` |
| Citation provenance survives context building | evidence keeps document, version, source key, heading path, pages and character span, and the retrieved chunks it stands for (`tests/unit/test_context_builder.py`) |
| System prompt size regression | `tests/unit/test_system_prompt.py`: pinned hash, measured 209 tokens, limit 260 |
| Gate: false refusals at most 10 % and correct refusals at least 90 % on dev | **not met** with the dense cosine on the exploratory set: 4.5 % false, 83.3 % correct (see [`RETRIEVAL_EVALUATION.md`](RETRIEVAL_EVALUATION.md)); invalidation of the calibration on a model change is tested (`tests/unit/test_sufficiency.py`, `tests/integration/test_integrity_corruption.py`) |
| `rag search --rerank`, `rag context QUERY` | `tests/e2e/test_search_cli.py` |

Not met: the gate target. The reranker was measured and does not meet the conditions for being enabled; the decision is recorded.

## Phase 7 acceptance: criteria and evidence

| Criterion | Evidence |
|---|---|
| `LLMProvider` port and `ScriptedLLM` scenarios (P7.1) | `tests/contract/test_llm_provider_contract.py` runs against `ScriptedLLM` and `ResilientLLM(ScriptedLLM)` |
| `OllamaChat` native, `num_ctx`, `num_predict`, think, `prompt_eval_count`, `done_reason` (P7.2) | `tests/contract/test_chat_adapters.py` (mocked HTTP: request shape, usage, finish reason, thinking dropped, errors, cancellation); real model: `RAG_TEST_OLLAMA_CHAT_MODEL=<model> uv run pytest tests/external/test_ollama_chat.py` (behind the memory gate) |
| `OpenAICompatChat` with a mandatory `context_window` (P7.3) | the same file; the window is a required argument and setting; the key never appears in errors |
| Prompt `answer.v1` with `E#` markers and the sentinel, snapshot and size (P7.4) | `tests/unit/test_templates.py` (snapshot of the rendered prompt, marker defusing), `tests/unit/test_system_prompt.py` (pinned hash, 209 tokens, limit 260) |
| Truncated prompt caught on 100 % of the scenarios (P7.5) | `tests/unit/test_generator.py`: `prompt_eval_count` equal to or one below the window for windows 1024 to 8192; `tests/contract/test_chat_adapters.py` for the stream |
| No `answered` result shorter than the threshold (P7.6) | `tests/unit/test_generator.py`: one character, empty, whitespace, punctuation, a lone marker, and the same cut by the length limit all end in `E_DEGENERATE_ANSWER` after one retry; the default threshold is the specified 20 characters (markers excluded) and is configurable (`[answer] min_answer_chars`) |
| Timeout, retry, circuit breaker, semaphore (P7.7) | `tests/unit/test_resilience.py`, `tests/integration/test_generation_stack.py` |
| Stream equals non-stream (P7.8) | `tests/unit/test_generator.py` (event order, equal text and citations, refusal without text, retraction, `verified_only`), `tests/contract/test_llm_provider_contract.py`, `tests/e2e/test_generation_flow.py` |
| Real small-model smoke without out-of-memory, or a documented refusal by the gate (P7.9) | `eval/scripts/llm_smoke.py`; on 2026-11-27 the gate refused `qwen3.5:4b` (see below) |
| No invented sources | `tests/unit/test_generator.py`, `tests/e2e/test_generation_flow.py`: a marker that names no evidence fails after one retry and never reaches the caller |

P7.9, 2026-11-27: `qwen3.5:4b` (Q4_K_M, 3.1 GiB on disk, with a vision projector) needs its size plus
1 GiB of headroom, 4.1 GiB, and at least 0.5 GiB of free swap. The machine had 3.4 to 3.7 GiB
available and 0.03 GiB of free swap, with a desktop session running, so `llm_smoke.py` refused with
exit code 3 and the model was never loaded. This is the intended behaviour of the gate (an earlier
attempt to run the 4B embedding model here was killed for lack of memory), not a failure of
the adapter; the adapter is tested against mocked servers, and the real-model tests run once enough
memory is free. The 9B model was not tried.

Not claimed: faithfulness. The citation check is a lexical screen; faithfulness, hallucination
rate and citation accuracy are measured in Phase 10.

## Phase 8 acceptance: criteria and evidence

| Criterion | Evidence |
|---|---|
| Every branch of the status table is covered | `tests/e2e/test_pipeline.py` (answered, gate refusal, no hits, model refusal, fabricated citation, repaired citation, degenerate reply, provider failure, context budget, timeout, `test_every_status_is_reachable_and_only_answered_carries_text`); `tests/unit/test_pipeline_answer.py` for the invariants |
| A gate refusal calls no model | `test_a_gate_refusal_answers_without_calling_the_model` (spy: zero calls), the stream variant, and `test_a_question_nothing_matches_never_calls_the_model` through `rag ask` (no request reaches the chat server) |
| Fabricated citations do not pass | a marker outside the evidence is `unverified` after one retry (pipeline, stream and `rag ask`), the text is never the answer; markers inside documents are defused (`tests/unit/test_templates.py`) |
| NFR-07: no silent truncation or dropping | the context report is in `diagnostics.context` and in the `pipeline.context` log event (`test_a_cut_or_dropped_context_is_reported_in_diagnostics_and_in_the_log`); the 1000-case property test of Phase 6 still covers the builder |
| NFR-08: no one-character or empty `answered` | `test_a_one_character_or_empty_reply_is_never_answered` (five replies), the same set in `tests/unit/test_generator.py` including replies cut by the length limit, and the `PipelineAnswer` invariant |
| Verified streaming | `test_a_verified_stream_*`: no text before validation; `--live` marks drafts provisional and retracts them; the final event is the only authoritative one |
| Total time budget | `tests/unit/test_pipeline_budget.py` (shares, never more than what is left), `test_a_model_that_outlasts_the_total_budget_is_a_timeout_naming_the_stage` |
| Cancellation and concurrency | `test_a_request_cancelled_mid_generation_releases_everything`, `test_requests_are_served_one_at_a_time_by_default`, `test_a_higher_concurrency_limit_lets_requests_overlap_and_one_cancel_spares_the_other` |
| Release of models | `release()` on the embedder, the cross-encoder and the stage is tested (`tests/contract`, `tests/unit/test_rerank_stage.py`); the effect on memory was **measured**, not assumed: 383 MiB of 1160 MiB from `release()`, 760 MiB with `malloc_trim` (E5-small, one run, `eval/scripts/release_memory.py`); the reranker was not measured |
| `rag ask` with sources and refusal | `tests/e2e/test_ask_cli.py`: text, `--json`, `--sources`, refusal (exit 10), unverified (exit 11), provider error (exit 6), stream, `--live`, missing `[llm]`, bad arguments |
| Generation evaluation, oracle and e2e modes | `eval/scripts/generation_eval.py` over the mini dataset (unreviewed labels, so exploratory) with a **stub** model: e2e 44 of 44 answered with valid citations, oracle 36 of 36; correct refusals 0 of 8 because the stub never refuses and the gate has no calibration. This shows the wiring works. It is not a measurement of any model |

**MVP-1 is functionally implemented, not accepted on quality.** The pipeline answers, cites,
refuses and reports statuses on a scripted model in CI. The following are open and are not closed
by the stub run:

1. SufficiencyGate: 83.3 % correct refusals against the 90 % target (Phase 10).
2. Real LLM inference and its performance: no measurement exists; the memory gate refused the 4B
   model on this machine (see Phase 7).
3. Faithfulness and hallucination rate: not measured; the citation overlap check is a lexical screen.
4. The evaluation dataset has not been reviewed by the owner; every metric over it is exploratory.

## Phase 9 acceptance: criteria and evidence

| Criterion | Evidence |
|---|---|
| `/v1`: health, stats, sources, documents, jobs (P9.1) | `tests/api/test_manage.py` through an in-process client over a real store |
| `POST /v1/search`, `POST /v1/answers` and the server-sent events sequence (P9.2) | `tests/api/test_query.py`: evidence, delta, citations, final; verified text sent once; provisional drafts and `retract` in live mode; a failed stage is a `final` event of status `error` |
| problem+json, error codes, cursor pagination, `Idempotency-Key` (P9.3) | `tests/api/test_manage.py` (replay, conflict, no second write, cursors, bad cursors, limits), `tests/api/test_query.py` (engine codes in problems) |
| Security: token, no non-loopback bind without a token, size limits, CORS off (P9.4) | `tests/api/test_security.py` (401 everywhere but health, wrong scheme and token, token never echoed, public bind refused when serving, weak token refused, 413, question length, CORS), `tests/e2e/test_admin_cli.py` (`rag serve` refuses to start) |
| OpenAPI snapshot and its diff in CI (P9.5) | `tests/api/test_openapi.py` compares the generated document with `docs/openapi.json`; the CI test job fails on any difference; also checks endpoints, security and error documentation |
| CLI: `init`, `config`, `index rebuild`, `gc`, `backup`, `serve`, `--json`, exit codes (P9.6) | `tests/e2e/test_admin_cli.py`, `tests/e2e/test_ask_cli.py`; exit codes in [CLI.md](CLI.md) |
| API and CLI documentation checked against the schemas (P9.7) | `tests/api/test_docs.py`: every endpoint and command is documented, JSON examples parse |
| Cancellation and concurrency | `tests/e2e/test_pipeline.py` (cancel, concurrency limit); a client disconnect cancels the pipeline through the stream; a real `rag serve` was started on the loopback, answered health, refused anonymous reads when a token was set and created a managed source |

Not covered by an automated test: a real browser client, the `uvicorn` process under load, and the
effect of client disconnects on a live socket (the in-process client cannot simulate them). The
idempotency memory is per process by design.

## Phase 10 acceptance: criteria and evidence

| Criterion | Evidence |
|---|---|
| Generation metrics with hand-computed values (P10.1) | `tests/unit/test_generation_eval_metrics.py`: faithfulness proxy and judge, hallucination rate, citation precision/recall, correctness, no-answer matrix |
| Judge behind a port, calibration with kappa (P10.2) | `evaluation/judge.py`, `tests/unit/test_generation_eval_metrics.py`, `tests/unit/test_eval_stats.py` (kappa by hand). **No judge is calibrated**: no human-labelled sample exists |
| Paired tests, cluster bootstrap (P10.3) | `tests/unit/test_eval_stats.py`: McNemar exact, sign test, cluster bootstrap, Holm |
| Saturation and N < 30 warnings (P10.4) | `tests/unit/test_eval_stats.py`, `tests/unit/test_eval_protocol.py` (report flags) |
| Test split protection with an access counter (P10.5) | `tests/unit/test_eval_protocol.py`, `tests/e2e/test_eval_cli.py` (`--final` required, reads counted, a repeated read is reported as not held out) |
| Run manifest, `compare`, `report` (P10.6) | `tests/unit/test_eval_protocol.py`, `tests/e2e/test_eval_cli.py` |
| Baseline and regression gate in CI (P10.7) | `baselines/mini_hashing_dev_v1.json`; `tests/e2e/test_eval_cli.py`: the current code passes, a shallower search fails with exit 12 |
| Harder set: `conflicting`, `out_of_scope`/`no_answer`, hard negatives, near duplicates, multilingual (P10.8) | `eval/datasets/retrieval_hard_v1.json` (frozen) and `retrieval_hard_v2.json` (corrected; baseline in `docs/BASELINE_V2.md`), `tests/unit/test_hard_dataset.py`. **Not met:** at least 100 *reviewed* questions. 141 questions exist and all are `unreviewed`; only the owner can review them |
| Reranker on hard data | measured on dev: significant gain, cost unchanged, decision unchanged ([ADR 0018](adr/0018-hard-set-gate-and-reranker.md)) |
| Gate on a separate calibration and held-out split | `eval/scripts/gate_research.py`: fitted on dev, read test once. **Not met:** best held-out 73.3 % correct refusals at 8.6 % false refusals (target 90 % / 10 %); on the independent `gate-heldout@v2` the reranker rule gave 72.5 % / 4.2 % and dense 32.5 % / 6.3 % (ADR 0020) |
| Faithfulness, hallucination rate and generation latency on a real model | **Not measured**: the memory gate refused the 4B model and no judge is calibrated |

**Phase 10 is implemented as a method and a toolbox, not accepted on quality.** Open, unchanged:
the gate target, a reviewed dataset of at least 100 questions, a real-model measurement, faithfulness.

## Phase 11 acceptance: criteria and evidence

| Criterion | Evidence |
|---|---|
| Docker: multi-stage, pinned digests, non-root, healthcheck, at most 400 MB (P11.1) | `Dockerfile`; `scripts/docker_smoke.sh` in a CI job: 80 MB, user `rag` (uid 10001), refuses to start without a token, 401 without and 200 with it, healthy |
| README quickstart in a clean container | the same smoke script runs init, config check, source add, ingest, status, backup, verify and doctor inside a fresh container |
| Backup, restore, verify and a runbook; the restored database passes `doctor` (P11.2) | `tests/e2e/test_admin_cli.py` (the drill, the refusal to overwrite, a damaged backup never restored); [OPERATIONS.md](OPERATIONS.md) |
| Health and readiness, metrics, log rotation (P11.3) | `tests/api/test_manage.py`, `tests/api/test_security.py` (metrics by route template, token required), `tests/unit/test_log_rotation.py` |
| Soak, one search per minute for an hour: RSS growth under 10 %, errors under 2 %, no out-of-memory kill (P11.4) | **passed**, see below |
| Documentation with a link checker (P11.5) | README, ARCHITECTURE, DEVELOPMENT, TESTING, CONTRIBUTING, SECURITY, PROVENANCE, CHANGELOG, ADRs; `tests/unit/test_docs_links.py` |
| Licences, notices, SBOM, audit (P11.6) | `THIRD_PARTY_NOTICES.md` and `sbom.cdx.json` generated from `uv.lock` (54 components, none under a forbidden licence) and checked in CI; `pip-audit` and the licence check in CI |
| Release v0.1.0 and the decision on publicity (P11.7) | **not done on purpose**: a checklist is in [RELEASE.md](RELEASE.md); the version, tag and publication are the owner's decisions (the licence, MIT, is chosen) |
| Optional adapters, LanceDB/ANN and MCP (P11.8) | not implemented; the vector index and the pipeline sit behind ports, so they can be added without touching the core |
| Secret scan clean | gitleaks in CI, green on every pull request |
| Performance budgets (NFR-04 and the Phase 3 parse and chunk budgets) | `pytest -m perf` on the quiet reference machine, 2026-11-28: 14 of 14 within budget, for example a rescan of 1000 unchanged files in 0.15 s (budget 5 s) and 25 MB peak for a 2 MB document (budget 150 MB) |
| Concurrency | `tests/api/test_concurrency.py`: parallel readers and a writer give only 200, 202 or the retryable 503 `E_STORE_LOCKED`; an idempotent burst leaves one document |

### Soak (2026-11-28, `eval/scripts/soak.py`)

A real `rag serve` process with the real `multilingual-e5-small` model, an index of the hard corpus
(26 documents), one dense search per minute for 60 minutes, on the reference machine (4 vCPU, 7.8 GiB,
shared with a desktop session). **Scope: search only.** No language model ran, so this says nothing
about answers.

| | result | criterion |
|---|---|---|
| requests | 60 (all HTTP 200) | |
| error rate | 0.0 % | below 2 % |
| server died, out-of-memory kill | no, none in the kernel log during the run | none |
| resident memory, first request / third request / last | 1162 / 1139 / 1101 MiB | |
| growth, third request to last | -3.3 % (trend -36 MiB per hour) | below +10 % |
| resident memory, minimum / median / maximum | 1100 / 1112 / 1162 MiB | |
| search latency p50 / p95 / maximum | 64 ms / 163 ms / 6.3 s | |
| lowest available memory on the machine | 1.26 GiB | |

The slowest request (6.3 s) is the first one, which loads the model's session on first use;
the next slowest is 257 ms. Memory declined gradually from 1162 to 1101 MiB over the hour (the allocator returning pages after
the model's first use) and never rose; from the twentieth request on it moved within 16 MiB. Limits of this evidence: one run, one corpus of 26 short documents, one query
per minute (no concurrency), a warm file cache, and a process that had no ingestion going on.

**MVP-2 is functionally in place and its packaging criteria are met; it is not quality-accepted and not
released.** The open criteria are unchanged: the sufficiency gate (best held-out 73.3 % correct
refusals against 90 %), no real-model measurement (answer latency, faithfulness, hallucination
rate), no reviewed evaluation labels and no calibrated judge.

## Gate calibration (`rag calibrate`)

`tests/unit/test_gate_calibration.py` (question files, overlap, fitting, cross-validation, the bound
record and its warnings), `tests/e2e/test_calibrate_cli.py` (the whole story on a real index with
mocked model servers: open gate, calibrate, refuse, answer, doctor, stale setup, below target,
`--require-target`, dry run, clear, atomic save, concurrent index change), `tests/api/test_calibration.py`
(the API sees the CLI's calibration). The corpus is synthetic and separable on purpose
(`tests/calibration_support.py`), so these tests show the mechanism, not a quality.

## Failure injection (`tests/chaos`)

A child process (`tests/chaos/child.py`) kills itself with `SIGKILL` at one point; the test
then checks that the database opens, `integrity_check` and `foreign_key_check` pass, the
interrupted work is entirely absent or entirely present, and a second run reaches exactly the
state of an uninterrupted run (compared on a backup copy). Points: after scan, at the start
of apply, in the middle of apply (half of the documents written), before commit, after commit
before garbage collection, in the middle of garbage collection, in the middle of a job
(lease recovered, no duplicate, no job processed twice), and in the middle of migration `0002`
(old schema intact, retried cleanly, both backups present). `tests/integration` additionally
covers a kill inside a plain transaction and an injected failure between chunk insertion and FTS
publication. A child is killed after FTS writes during indexed publication; its retry publishes
one complete version. The indexed e2e test kills a model switch inside its final transaction,
verifies that the previous model and generation remain active, then resumes the switch.

## Data integrity (`tests/integrity`)

`rag doctor --integrity` opens a read-only SQLite snapshot. It checks SQLite and foreign keys,
document/version ownership, current pointers, compressed text and chunk offsets, content hashes,
deterministic chunk IDs, the FTS row set, active-model coverage, vector dimensions, finite norms,
model IDs, and index generation. Deliberately corrupted copies exercise each class of error and
verify that inspection does not alter the database. The model-based ingestion test runs doctor
after every operation in 80 sequences of 22 steps (1760 steps total); the indexed e2e test also
checks doctor after 1000 deterministic lexical, rebuild, GC and search operations.

The one-paragraph NFR-05 scenario publishes exactly 100 indexed chunks in each of two documents:
one with section headings and one without. It edits one middle paragraph and counts actual
provider inputs. Both cases require 1–3 new embeddings and a sound store. The recursive chunker
anchors packing at paragraph groups so a local edit does not shift unrelated later boundaries.

`checks.py` holds the invariants as `check_*` functions (no orphans, version ownership,
unversioned documents are not searchable, sync state and documents agree, one active job per
document, index state mirrors the migrations). They run at teardown of every test that uses the
`workspace` fixture. `test_ingestion_model.py` is a Hypothesis state machine: random sequences
of create/modify/delete/rename/wait/rescan (including steps around the 30-day grace boundary)
are compared with a naive model of the ingestion rules after every rescan; identities must not
change. Changing the grace period in the model by one day makes it fail.

## Parsing and chunking (Phase 3)

- **Contracts.** `tests/contract/test_parser_contract.py` runs every parser (md, html, txt, pdf,
  docx) over valid samples, empty and oversized input, arbitrary bytes and mutated samples;
  `test_chunker_contract.py` runs every chunking strategy over the same documents, policies and
  random documents; `test_token_counter_contract.py` covers both counters.
- **Corpus.** `tests/fixtures/corpus_mini` holds twenty-one original Russian, English and mixed
  documents (Markdown, HTML, text, a cp1251 file, PDF and DOCX). `generate_corpus_mini.py`
  recreates them byte for byte.
- **Golden snapshot.** `tests/fixtures/golden/corpus_mini.json` records, for each document, the
  parser, versions, text hash, and every chunk (level, parent, kind, tokens, offsets, text hash,
  heading path, language, pages, duplicate flag). Any change in normalisation, parsing or chunk
  boundaries is a diff. After an intended change run
  `uv run python tests/fixtures/update_golden.py` and review the diff.
- **Properties.** `tests/unit/test_pipeline_properties.py` generates Markdown, HTML and text and
  random size policies; every strategy must refuse a document with a documented error or return
  chunks that satisfy the data-model invariants, cover the text, respect `max_tokens` and are
  identical on a second run; without overlap the leaves rebuild the text.
- **Fuzzing.** `tests/integration/test_pipeline_fuzz.py` mutates every corpus file with a fixed
  seed (flipped bytes, truncation, deleted, inserted, duplicated and zeroed ranges) and checks
  the same outcome rule; the isolated worker must give the outcome of in-process parsing.
- **Isolation.** `tests/integration/test_parser_isolation.py` runs parsers that hang, crash,
  exhaust memory, recurse, print to the protocol channel, read the environment or raise.
  A native HTML-library allocation failure may surface as a generic exception and be reported
  as `corrupt`; no reliable reproducer that distinguishes this from malformed input has been
  established, so the classifier is unchanged.

## NFR-04

`tests/perf/test_nfr04_rescan.py` ingests 1000 files, drains the queue through a spy parser,
then rescans. It asserts: at most 5 s, 0 parser calls, 0 jobs, and an identical hash of the
logical database dump (`tests/workspace.py: logical_dump`).

Measured on 2026-11-22 with `make perf` (4 vCPU, Python 3.12.3, SQLite 3.45.1, ext4, three runs
on the code of the Phase 2 compliance PR):

| Run | First scan, 1000 files | Rescan, 1000 unchanged (service) | Rescan through the CLI |
|---|---|---|---|
| 1 | 0.315 s | 0.099 s | 0.048 s |
| 2 | 0.358 s | 0.093 s | 0.065 s |
| 3 | 0.311 s | 0.102 s | 0.068 s |

Budget: 5 s. Parser calls on rescan: 0. Jobs created: 0. Logical database dump: unchanged.

## Phase 3 performance budgets

`tests/perf/test_phase3_pipeline.py` generates its inputs (no stored binaries) and prints one
line per measurement. The budgets are multiples (about five times, ten for the worker round
trip) of the measurements below; they exist to catch an accidental quadratic step, and like all
initial budgets they may be revised with new measurements.

Measured on 2026-11-22 with `make perf` (4 vCPU, Python 3.12.3, three runs on the code of the
hardening PR; seconds, heuristic token counter, default chunk policy 256/384/48/12 %). Sizes
in the table are *characters* of generated text: "1 MB" of Cyrillic Markdown is 1.8 MB on disk.):

| Measurement | Run 1 | Run 2 | Run 3 | Budget |
|---|---|---|---|---|
| Count tokens of 6 MB of text | 1.28 | 1.29 | 1.38 | 7 |
| Markdown, 1 MB, parse + chunk (structure-aware) | 3.49 | 3.34 | 3.28 | 15 |
| HTML, 1 MB, parse + chunk | 1.78 | 1.74 | 1.79 | 10 |
| Plain text, 1 MB, parse + chunk (recursive) | 1.00 | 1.04 | 1.06 | 6 |
| Chunk 1 MB, structure-aware | 1.42 | 1.31 | 1.33 | 15 |
| Chunk 1 MB, recursive | 1.01 | 1.04 | 0.92 | 15 |
| Chunk 1 MB, fixed | 2.96 | 3.15 | 3.27 | 15 |
| PDF, 100 pages, parse + chunk | 0.61 | 0.62 | 0.75 | 5 |
| DOCX, 2000 paragraphs, parse + chunk | 2.08 | 2.21 | 2.17 | 10 |
| Isolated worker: start + first document | 0.95 | 0.79 | 0.74 | 5 |
| Isolated worker: one more 20 KB document | 0.004 | 0.005 | 0.004 | 0.5 |
| Peak Python memory (`tracemalloc`), Markdown of 2 million characters (3.6 MB) parse + chunk | 25 MB | 25 MB | 25 MB | 150 MB |

The worker adds under a second once per process and a few milliseconds per document.

## Memory

Measured on 2026-11-22 (4 vCPU, Python 3.12.3, Linux) with generated documents, each parsed in a
fresh process (scripts are not part of the repository; the perf test above repeats the
`tracemalloc` case). Sizes are millions of characters of normalised text (Mchar).

**Python-level peak, parse + chunk (`tracemalloc`), MB per Mchar**

| Format | 0.5 Mchar | 1 Mchar | 2 Mchar |
|---|---|---|---|
| Plain text | 5.0 | 5.0 | n/a |
| HTML | 11.0 | 9.4 | n/a |
| DOCX | 12.0 | 10.0 | 9.4 |
| Markdown (Cyrillic) | 12.9 | 12.4 | 12.4 |
| PDF | about 2 MB in total for up to 100 pages (the text is small) | | |

**Growth of the peak resident set (RSS) over the 70 MB of a process that has only imported the
code, at 4 Mchar (2 Mchar for DOCX), MB per Mchar:** Markdown 9.0, HTML 5.8, DOCX 5.4, plain text
1.8 for parsing and 3.5 for parsing and chunking, PDF about 0.

**Smallest worker cap (`isolation_memory_mb`, `RLIMIT_DATA`) that still parsed the document**,
among 192, 256, 320, 384, 448, 512 and larger:

| Document | Result |
|---|---|
| any format up to 4 Mchar (Markdown 7 MB on disk) | 256 MB suffices; 192 MB did not |
| HTML, 16.3 Mchar (16.5 MB) | 384 MB (320 MB failed) |
| Markdown, 16.4 Mchar (28.6 MB) | 448 MB (384 MB failed) |
| plain text, 19.0 Mchar (19 MB) | 320 MB |

What this means, and what it does not:

- The figures are not interchangeable. `tracemalloc` sees Python allocations only, adds its own
  overhead and misses native memory (the HTML parser's C library, the allocator); RSS growth
  misses memory that the process had already mapped and freed, so it under-reports small
  documents; the worker cap counts *virtual* data segment, including about 200 MB that exist
  before the first document. A ratio such as "N times the text" is only meaningful together
  with its metric and its unit (characters, not bytes).
- **Conservative budget.** Main process: 15 MB per Mchar on top of a 70 MB baseline (the worst
  measured Python-level peak is 12.9). Worker: 250 MB plus 14 MB per Mchar (the worst measured
  need is 448 MB at 16.4 Mchar, which this rule covers); the default text limit of 20 Mchar
  gives about 530 MB against the default cap of 1024 MB. Do not set `isolation_memory_mb` below
  512 MB when documents of that size are expected.
- Not measured: DOCX and PDF documents near the archive and page limits, several workers or
  concurrent documents, other Python versions, another allocator or kernel.
- **Known limitation.** When a cap is too small, the HTML parser's native allocation can fail
  inside the C library; the worker then reports `corrupt` (`SelectolaxError`) instead of
  `memory` (seen at 256 MB with a 16 Mchar page). The failure is still contained and clean, but
  its reason is misleading.

## Running

```bash
make test        # unit tests only
make test-all    # everything except perf, with coverage and the domain coverage gate (90 %)
make perf        # NFR-04 and the Phase 3 budgets, run before a phase is closed
make check       # lint, types, architecture, all tests
```

Permission-based tests are skipped when run as root (root ignores file modes).
