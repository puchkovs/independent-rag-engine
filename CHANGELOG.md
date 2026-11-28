# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/); versions follow the phases of the
project until a release is cut.

## [Unreleased]

### Final audit and release hardening
- Retrieval baseline recomputed on `retrieval-hard@v2` and `retrieval-mini@v2` (dense, hybrid, lexical;
  hit@K, MRR, nDCG, recall, latency, memory), with a version 1 against version 2 comparison that
  attributes every movement to the corrected questions: `docs/BASELINE_V2.md`. No retrieval code or
  parameter changed. `retrieval_eval.py` now guards and counts reads of the test split and refuses
  to start without memory for the model; `rerank_bakeoff.py` has the same resource gate. Regression
  baselines for the hashing embedder on both v2 datasets.
- Datasets: `retrieval_hard_v2` and `retrieval_mini_v2` correct the labelling errors the audit found
  (root cause fixed in `build_hard_dataset.py`, which now refuses a dataset the audit finds wrong on
  its face); version 1 is frozen, the history is in `eval/datasets/CHANGES_v2.json`, nothing is
  marked reviewed. Audit after the fix: 170 correct, 15 doubtful, 0 incorrect.
- Preliminary automatic audit of evaluation questions (`eval/scripts/audit_questions.py`,
  `evaluation/question_audit.py`): correct / doubtful / incorrect, lexical and optional semantic
  layer; and a batch-review table in the review page with group accept and reject that act only on
  rows the person selected and opened. Nothing is marked reviewed and no dataset is changed.
- The database is larger than its target (5.6× the text without vectors against about 3×); the
  migration is planned after the first release (ADR 0022).
- Fix: a chunk with no word character (an ASCII table border, a rule) is no longer indexed. It used
  to stop the whole document from publishing (`E_INTEGRITY`, a dead job). Chunk coverage is unchanged.
- `eval/scripts/db_size.py` (size per table and column) and a harder `eval/scripts/soak.py`
  (`--workers`, `--churn-every`; file descriptors, threads, WAL and clean stop are criteria).
- `rag calibrate run|show|clear` (ADR 0021): the sufficiency gate is calibrated on the installation's
  own index with a cross-validated estimate, an optional independent holdout, and a record bound to
  the model, the retrieval setup and the decision rule. Answers, `rag doctor` and the API warn when
  the gate is open, stale or below its targets. Guide: `docs/CALIBRATION.md`.
- `docs/AUDIT.md` (every requirement and phase with a verdict and its evidence) and
  `docs/REQUIREMENTS.md`; `docs/LLM_VERIFICATION.md` (how to measure a real model).
- Security: the OpenAPI document is served behind the token like every other route.
- Gate: the reranker logit decides alone when it ran (ADR 0020). On a new independent held-out set
  it refuses 72.5 % of unanswerable questions at 4.2 % false refusals; dense alone 32.5 %. The 90 %
  target is still not met.
- Evaluation: `evaluation/llm_run.py` and `generation_eval.py` now report answer correctness,
  faithfulness, hallucination rate, citation precision and recall, the refusal matrix, latency and
  tokens, also for an OpenAI-compatible endpoint; a review kit (`eval/scripts/review_kit.py`) puts
  all 185 questions of the hard and mini sets on one page for the owner to decide on.
- Tooling: `rag.example.toml` documents every setting (a test checks it); CI actions are pinned by
  commit and Dependabot is configured; public text says "requirements" and "an AI language model".

### Phase 11: production readiness (implemented; a release has not been cut)
- Docker image (multi-stage, base image pinned by digest, dependencies installed from hashes, runs
  as an unprivileged user, health check, about 80 MB), a CI job that builds and smoke-tests it, and a
  packaging smoke test (wheel installs without extras, the API extra is optional).
- `rag verify BACKUP` and `rag restore BACKUP [--replace]`; the backup, verify, restore and doctor
  drill is a test. `docs/OPERATIONS.md` is the runbook.
