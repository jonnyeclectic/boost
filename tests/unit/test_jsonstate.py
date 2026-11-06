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


    def test_invalid_utf8_is_error_not_a_crash(self, tmp_path):
        # A decode failure is a ValueError, not an OSError or a
        # JSONDecodeError, so it sailed past both guards and took down every
        # command that reads config.json — `boost doctor` included.
        p = tmp_path / "f.json"
        p.write_bytes(b"\xff\xfe")
        data, err = jsonstate.read_object(p)
        assert data is None
        assert err.startswith(str(p) + ": not valid UTF-8 (")


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

    def test_invalid_utf8_is_corrupt(self, tmp_path):
        p = tmp_path / "f.json"
        p.write_bytes(b"\xff\xfe")
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


class TestByteOrderMark:
    """A UTF-8 BOM is what Windows editors save, not corruption."""

    def test_object_with_a_bom_parses(self, tmp_path):
        p = tmp_path / "f.json"
        p.write_bytes(b'\xef\xbb\xbf{"a": 1}')
        assert jsonstate.read_object(p) == ({"a": 1}, None)
        assert jsonstate.is_corrupt(p) is False

    def test_jsonc_object_with_a_bom_parses(self, tmp_path):
        p = tmp_path / "f.json"
        p.write_bytes(b'\xef\xbb\xbf{"a": 1} // c')
        assert jsonstate.read_object(p, jsonc=True) == ({"a": 1}, None)

    def test_list_with_a_bom_parses(self, tmp_path):
        p = tmp_path / "f.json"
        p.write_bytes(b'\xef\xbb\xbf[1]')
        assert jsonstate.read_list(p) == ([1], None)


class TestReadList:
    def test_missing_file_is_none_none(self, tmp_path):
        assert jsonstate.read_list(tmp_path / "nope.json") == (None, None)

    def test_valid_array_round_trips(self, tmp_path):
        p = tmp_path / "f.json"
        p.write_text('[{"a": 1}]', encoding="utf-8")
        assert jsonstate.read_list(p) == ([{"a": 1}], None)

    def test_empty_array_is_data_not_missing(self, tmp_path):
        p = tmp_path / "f.json"
        p.write_text("[]", encoding="utf-8")
        assert jsonstate.read_list(p) == ([], None)

    def test_invalid_json_is_error(self, tmp_path):
        p = tmp_path / "f.json"
        p.write_text("[{", encoding="utf-8")
        data, err = jsonstate.read_list(p)
        assert data is None
        assert err.startswith("%s: invalid JSON (" % p)

    def test_object_is_error(self, tmp_path):
        p = tmp_path / "f.json"
        p.write_text("{}", encoding="utf-8")
        assert jsonstate.read_list(p) == (
            None, "%s: expected a JSON array, found dict" % p)

    def test_non_utf8_is_error_not_a_crash(self, tmp_path):
        p = tmp_path / "f.json"
        p.write_bytes(b"[\xff\xfe]")
        data, err = jsonstate.read_list(p)
        assert data is None
        assert err.startswith("%s: not valid UTF-8 (" % p)

    def test_unreadable_path_is_error(self, tmp_path):
        p = tmp_path / "dir.json"
        p.mkdir()
        data, err = jsonstate.read_list(p)
        assert data is None
        assert err.startswith("%s: " % p)


class TestObjectMapError:
    def test_absent_key_is_fine(self):
        assert jsonstate.object_map_error({}, "skills") is None

    def test_map_of_objects_is_fine(self):
        assert jsonstate.object_map_error(
            {"skills": {"a": {}, "b": {"v": 1}}}, "skills") is None

    def test_empty_map_is_fine(self):
        assert jsonstate.object_map_error({"skills": {}}, "skills") is None

    def test_non_object_value_names_key_and_type(self):
        assert jsonstate.object_map_error({"skills": "x"}, "skills") == (
            "'skills' is a str, not an object")
        assert jsonstate.object_map_error({"skills": []}, "skills") == (
            "'skills' is a list, not an object")

    def test_non_object_record_names_the_record(self):
        assert jsonstate.object_map_error(
            {"skills": {"ok": {}, "a": "b"}}, "skills") == (
            "'skills' entry 'a' is a str, not an object")

    def test_only_the_named_key_is_checked(self):
        assert jsonstate.object_map_error(
            {"skills": {}, "rules": "x"}, "skills") is None
