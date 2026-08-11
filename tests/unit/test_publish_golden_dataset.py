"""Unit tests: the LangSmith golden-set publisher, which had none.

``evals/publish_golden_dataset.py`` is the "observe" leg of boost's LangChain
integration — it mirrors ``tests/eval/golden.jsonl`` into a LangSmith dataset so
online evals grade against the same ground truth the offline Tier-1 gate floors.
It is deliberately outside the required gate (a required check that depends on a
SaaS account fails when someone else's billing lapses), and the cost of that is
that **nothing exercised it at all**: no test imported it, so every path
including the argument parsing was unverified.

It cannot be tested against the real service, and should not be. What *is*
testable is everything the network never sees, which is where the bugs a reader
would actually hit live:

* the two opt-in guards return cleanly rather than tracebacking, which is the
  documented contract for a surface that must degrade when unconfigured;
* the golden file parses the way the offline gate parses it — comments and
  blanks dropped — because a publisher that silently disagrees with the gate
  about which rows count would publish a dataset that grades differently while
  claiming to be the same ground truth;
* every row becomes exactly one example with the query as input and the
  judgments as output.

The client is a stub. That is not a shortcut around the interesting part: the
interesting part is the mapping from a golden row to an example, and a stub is
what makes it observable.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "evals" / "publish_golden_dataset.py"
GOLDEN = ROOT / "tests" / "eval" / "golden.jsonl"

pytestmark = pytest.mark.skipif(
    not SCRIPT.exists(), reason="evals/ not reachable (e.g. mutation sandbox)")


def load_publisher():
    """Import the script by path, the way this repo tests scripts/."""
    spec = importlib.util.spec_from_file_location("publish_golden_dataset",
                                                  SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


MOD = load_publisher()


class TestLoadGolden:
    """The parse must agree with the gate's, or the two grade different sets."""

    def test_comments_and_blanks_are_dropped(self, tmp_path):
        path = tmp_path / "g.jsonl"
        path.write_text(
            '# a comment\n\n{"query": "q1", "relevant": ["a"]}\n'
            '   \n{"query": "q2", "relevant": ["b"]}\n', encoding="utf-8")
        assert [r["query"] for r in MOD.load_golden(path)] == ["q1", "q2"]

    def test_the_real_golden_set_parses(self):
        rows = MOD.load_golden(GOLDEN)
        assert rows, "the shipped golden set parsed as empty"
        assert all("query" in r for r in rows)

    def test_it_agrees_with_the_gate_on_how_many_rows_there_are(self):
        # THE POINT of testing the parser at all. The offline gate and this
        # publisher both read golden.jsonl; if they disagree about which lines
        # count, the LangSmith dataset silently grades a different set while
        # claiming to be the same ground truth.
        expected = sum(
            1 for line in GOLDEN.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#"))
        assert len(MOD.load_golden(GOLDEN)) == expected


class TestItDegradesWhenUnconfigured:
    """Both guards are documented as "message, not traceback". Pin that."""

    def test_a_missing_key_returns_nonzero_without_raising(self, monkeypatch,
                                                           capsys):
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        assert MOD.main(["--golden", str(GOLDEN)]) == 1
        assert "LANGSMITH_API_KEY" in capsys.readouterr().err

    def test_a_missing_package_returns_nonzero_without_raising(self, monkeypatch,
                                                              capsys):
        monkeypatch.setenv("LANGSMITH_API_KEY", "not-a-real-key")
        monkeypatch.setitem(__import__("sys").modules, "langsmith", None)
        assert MOD.main(["--golden", str(GOLDEN)]) == 1
        assert "langsmith" in capsys.readouterr().err

    def test_the_key_check_happens_before_any_client_is_built(self, monkeypatch):
        # Ordering, not politeness: reaching a Client() constructor without a
        # key is how an opt-in surface turns into a traceback on a machine that
        # simply never opted in.
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        built = []
        monkeypatch.setitem(__import__("sys").modules, "langsmith",
                            _fake_langsmith(built))
        MOD.main(["--golden", str(GOLDEN)])
        assert built == []


class _FakeDataset:
    def __init__(self, ident="ds-1"):
        self.id = ident


class _FakeClient:
    """Enough of langsmith.Client to observe what would be sent."""

    def __init__(self, existing=False, calls=None):
        self.calls = calls if calls is not None else []
        self._existing = existing
        self.created_examples = []
        self.deleted = []

    def has_dataset(self, dataset_name):
        self.calls.append(("has_dataset", dataset_name))
        return self._existing

    def read_dataset(self, dataset_name):
        self.calls.append(("read_dataset", dataset_name))
        return _FakeDataset()

    def create_dataset(self, dataset_name, description=""):
        self.calls.append(("create_dataset", dataset_name))
        return _FakeDataset()

    def list_examples(self, dataset_id):
        self.calls.append(("list_examples", dataset_id))
        return [_FakeDataset("ex-1"), _FakeDataset("ex-2")]

    def delete_example(self, example_id):
        self.deleted.append(example_id)

    def create_examples(self, dataset_id, examples):
        self.calls.append(("create_examples", dataset_id))
        self.created_examples = examples


def _fake_langsmith(built, existing=False, box=None):
    """A stand-in ``langsmith`` module whose Client records what it was asked."""
    import types
    mod = types.ModuleType("langsmith")

    def _client(*a, **k):
        client = _FakeClient(existing=existing)
        built.append(client)
        if box is not None:
            box.append(client)
        return client

    mod.Client = _client
    return mod


def _run(monkeypatch, tmp_path, rows, existing=False):
    """Publish ``rows`` through a stub client; return that client."""
    path = tmp_path / "g.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    monkeypatch.setenv("LANGSMITH_API_KEY", "not-a-real-key")
    built: list = []
    monkeypatch.setitem(__import__("sys").modules, "langsmith",
                        _fake_langsmith(built, existing=existing))
    rc = MOD.main(["--golden", str(path), "--name", "test-set"])
    assert rc == 0
    assert built, "no client was constructed"
    return built[0]


ROWS = [{"query": "how do I review code", "relevant": ["code-review"],
         "kind": "skill", "note": "n1"},
        {"query": "commit conventions", "relevant": ["conventional-commits"],
         "kind": "rule", "note": ""}]


class TestEveryRowBecomesAnExample:
    def test_one_example_per_row(self, monkeypatch, tmp_path):
        client = _run(monkeypatch, tmp_path, ROWS)
        assert len(client.created_examples) == len(ROWS)

    def test_the_query_is_the_input(self, monkeypatch, tmp_path):
        client = _run(monkeypatch, tmp_path, ROWS)
        assert [e["inputs"]["query"] for e in client.created_examples] == \
            [r["query"] for r in ROWS]

    def test_the_judgments_are_the_output(self, monkeypatch, tmp_path):
        # This is the ground truth an online eval grades against; losing it
        # would leave a dataset of questions with no answers, which still
        # publishes cleanly.
        client = _run(monkeypatch, tmp_path, ROWS)
        assert client.created_examples[0]["outputs"]["relevant"] == \
            ["code-review"]
        assert client.created_examples[0]["outputs"]["kind"] == "skill"

    def test_a_row_missing_optional_fields_still_publishes(self, monkeypatch,
                                                          tmp_path):
        # golden.jsonl's optional keys are optional in the gate too.
        client = _run(monkeypatch, tmp_path, [{"query": "bare"}])
        example = client.created_examples[0]
        assert example["outputs"]["relevant"] == []
        assert example["metadata"]["note"] == ""


class TestItMirrorsRatherThanAccretes:
    """Re-running must leave the dataset equal to the file, not appended to."""

    def test_a_new_dataset_is_created_when_absent(self, monkeypatch, tmp_path):
        client = _run(monkeypatch, tmp_path, ROWS, existing=False)
        assert ("create_dataset", "test-set") in client.calls

    def test_existing_examples_are_deleted_before_the_new_ones_land(
            self, monkeypatch, tmp_path):
        # Without this, publishing twice doubles every example and the dataset
        # quietly stops matching the file it claims to mirror.
        client = _run(monkeypatch, tmp_path, ROWS, existing=True)
        assert client.deleted, "no existing examples were removed"
        assert ("create_dataset", "test-set") not in client.calls