- Optional Prometheus-format metrics at `GET /v1/metrics` (`[api] metrics`), size-rotated log files
  (`[logging] file`), `scripts/generate_notices.py` (third-party notices and a CycloneDX SBOM,
  checked in CI), a Markdown link checker, `SECURITY.md` with a threat model, `PROVENANCE.md`,
  `CONTRIBUTING.md`, and a rewritten README.
- `eval/scripts/soak.py`: a one-hour search soak behind a memory gate (result in `docs/TESTING.md`).
- Not done on purpose: a version tag, a GitHub release, a licence and the decision to publish are
  the owner's.

### Phase 10: evaluation (implemented; quality criteria are open)
- Statistics (McNemar, sign test, cluster bootstrap, Holm, kappa), generation metrics and a claim
  judge with calibration, a run manifest, a guarded and counted test split, `rag eval
  validate|run|report|compare|gate` and a committed regression baseline.
- A harder multilingual set (`retrieval-hard@v1`, all labels unreviewed). Held-out gate research:
  best 73.3 % correct refusals at 8.6 % false refusals against 90 % and 10 % (criterion open). The
  reranker gains nDCG@10 +0.16 (dense) and +0.37 (hybrid) on its dev split (still off by default);
  hybrid is worse than dense on this set (ADR 0018).

### Phase 9: HTTP API
- `rag serve`: FastAPI under `/v1` with health, readiness, statistics, sources, documents (cursor
  pagination, `Idempotency-Key`), jobs, search and answers (JSON or server-sent events),
  problem+json, bearer token, refusal to listen beyond the loopback without one, size limits, CORS
  off, a committed OpenAPI snapshot; `rag init`, `rag config`, `rag backup` (ADR 0017).

### Phase 8: query pipeline (MVP-1 implemented, not quality-accepted)
- `RagPipeline` with the statuses `answered`, `insufficient_evidence`, `unverified` and `error`,
  one time budget, verified streaming, cancellation and a measured release of in-process models;
  `rag ask` (exit codes 10 and 11) (ADR 0016).

### Phase 7: generation
- Prompt `answer.v1`, citation validation against the evidence of the request, refusal sentinel,
  degenerate-answer and truncation detection, resilient provider wrapper, Ollama and
  OpenAI-compatible adapters, a memory-gated smoke test that refused the 4B model on the reference
  machine (ADR 0015).

### Phase 6: reranking and context (implemented; the gate target is unmet)
- Reranker measured with the real `BAAI/bge-reranker-v2-m3-int8` (ADR 0014): on the saturated
  exploratory set it gives no gain (nDCG@10 −0.02 dense, −0.03 hybrid, intervals touching zero), the
  rerank stage takes 3.1 s at p50 and 4.1 s at p95 for a pool of 30 (limit 1.5 s) and the process
  peaks at 2.5 GiB, so it stays off by default. `eval/scripts/rerank_bakeoff.py` repeats the
  measurement; opt-in tests with the real weights run with `RAG_TEST_RERANK_DIR`.
- `OnnxCrossEncoder` (offline, files pinned by fingerprint, pairs over the window refused) and the
  `[rerank]` and `[context]` settings; `rag context QUERY` shows the evidence a question would get,
  the measured token budget (`window - system - question - max_new - margin`) and everything that
  was dropped, merged or cut, with `E_CONTEXT_BUDGET` (exit 7) and a hint when nothing fits.
  ADR 0014 keeps reranking off by default: no multilingual cross-encoder has been measured (the
  0.57 GB download awaits approval) and the current evaluation set is saturated.
- `SufficiencyGate` with `calibrate`: the best dense cosine (A) or reranker logit (B) must reach a
  threshold, either is enough; lexical coverage of the top passage (C) decides only when neither is
  available. Thresholds are fitted on dev to keep false refusals within 10 % while refusing as many
  unanswerable questions as possible, and are stored in `index_state.calibration` together with the
  embedding model id. A missing calibration, one made for another model, or no signal lets the
  question through and says why. `rag doctor --integrity` now prints warnings, including a stale
  calibration. First exploratory result: with E5-small the dense cosine does not separate
  answerable from unanswerable questions well enough (83 % correct refusals at 4.5 % false ones on
  dev, target 90 %); see `docs/RETRIEVAL_EVALUATION.md`.
