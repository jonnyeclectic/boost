# Copyright the boost contributors.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests: boost_cli/core/jsonstate.py — corrupt-JSON read/quarantine."""
from __future__ import annotations

from boost_cli.core import jsonstate


class TestReadObject:
    def test_missing_file_is_none_none(self, tmp_path):
        data, err = jsonstate.read_object(tmp_path / "nope.json")
        assert data is None
        assert err is None

    def test_valid_object_round_trips(self, tmp_path):
        p = tmp_path / "f.json"
        p.write_text('{"a": 1}', encoding="utf-8")
        data, err = jsonstate.read_object(p)
        assert data == {"a": 1}
        assert err is None

    def test_invalid_json_is_error(self, tmp_path):
        p = tmp_path / "f.json"
        p.write_text("{not json!!", encoding="utf-8")
        data, err = jsonstate.read_object(p)
        assert data is None
        assert str(p) in err
        assert "invalid JSON" in err

    def test_valid_json_non_object_is_error(self, tmp_path):
        p = tmp_path / "f.json"
        p.write_text("[1, 2, 3]", encoding="utf-8")
        data, err = jsonstate.read_object(p)
        assert data is None
        assert "expected a JSON object" in err
        assert "list" in err

    def test_json_scalar_is_error(self, tmp_path):
        p = tmp_path / "f.json"
        p.write_text("42", encoding="utf-8")
        data, err = jsonstate.read_object(p)
        assert data is None
        assert "expected a JSON object" in err

    def test_unreadable_path_is_error(self, tmp_path):
        # A directory "exists" but can't be read as text — OSError branch,
        # reachable without needing actual filesystem permission tricks
        # (this container runs as root, where chmod 0 reads anyway).
        p = tmp_path / "adir.json"
        p.mkdir()
        data, err = jsonstate.read_object(p)
        assert data is None
        assert str(p) in err


class TestIsCorrupt:
    def test_missing_file_is_not_corrupt(self, tmp_path):
        assert jsonstate.is_corrupt(tmp_path / "nope.json") is False

    def test_valid_file_is_not_corrupt(self, tmp_path):
        p = tmp_path / "f.json"
        p.write_text("{}", encoding="utf-8")
        assert jsonstate.is_corrupt(p) is False

    def test_invalid_json_is_corrupt(self, tmp_path):
        p = tmp_path / "f.json"
        p.write_text("not json", encoding="utf-8")
        assert jsonstate.is_corrupt(p) is True


class TestQuarantine:
    def test_moves_file_aside(self, tmp_path):
        p = tmp_path / "f.json"
        p.write_text("bad", encoding="utf-8")
        dest = jsonstate.quarantine(p)
        assert dest == tmp_path / "f.json.corrupt"
        assert not p.exists()
        assert dest.read_text(encoding="utf-8") == "bad"

    def test_repeated_corruption_never_overwrites_prior_quarantine(self, tmp_path):
        p = tmp_path / "f.json"
        p.write_text("first bad", encoding="utf-8")
        first = jsonstate.quarantine(p)

        p.write_text("second bad", encoding="utf-8")
        second = jsonstate.quarantine(p)

        assert first != second
        assert first.read_text(encoding="utf-8") == "first bad"
        assert second.read_text(encoding="utf-8") == "second bad"

    def test_third_quarantine_picks_next_free_name(self, tmp_path):
        p = tmp_path / "f.json"
        for i, body in enumerate(["one", "two", "three"], start=1):
            p.write_text(body, encoding="utf-8")
            dest = jsonstate.quarantine(p)
            if i == 1:
                assert dest.name == "f.json.corrupt"
            else:
                assert dest.name == "f.json.corrupt.%d" % i
