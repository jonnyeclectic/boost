# Copyright the boost contributors.
# SPDX-License-Identifier: GPL-3.0-only
"""An unwritable store must fail with an explanation, not a traceback.

Two of the three crash reports on a real machine were the same thing: a
sandboxed run where ``~/.agents/skills`` could not be written, and
``tempfile.mkdtemp`` raised ``PermissionError`` straight out of
:func:`store._copy_skill`. boost printed a stack trace ending in a temp path
nobody recognises, and wrote a crash report, for what is an ordinary
permissions problem the user can fix.
"""
from __future__ import annotations

import pytest

from boost_cli.core import store
from boost_cli.errors import BoostError


class TestCopySkillPermissionError:
    def _blow_up(self, monkeypatch, exc):
        def boom(*a, **k):
            raise exc
        monkeypatch.setattr(store.tempfile, "mkdtemp", boom)

    def test_permission_error_becomes_a_boost_error(self, monkeypatch, sandbox, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        dest = store.skill_store_dir("x")
        self._blow_up(monkeypatch, PermissionError(1, "Operation not permitted"))
        with pytest.raises(BoostError) as ei:
            store._copy_skill(src, dest)
        # It must name the directory that could not be written — that is the
        # whole content of the fix. A message that only says "permission
        # denied" leaves the reader where the traceback did.
        assert str(dest.parent) in (ei.value.message + (ei.value.hint or ""))

    def test_the_message_is_actionable(self, monkeypatch, sandbox, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        self._blow_up(monkeypatch, PermissionError(1, "Operation not permitted"))
        with pytest.raises(BoostError) as ei:
            store._copy_skill(src, store.skill_store_dir("x"))
        assert ei.value.hint, "a permissions failure the user can fix deserves a hint"

    def test_oserror_that_is_not_permission_still_surfaces(self, monkeypatch,
                                                           sandbox, tmp_path):
        # Don't over-catch: a disk-full or read-only-fs error is a different
        # problem and must not be described as a permissions one.
        src = tmp_path / "src"
        src.mkdir()
        (src / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        self._blow_up(monkeypatch, OSError(28, "No space left on device"))
        with pytest.raises(BoostError) as ei:
            store._copy_skill(src, store.skill_store_dir("x"))
        assert "No space left on device" in (ei.value.message + (ei.value.hint or ""))