- System prompt `rag-system/1` (`context/prompt.py`): evidence-only answers, `[E<n>]` citations, one
  exact refusal sentence, answer in the question's language. Its SHA-256 is pinned and a test caps its
  measured size (217 tokens with the conservative counter, limit 260), so any change to the prompt
  or its cost is a visible decision.
- `ContextBuilder` turns ranked hits into numbered evidence (`E1..En`) inside a measured token
  budget (`window - system - question - max_new - margin`, margin `max(256, 10 %)`): exact
  duplicates are dropped, overlapping chunks of one version are folded into their exact union, a
  document may take at most three places, optional small-to-big replaces a leaf by its section, and
  the order is by score or by document. A top hit that cannot fit is cut at a sentence end and
  flagged `truncated`; if the required evidence cannot fit the build fails with `E_CONTEXT_BUDGET`
  and a hint. Every retrieved chunk ends up shown, merged into a named neighbour, or dropped with a
  reason (`duplicate`, `budget`, `doc_cap`, `overlap`, `missing`) in the `ContextReport`, together
  with the token use and a context hash. Evidence keeps the provenance a citation needs (document,
  version, source key, heading path, pages, character span, the hits it stands for). A property
  test runs 1000 random corpora, budgets and policies and checks that nothing is lost silently.
- `Reranker` contract tests and `FakeReranker`; `RerankStage` runs a reranker under a time and pool
  budget and can never fail a search: an error, a timeout, a model still busy with a timed-out call
  or output that is not a reordering of the input keeps the fused order and reports
  `rerank_skipped:<reason>`. The service reranks a pool larger than `top_k` (default 30) and returns
  `top_k` with the raw reranker score in `HitScores.rerank`. `rag search --rerank/--no-rerank`;
  without a configured reranker `--rerank` is a noted fallback. `ChunkContentReader` port with a
  SQLite reader returns text, position and provenance of any chunk.

### Phase 5: retrieval (implemented; labels await review)
- Review tooling for evaluation datasets: `eval/scripts/review_sheet.py export` writes a CSV with the
  question, gold quote with its surrounding text, reference answer and an empty decision column;
  `apply` records `accept`, `edit` or `reject` decisions under a named person and writes a new file.
  A reviewer whose name looks like a program is refused, an empty decision stays unreviewed and an
  unclear one is an error. How to review is in `docs/DATASET_REVIEW.md`.
- `eval/scripts/benchmark_search.py`: end-to-end search latency over a real published index.
  Hybrid p95 is 30.2 ms at 10⁴ chunks and 281.6 ms at 10⁵ (query embedding excluded), peak 85 and
  280 MiB; Phase 5 acceptance criteria and their evidence are tabulated in `docs/TESTING.md`.
- Evaluation: dataset schema v2 with a strict parser and validator (verbatim anchors, absence terms,
  question-type rules, split policy over shared gold documents, reviewer checks, metric
  eligibility), `retrieval_mini_v1` (18 original documents, 44 English and Russian questions, all
  unreviewed), a scoring runner (document- and chunk-level metrics, bootstrap summaries by type and
  language, paired comparison, saturation and anecdotal flags) and `eval/scripts/retrieval_eval.py`,
  which drives the real ingest and search. First exploratory result: dense and hybrid saturate the
  set, lexical is lower. ADR 0013 keeps `dense` as the default; see `docs/RETRIEVAL_EVALUATION.md`.
