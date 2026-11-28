"""``rag eval``: validate, run, report, compare and gate against the committed baseline."""

from __future__ import annotations

import asyncio
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

from rag_engine.cli.main import main as _main
from rag_engine.container import DefaultContainer
from rag_engine.testing import HashingEmbedder

pytestmark = pytest.mark.e2e

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "eval" / "datasets" / "retrieval_mini_v1.json"
BASELINE = ROOT / "baselines" / "mini_hashing_dev_v1.json"
DIGEST = "c" * 64


def main(args: list[str]) -> int:
    return _main(args, container=DefaultContainer())


def build_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corpus_name: str) -> list[str]:
    embedder = HashingEmbedder(32)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "test", "digest": DIGEST}]})
        texts = json.loads(request.content)["input"]
        with ThreadPoolExecutor(max_workers=1) as pool:
            vectors = pool.submit(asyncio.run, embedder.embed_documents(texts)).result()
        return httpx.Response(200, json={"embeddings": vectors.tolist()})

    real = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient",
        lambda **kw: real(base_url=kw["base_url"], transport=httpx.MockTransport(handler)),
    )  # fmt: skip
    monkeypatch.chdir(tmp_path)  # the test-access counter lives under ./eval_runs
    corpus = tmp_path / "corpus"
    shutil.copytree(ROOT / "eval" / "corpus" / corpus_name, corpus)
    config = tmp_path / "rag.toml"
    config.write_text(
        '[parsing]\nisolate = []\n[embedding]\nenabled = true\nprovider = "ollama"\n'
        f'model = "test"\nrevision = "{DIGEST}"\ndimension = 32\nbase_url = "http://test"\n'
    )
    prefix = ["--config", str(config), "--db", str(tmp_path / "rag.db")]
    assert main([*prefix, "source", "add", "corpus", str(corpus)]) == 0
    assert main([*prefix, "ingest", "corpus", "--json"]) == 0
    return prefix


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    return build_workspace(tmp_path, monkeypatch, "mini_v1")


def run(prefix: list[str], out: Path, *extra: str) -> int:
    args = ["eval", "run", "--dataset", str(DATASET), "--include-unreviewed", "--output", str(out)]
    return main([*prefix, *args, *extra])


def test_the_dataset_validates_and_reports_that_nothing_is_reviewed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    capsys.readouterr()
    assert main(["eval", "validate", str(DATASET), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] and data["questions"] == 44 and data["reviewed"] == 0


def test_a_run_with_the_committed_embedder_setup_passes_the_regression_gate(
    workspace: list[str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "run.json"
    assert run(workspace, out, "--split", "dev", "--mode", "hybrid") == 0
    capsys.readouterr()
    assert main(["eval", "gate", str(out), str(BASELINE)]) == 0
    assert "no regression" in capsys.readouterr().out
    data = json.loads(out.read_text())
    assert data["flags"]["exploratory"] is True and data["manifest"]["embedding_model"]
    assert data["manifest"]["dataset_hash"] and data["manifest"]["corpus_hash"]


@pytest.mark.parametrize(
    ("corpus", "dataset", "baseline", "questions"),
    [
        ("mini_v1", "retrieval_mini_v2.json", "mini_hashing_dev_v2.json", 44),
        ("hard_v1", "retrieval_hard_v2.json", "hard_hashing_dev_v2.json", 141),
    ],
)
def test_the_version_2_datasets_pass_their_own_baselines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    corpus: str,
    dataset: str,
    baseline: str,
    questions: int,
) -> None:
    prefix = build_workspace(tmp_path, monkeypatch, corpus)
    path = ROOT / "eval" / "datasets" / dataset
    out = tmp_path / "run.json"
    args = ["eval", "run", "--dataset", str(path), "--include-unreviewed", "--output", str(out)]
    assert main([*prefix, *args, "--split", "dev", "--mode", "hybrid"]) == 0
    capsys.readouterr()
    assert main(["eval", "gate", str(out), str(ROOT / "baselines" / baseline)]) == 0
    assert "no regression" in capsys.readouterr().out
    assert main(["eval", "validate", str(path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["questions"] == questions


def test_a_change_that_makes_retrieval_worse_fails_the_gate_with_its_own_exit_code(
    workspace: list[str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "shallow.json"
    assert run(workspace, out, "--split", "dev", "--mode", "hybrid", "--top-k", "1") == 0
    capsys.readouterr()
    assert main(["eval", "gate", str(out), str(BASELINE), "--json"]) == 12
    result = json.loads(capsys.readouterr().out)
    assert result["passed"] is False and {v["metric"] for v in result["violations"]}


def test_the_test_split_is_guarded_and_counted(
    workspace: list[str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "test.json"
    capsys.readouterr()
    assert run(workspace, out, "--split", "test") == 2  # refused without --final
    assert "--final" in capsys.readouterr().err and not out.exists()
    assert run(workspace, out, "--split", "test", "--final") == 0
    assert json.loads(out.read_text())["flags"]["held_out"] is True
    assert run(workspace, out, "--split", "test", "--final") == 0
    again = json.loads(out.read_text())["flags"]
    assert again["test_reads"] == 2 and again["held_out"] is False
    report = main(["eval", "report", str(out)])
    assert report == 0 and "NOT held out" in capsys.readouterr().out


def test_report_and_compare_print_markdown_and_json(
    workspace: list[str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    deep, shallow = tmp_path / "deep.json", tmp_path / "shallow.json"
    assert run(workspace, deep, "--mode", "hybrid") == 0
    assert run(workspace, shallow, "--mode", "hybrid", "--top-k", "1") == 0
    capsys.readouterr()
    assert main(["eval", "report", str(deep)]) == 0
    text = capsys.readouterr().out
    assert "EXPLORATORY" in text and "| all | hit@1 |" in text
    assert main(["eval", "compare", str(deep), str(shallow), "--json"]) == 0
    rows = {r["metric"]: r for r in json.loads(capsys.readouterr().out)}
    assert rows["hit@10"]["mean_diff"] > 0 and rows["hit@1"]["mean_diff"] == 0
    assert main(["eval", "compare", str(deep), str(deep)]) == 0
    assert "no evidence of a difference" in capsys.readouterr().out


def test_a_run_without_an_index_or_questions_explains_itself(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "rag.toml"
    config.write_text("[parsing]\nisolate = []\n")
    prefix = ["--config", str(config), "--db", str(tmp_path / "none.db")]
    capsys.readouterr()
    assert (
        main(
            [
                *prefix,
                "eval",
                "run",
                "--dataset",
                str(DATASET),
                "--output",
                str(tmp_path / "x.json"),
            ]
        )
        == 2
    )
    assert "reviewed" in capsys.readouterr().err  # nothing is reviewed: needs --include-unreviewed
    assert run(prefix, tmp_path / "x.json") == 4
