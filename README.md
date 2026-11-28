# Independent RAG Engine

Modular, local-first RAG engine for reliable knowledge retrieval, evidence-grounded
generation, and reproducible evaluation.

> **Status: functionally complete, quality not yet accepted.** Ingestion, hybrid retrieval,
> reranking, context assembly, cited answers with refusals, a command line, an HTTP API,
> an evaluation toolbox, backup and restore and a Docker image all exist and are tested without
> any model or network. What is **not** established: the sufficiency gate refuses 73 % of
> unanswerable questions on held-out (unreviewed) data against a 90 % target; no language model has
> been run through the pipeline on this project's reference machine, so faithfulness, hallucination
> rate and answer latency are unmeasured; and the evaluation labels have not been reviewed by a
> person. [docs/TESTING.md](docs/TESTING.md) lists every criterion with its evidence and every one
> that is open. Licensed under the [MIT licence](LICENSE).

## What it does

Point it at folders of Markdown, HTML, text, PDF or DOCX files. It parses and chunks them,
embeds the chunks (a local ONNX model or Ollama), and keeps everything in one SQLite file. Then:

- `rag search` returns ranked passages (dense, lexical or hybrid, with filters) with their source,
  heading and position;
- `rag ask` answers from those passages, **cites them**, and says so when the documents do not
  contain the answer; a citation that does not point at evidence the model was given is rejected,
  and text whose citations fail is withheld;
- `rag serve` exposes the same through an HTTP API with OpenAPI, tokens and server-sent events.

## Design goals

- **Local-first.** A laptop-class CPU is enough; SQLite is the system of record.
- **Modular monolith, hexagonal.** A pure domain, `Protocol` ports, and replaceable adapters.
  Boundaries are enforced in CI.
- **Deterministic.** Identifiers, chunking and tests are reproducible; non-determinism is
  confined to model providers.
- **Explicit failures.** One error taxonomy with stable codes; nothing is truncated or
  skipped silently.
- **Safe by default.** Document text, prompts and secrets are never written to logs;
  secrets are read from environment variables only.
- **Testable without models or network.** Deterministic fakes ship in `rag_engine.testing`.

## Requirements