- `rag search QUERY`: dense, lexical or hybrid retrieval over the published index with metadata
  filters (`--source`, `--path-prefix`, `--path-glob`, `--tag`, `--tag-all`, `--language`, `--kind`,
  `--modified-after/-before`, `--doc-id`, `--exclude-doc-id`), `--top-k`, `--candidate-k`, `--full`,
  `--debug` (counts, per-hit channel ranks, timings) and `--json`. It opens the database read-only
  and writes nothing; bad input is a user error (exit 2) with `E_QUERY_INVALID` or
  `E_FILTER_INVALID`. New `[retrieval]` settings section (default mode `dense`, `top_k = 8`,
  `candidate_k = 40`, RRF `k = 60`).
- `RetrievalService`: one deterministic pipeline over ports: query processing, metadata prefilter,
  dense and lexical channels (`candidate_k` each), fusion, duplicate collapsing and the document
  cap, then `top_k` hits with every score component and per-channel rank in the diagnostics. The
  model's query prefix is applied once by the service. A filter that matches nothing, an index
  without a published model and a silent channel are reported as fallbacks, not errors; a query
  model that differs from the index model is `E_EMBED_MODEL_MISMATCH`.
- `diversify`: exact repeats of a text (`text_hash`) collapse to their first occurrence across
  documents, and `max_per_document` caps how many places one document may take; rank order is kept.
  The outcome reports collapsed, capped and unknown counts and the share of unique documents.
- `QueryProcessor`: NFC, control characters to spaces, invisible format characters dropped,
  whitespace collapsed, a character cap before tokenising and a token limit (a query over it is
  refused, never truncated), and script-based language detection with an optional hint. New error
  code `E_QUERY_INVALID` (category `user`, exit code 2) for blank, unusable or over-long queries.
- `rag_engine.retrieval.fusion`: reciprocal rank fusion (`k = 60`, dense weight 1.0, lexical
  weight 0.5 as starting values) and min-max weighted-score fusion of the dense and lexical
  channels. Every component (raw scores, per-channel ranks) is kept; ties are broken by chunk id,
  so the order depends only on the inputs. A chunk absent from a channel adds nothing for it.
- Metadata filters (`RetrievalFilters`) resolve to the set of searchable chunks through
  parameterised SQL (`storage/filters.py`, port `ChunkFilter`): sources, case-sensitive path
  prefix, path glob (the source-policy grammar, now `domain/globs.py`), tags any/all, chunk
  language and kind, modification window, document include/exclude. There is no raw SQL: values
  are bound parameters, lists are capped at 1000 values, a malformed glob is `E_FILTER_INVALID`.
  Only indexed, non-duplicate chunks of active documents' current versions can match. A
  `ChunkCatalog` port gives chunk identity and text hash for diversity and result building.
- `rag_engine.evaluation`: Recall@k, Precision@k, hit rate (coverage), reciprocal rank and graded
  nDCG@k for one ranking, and seeded percentile bootstrap intervals, plain and paired over queries.
  Values are checked against hand-computed rankings; the same seed reproduces an interval exactly.

### Phase 4: embeddings and storage (complete)
- Decision D-03 closed ([ADR 0012](docs/adr/0012-embedding-default-evaluation.md)): the default
  embedding model is `intfloat/multilingual-e5-small` through ONNX, chosen by an explicit rule
  (resource gate, paired quality interval, tie-breaks). Evidence in `docs/EMBEDDING_BAKEOFF.md`: NoMIRACL judged-pool ranking in
  English and Russian with paired bootstrap intervals, uncached latency, throughput and memory of
  E5-small and Qwen3 0.6B, exact dense search at 10k and 100k vectors, and the memory of loading a
  real 100k-vector index (peak 276 MiB). Qwen3 4B quality could not be measured on the 7.8 GiB
  development machine and is recorded as such. Scripts: `eval/scripts/bakeoff_nomiracl.py`,
  `bakeoff_report.py`, `benchmark_dense.py`, `benchmark_refresh.py`.
