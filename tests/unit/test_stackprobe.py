# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests: boost_cli/core/stackprobe.py — the shared tech-stack prober."""
from __future__ import annotations

import json

from boost_cli.core import stackprobe as sp


def _write(root, rel, text=""):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


class TestDetectStack:
    def test_empty_dir_is_empty(self, tmp_path):
        assert sp.detect_stack(tmp_path) == {
            "languages": [], "frameworks": [], "keywords": []}

    def test_python_with_frameworks(self, tmp_path):
        _write(tmp_path, "pyproject.toml", "django\nfastapi\n")
        stack = sp.detect_stack(tmp_path)
        assert stack["languages"] == ["python"]
        assert stack["frameworks"] == ["django", "fastapi"]
        assert "python" in stack["keywords"] and "django" in stack["keywords"]

    def test_requirements_txt_also_python(self, tmp_path):
        _write(tmp_path, "requirements.txt", "flask==2.0\n")
        stack = sp.detect_stack(tmp_path)
        assert stack["languages"] == ["python"]
        assert stack["frameworks"] == ["flask"]

    def test_package_json_deps_frameworks_and_typescript(self, tmp_path):
        _write(tmp_path, "package.json", json.dumps({
            "dependencies": {"react": "18", "@next/font": "1"},
            "devDependencies": {"typescript": "5"}}))
        stack = sp.detect_stack(tmp_path)
        assert "javascript" in stack["languages"]
        assert "typescript" in stack["languages"]
        assert "react" in stack["frameworks"]
        assert "next" in stack["frameworks"]      # matched via "@next/font"

    def test_package_json_invalid_still_javascript(self, tmp_path):
        _write(tmp_path, "package.json", "{not valid json")
        stack = sp.detect_stack(tmp_path)
        assert stack["languages"] == ["javascript"]
        assert stack["frameworks"] == []

    def test_package_json_non_dict_is_ignored(self, tmp_path):
        _write(tmp_path, "package.json", "[1, 2, 3]")
        stack = sp.detect_stack(tmp_path)
        assert stack["languages"] == ["javascript"]
        assert stack["frameworks"] == []

    def test_go_rust_java_ruby_markers(self, tmp_path):
        _write(tmp_path, "go.mod", "module x\n")
        _write(tmp_path, "Cargo.toml", "[package]\n")
        _write(tmp_path, "pom.xml", "<project>org.springframework</project>")
        _write(tmp_path, "Gemfile", "gem 'rails'\n")
        stack = sp.detect_stack(tmp_path)
        assert set(stack["languages"]) == {"go", "rust", "java", "ruby"}
        assert set(stack["frameworks"]) == {"spring", "rails"}

    def test_docker_ci_terraform_extras(self, tmp_path):
        _write(tmp_path, "Dockerfile", "FROM scratch\n")
        _write(tmp_path, "a.tf", "resource {}\n")
        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        stack = sp.detect_stack(tmp_path)
        assert "docker" in stack["keywords"]
        assert "ci" in stack["keywords"]
        assert "terraform" in stack["keywords"]
        # extras are keyword-only, never languages/frameworks
        assert stack["languages"] == []
        assert stack["frameworks"] == []

    def test_extension_count_threshold(self, tmp_path):
        # one .py file is not enough (needs >= 2) without a manifest
        _write(tmp_path, "only.py", "pass\n")
        assert sp.detect_stack(tmp_path)["languages"] == []
        _write(tmp_path, "second.py", "pass\n")
        assert sp.detect_stack(tmp_path)["languages"] == ["python"]

    def test_tsconfig_marks_typescript(self, tmp_path):
        _write(tmp_path, "tsconfig.json", "{}")
        assert "typescript" in sp.detect_stack(tmp_path)["languages"]

    def test_skips_vendored_dirs(self, tmp_path):
        # a Cargo.toml buried in node_modules must not count as rust
        _write(tmp_path, "node_modules/dep/Cargo.toml", "[package]\n")
        assert sp.detect_stack(tmp_path)["languages"] == []

    def test_stops_descending_past_two_levels(self, tmp_path):
        # a marker three dirs deep (a/b/c/) is never descended into
        _write(tmp_path, "a/b/c/go.mod", "module deep\n")
        assert "go" not in sp.detect_stack(tmp_path)["languages"]
        # a marker one dir deep (a/) is within the walk horizon
        _write(tmp_path, "a/go.mod", "module shallow\n")
        assert "go" in sp.detect_stack(tmp_path)["languages"]

    def test_keywords_union_languages_frameworks_extras_sorted(self, tmp_path):
        _write(tmp_path, "pyproject.toml", "pytest\n")
        _write(tmp_path, "Dockerfile", "FROM scratch\n")
        stack = sp.detect_stack(tmp_path)
        assert stack["keywords"] == sorted(stack["keywords"])
        assert set(stack["keywords"]) == {"python", "pytest", "docker"}


class TestReadText:
    def test_reads_utf8(self, tmp_path):
        p = _write(tmp_path, "f.txt", "héllo")
        assert sp._read_text(p) == "héllo"

    def test_missing_file_returns_empty(self, tmp_path):
        assert sp._read_text(tmp_path / "nope.txt") == ""