- Python `>=3.12,<3.14`
- [uv](https://docs.astral.sh/uv/)

## Supported documents

Markdown, HTML and plain text work out of the box. Optional formats are separate extras:

| Format | Extra | Notes |
|---|---|---|
| PDF | `uv sync --extra pdf` | text layer only; a scan without text is refused (`no_text_layer`) |
| DOCX | `uv sync --extra docx` | headings, lists, tables, quotes and code from styles; password-protected files are refused |
| exact token counting | `uv sync --extra tokenizers` | counts with a local `tokenizer.json` |
| ONNX embeddings | `uv sync --extra onnx` | in-process, offline; the recommended default model is `intfloat/multilingual-e5-small` ([ADR 0012](docs/adr/0012-embedding-default-evaluation.md)) |

## Quick start

```bash
git clone https://github.com/puchkovs/independent-rag-engine.git
cd independent-rag-engine
uv sync --frozen --extra api
uv run rag --version
make check          # lint, types, architecture, tests (no models, no network)

uv run rag init --dir ~/rag-workspace         # a starter rag.toml and a data directory
$EDITOR ~/rag-workspace/rag.toml              # enable [embedding] and, for answers, [llm]
uv run rag --config ~/rag-workspace/rag.toml config check
```

With an embedding model configured ([below](#embedding-model)) and, for answers, a language model
(`[llm]`, for example Ollama with an explicit `context_window`):

```bash
uv run rag source add notes ~/Documents/notes
uv run rag ingest notes
uv run rag search "how are chunks stored"
uv run rag calibrate run questions.jsonl     # teach the gate your documents; see docs/CALIBRATION.md
uv run rag ask "How long are database backups kept?" --sources
RAG_API_TOKEN="$(openssl rand -hex 24)" uv run rag serve        # http://127.0.0.1:8765/v1
```

Or in a container (the image is about 80 MB and needs a token): see [docs/OPERATIONS.md](docs/OPERATIONS.md).

Register a folder and preview parsing and chunking. With embedding enabled in the
configuration, `rag ingest` processes the queue and publishes each complete version;
without it, jobs remain queued.

```bash
uv run rag source add notes ~/Documents/notes
uv run rag ingest --dry-run
uv run rag ingest
uv run rag status
uv run rag chunks ~/Documents/notes/guide.md
uv run rag index gc                 # purge old versions and unused embeddings
uv run rag index rebuild --lexical  # rebuild FTS5 in one transaction
uv run rag doctor --integrity        # inspect SQLite, published FTS and vectors read-only
uv run rag search "how are chunks stored" --mode hybrid --top-k 5
uv run rag search "ZX4471" --mode lexical --source notes --path-glob '**/*.md' --json
# after changing the configured embedding model:
uv run rag index switch-model      # stage every visible vector, then activate atomically
uv run python eval/scripts/chunk_grid.py   # chunk shapes at 192/256/384 tokens; ranks nothing
```

### Embedding model

Embedding is off until configured; nothing is downloaded automatically. The recommended default
is `intfloat/multilingual-e5-small` (MIT, 384 dimensions, 512-token window) run offline through
ONNX Runtime; [ADR 0012](docs/adr/0012-embedding-default-evaluation.md) records the measurements
behind that choice and its limits. Provision the model files yourself, set `provider = "onnx"` and
`model_dir`, and pin `revision` to the fingerprint of the directory (see `rag.example.toml`).
Ollama models remain supported when the machine can host them.

The local development environment used for Phase 4 measurements occupied 368 MB on disk
(including optional dependencies and development tools, excluding model weights). Install size
depends on selected extras and platform.

## Repository layout

```
src/rag_engine/
  domain/          identifiers, models, invariants, error taxonomy   (pure, no I/O)
  ports/           Protocol contracts: sources, parsing, chunking, embeddings, storage,
                   indexes, reranking, LLM, tokens, clock
  ingestion/       filesystem source, change detection, identity, lifecycle, duplicates, job
                   queue, MIME, document processing (parse and chunk)
  parsing/         normaliser, cleaners, parsers (md, html, txt, pdf, docx), isolated worker
  chunking/        token counters, splitting, packing, the fixed, recursive and
                   structure-aware chunkers
  retrieval/       query processing, fusion, diversity, the sufficiency gate and the search service
  context/         the token budget and the numbered evidence handed to the model
  generation/      the prompt, the model call, citation checks, refusal and resilience
  llm/             Ollama and OpenAI-compatible chat adapters
  pipeline/        the query pipeline: stages, time budget and the four answer statuses
  api/             the HTTP API (extra `api`)
  evaluation/      metrics, statistics, judge, run protocol, datasets and the regression gate
  storage/         SQLite store (WAL, single writer, unit of work) and SQL migrations
  lexical/         RU/EN Snowball analyzer shared by publication and FTS queries
  system/          real clock and identifier entropy
  config/          validated settings and resource profiles
  observability/   structured logging, request correlation, timing
  testing/         deterministic fakes (embedder, LLM, clock, in-memory source)
  cli/             the `rag` command (receives its collaborators, no infrastructure)
  container.py     composition root and entry point
tests/             unit, contract, architecture, integration, e2e, chaos, integrity and perf tests
docs/              architecture and development notes
eval/scripts/      reproducible reports (chunk grid, bake-offs, gate research, soak, smoke)
eval/corpus/       the public corpora of the evaluations (mini and hard)
baselines/         runs kept as regression references
eval/datasets/     versioned question sets
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Data model](docs/DATA_MODEL.md)
- [Development guide](docs/DEVELOPMENT.md) and [contributing](CONTRIBUTING.md)
- [HTTP API](docs/API.md) ([OpenAPI](docs/openapi.json)) and [command line](docs/CLI.md)
- [Operations: Docker, backup and restore, logs, metrics](docs/OPERATIONS.md)
- [Evaluation protocol](docs/EVALUATION.md)
- [Security policy and threat model](SECURITY.md)
- [Provenance of the code, data and models](PROVENANCE.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md) and [SBOM](sbom.cdx.json)
- [Testing](docs/TESTING.md)
- [Phase 4 embedding measurements](docs/EMBEDDING_BAKEOFF.md)
- [Retrieval evaluation](docs/RETRIEVAL_EVALUATION.md)
- [Retrieval baseline on dataset version 2](docs/BASELINE_V2.md)
- [Reviewing an evaluation dataset](docs/DATASET_REVIEW.md)
- [Calibrating the sufficiency gate](docs/CALIBRATION.md)
- [Verifying a real language model](docs/LLM_VERIFICATION.md)
- [Requirements and audit](docs/REQUIREMENTS.md)
- [Changelog](CHANGELOG.md)
- [Architecture decision records](docs/adr/README.md)

## Configuration

Settings come from an optional TOML file and `RAG_*` environment variables
(`RAG_LLM__CONTEXT_WINDOW=8192`); environment values win. See
[`rag.example.toml`](rag.example.toml). Secrets are referenced by the *name* of an
environment variable (`api_key_env`) and never stored in files.