- Phase 4 acceptance criteria and their evidence are tabulated in `docs/TESTING.md`.
- Acceptance tests for Phase 4 failure paths: sixteen injected corruptions that `doctor
  --integrity` must report (and never repair), every fencing guard of the atomic publisher,
  damaged stored vectors and model metadata at index load, indexing-handler refusals, Ollama
  response and connection errors, and the exact token counter. Total coverage rose from 93 % to
  94 %; `integrity.py` 79 → 96 %, `publishing.py` 81 → 97 %, `vector_flat.py` 83 → 98 %.
- ONNX embeddings support the pinned `intfloat/multilingual-e5-small` snapshot offline (384
  dimensions, 512 tokens, `query: ` / `passage: ` prefixes, mean pooling). The adapter counts
  tokens with the model's own `tokenizer.json`, special tokens included, and refuses an input over
  the window with `E_RESOURCE_GATE` instead of letting the inference library truncate it. Inference
  runs in-process (`parallel=None`) so a second concurrent call is still refused, not queued.
  Opt-in tests with the real weights run with `RAG_TEST_E5_DIR` set (marker `external`).
- `rag doctor --integrity` checks the read-only SQLite snapshot, foreign keys, model identity,
  vector shape and norm, current versions, chunk provenance, FTS consistency and index generation.
- Replaced-version chunks lose their indexed flag when unpublished. Embedding GC retains vectors
  referenced by any retained chunk and removes orphan cache entries after version data is purged.
- NFR-05 checks actual re-embedding after one paragraph edit in a 100-plus-chunk document;
  model-based random operations and failure injection exercise integrity and rollback.

### Phase 3: parsing and chunking (complete)
- Domain: `Block.attrs`, UTC check for `ParsedDocument.created`, `detect_language`,
  `check_block_provenance`, `check_duplicate_graph`; ADR 0008 defines the contracts.
- Ports: `ParseLimits`, `ParseHints.encoding/limits`, `Parser.normalizer_version`; domain
  `ParseReason` and `parse_failed`; settings sections `[parsing]` and `[chunking]`.
- Parsing: idempotent text normalisation (prose and code modes), exactly-once entity decoding,
  validated per-source cleaners that version the normaliser, and `TextAssembler`, which builds
  `normalized_text`, block offsets and heading paths together.
- Plain-text parser (declared or detected encoding, blank-line paragraphs, empty documents) and a
  shared `Parser` contract suite.
- Markdown parser: headings (ATX and setext), paragraphs, nested list items, quotes, fenced and
  indented code, tables, raw HTML blocks reduced to text, front-matter metadata (title, author,
  date) read without a YAML library; entities decoded once. Dependencies: `markdown-it-py`,
  `selectolax`.
- HTML parser: main-content selection, page furniture and hidden elements removed, headings,
  paragraphs, nested lists, tables, code and quotes, title, author and date from the page head.
- Token counting: `HeuristicTokenCounter` (script-aware, at least one token per word, errs on the
  high side) and `HfTokenCounter` for a local `tokenizer.json` (optional extra `tokenizers`).
- `DocumentProcessor`: size-limited reading, format identification from content, parser
  selection, provenance of a version (parser, normaliser, MIME decision, content hash) and
  clean failures (`E_PARSE_FAILED` with a reason, `E_UNSUPPORTED_FORMAT`); parser registry.
- Text splitting for the chunkers: sentences (Russian and English abbreviations, initials,
  decimals, list markers, ellipsis), words, lines and size-bounded hard splits that never separate
  a combining mark from its letter; every function reassembles its input exactly.
- Chunking core: a packer that joins sentences, lines and word groups up to the target size,
  repeats the tail of the previous prose chunk as overlap (never around tables or code), merges a
  too-small last chunk and guarantees `max_tokens` by recursive halving; a chunk assembler that
  builds identified, language-tagged chunks as exact slices of the normalised text and marks
  repeated leaf text as a non-indexed duplicate.
- `fixed` and `recursive` chunkers with a shared `Chunker` contract suite (bounds, coverage,
  provenance, determinism, overlap, duplicates, random documents).
- `structure_aware` chunker: sections cut at headings, tiny sections merged while they fit the
  target, headings without text joined to the section they introduce, a parent chunk (level 1)
  for every heading-led group with two or more leaves; the heading belongs to the parent, or to
  the leaf when the group has one leaf. Shares the `Chunker` contract suite.
- `ChunkerRegistry` and the `ChunkerSelector` port: `auto` picks `structure_aware` for documents
  with headings, `recursive` for several blocks and `fixed` for a single block; `[chunking]
  strategy` forces one. `DocumentProcessor.process` parses and chunks a file and reports the
  chunker, its version and its fingerprint; each stage is logged without document text.
- `corpus_mini` fixtures: sixteen original Russian, English and mixed documents (Markdown, HTML,
  plain text, a cp1251 file, tiny sections, empty headings, tables, code) produced by a
  deterministic generator, with a corpus test that checks parser and strategy choice, the chunk
  invariants under two policies, determinism, language, heading paths and parents.
- `rag chunks DOC`: parses and chunks a file (or, with `--source`, a document of a registered
  source with that source's cleaners) and prints the chunks as text or `--json`; `--cleaner`,
  `--strategy` and `--full` options; no database is needed for a plain file. `rag source add
  --cleaner` stores validated line cleaners with the source; `SourceRegistry.open` reads a
  document through its source; the container builds counter, limits, strategy and parsers from
  `[parsing]` and `[chunking]` (`Processing`).
- Architecture contracts: `parsing` and `chunking` join the independent adapter row and may not
  import storage, configuration, ingestion, the network or each other; negative tests run the
  project's own configuration against planted violations.
- PDF parser (optional extra `pdf`, `pypdf`): text layer to page-numbered paragraphs; lines joined
  by layout heuristics, hyphenated line ends and ligatures repaired, running titles and page
  numbers removed, title, author and date from the file; password-protected files
  (`encrypted`), scans (`no_text_layer`), damaged files, page, text and block limits and a time
  limit end as `E_PARSE_FAILED` with a reason. Source cleaners run on the original lines. A
  test helper builds PDFs without fixtures or network; two PDF reports join `corpus_mini`.
- DOCX parser (optional extra `docx`, `python-docx`): headings (a Title puts the Heading styles
  one level below it), paragraphs, nested list items, quotes and code from styles, tables as
  rows of cells, tracked insertions kept and deletions and text boxes left out, title, author and
  date from the file. The archive is checked first (entries, uncompressed size, compression
  ratio); password-protected files and damaged archives end as `E_PARSE_FAILED` with a reason.
  Test builders create DOCX files; two handbooks join `corpus_mini` (byte-identical on
  regeneration).
- Parser isolation: PDF, DOCX and HTML are parsed in a long-lived worker process by default
  (`[parsing] isolate`). The worker starts with a minimal environment, a data-segment cap
  (`isolation_memory_mb`) and no core dumps; messages are length-prefixed JSON, never pickle. A
  hang is killed at the time limit (`timeout`), exhausted memory ends as `memory`, a crash as
  `worker_failed`; the next document starts a fresh worker, which is also replaced every 200
  documents. Results equal those of in-process parsing (tested for the real parsers).
- `duplicate_of`: after ingestion changes are applied, in the same transaction, documents of one
  source with identical raw content are linked to the active one with the smallest
  `DocumentId` (no chains; links follow additions, changes, renames, disappearances and
  restorations; non-active documents hold none). `rag ingest` reports the links it updated. The
  integrity checks verify the graph exactly, and the model-based test now creates copies.
- Hardening: a golden snapshot of how every `corpus_mini` document is parsed and chunked (with an
  update script), property tests of parse-then-chunk for generated Markdown, HTML and text under
  random size policies, and mutation fuzzing of every corpus file through the whole pipeline,
  including equality of isolated and in-process outcomes.
- Performance budgets (`make perf`): token counting, parsing and chunking of 1 MB Markdown, HTML
  and text, a 100-page PDF, a 2000-paragraph DOCX, the isolated worker and peak memory, with
  three measured runs recorded in `docs/TESTING.md`.
- `eval/scripts/chunk_grid.py`: reports how a corpus is chunked at target sizes 192, 256 and 384
  tokens (chunk and section counts, token distribution, small and near-limit shares, overlap,
  duplicates, time) as Markdown or JSON. It describes shapes only and ranks nothing.
- `corpus_mini` gains a service-line and repeated-disclaimer document; the fixtures are excluded
  from the formatter so they stay byte-identical to the generator's output.
- Memory estimate corrected: memory is measured per million characters, with the Python-level
  peak, the resident-set growth and the worker cap kept apart; a conservative budget (15 MB per
  million characters, and 250 MB plus 14 MB per million characters for the worker) and the
  limits of the measurement are in `docs/TESTING.md` and ADR 0008.

### Phase 2 refinements
- Schema v2 (`0002_align_data_model.sql`, forward only; `0001` untouched): `document_versions`,
  `normalized_text`, `UNIQUE (document_id, content_hash)`, no `pending` status. Documents
  without a version are `active` and not searchable until their first commit. Phase 4's
  migration becomes v3.
- Automatic verified backup before migrating a populated database; foreign-key-safe table
  rebuilds in the migration runner; the schema version is mirrored from `schema_migrations`.
- Mass-delete guard: `max(10, 20 %)` plus `empty_scan` and `all_known_gone`; the flag is
  `--accept-mass-delete` (`--allow-mass-delete` is removed).
- CLI exit codes follow the error category.
- Retry delays have jitter; retry and lease parameters are `[ingest]` settings.
- MIME detection on `filetype` and `charset-normalizer` (cp1251, koi8-r, cp866, UTF-16 with BOM);
  the encoding is stored with the job.
- Ingestion emits structured stage events (numbers only).
- Composition root moved to `rag_engine/container.py` (new entry point); storage split into
  `core.py`, `uow.py`, `backup.py`; tests reorganised into `perf`, `chaos`, `integrity`; PR CI
  excludes `perf`.
- New tests: `SIGKILL` at every stage, invariants at teardown, a model-based ingestion test.
- ADRs 0005-0007; ADR 0004 refined.

## Phase 2: SQLite core and document ingestion

### Added
- SQLite store: WAL, single writer lock (`E_STORE_LOCKED`), unit of work with rollback,
  read-only opening, verified `VACUUM INTO` backup.
- Numbered, checksummed SQL migrations; schema v1 (sources, documents, versions, sync state,
  jobs, index state).
- `FilesystemSource` with include/exclude globs, symlink policy, root boundary, NFC keys.
- Change detection (size/mtime first, SHA-256 only when needed), content-based MIME detection.
- Source identity, explicit rebase, content-proven move detection.
- Tombstones with a per-source grace period, garbage collection and the mass-delete guard
  (`E_MASS_DELETE_GUARD`).
- Persistent job queue: idempotent enqueue, leases, heartbeats, exponential backoff, dead
  letters, crash recovery.
- `rag source add|list|rebase`, `rag ingest [--dry-run]`, `rag status` (Typer), JSON output and
  stable exit codes.
- Domain: `SyncState`, `IngestionJob`, `IndexMetadata`, `JobId`, `DocumentStatus.PENDING`;
  `SourceRevision` moved into the domain.
- Documentation: data model, testing guide; ADR 0004 accepted with amendments.

### Changed
- The Phase 1 `Store` port is replaced by `MetadataReader`, `MetadataWriter`, `UnitOfWork`
  and `Store`; `SourceAdapter` gained `scan`.
- The command line is built with Typer instead of `argparse`.
- Import contracts: `ingestion` sits above the adapters and may not import them.

### Not included
Parsing, chunking, embeddings, indexes, retrieval, generation, API (later phases).

## [0.0.1] - Phase 1: core foundation
Domain model, error taxonomy, ports, configuration, logging, test doubles, CI.
