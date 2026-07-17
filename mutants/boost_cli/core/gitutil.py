"""Thin git wrapper (stdlib subprocess only)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from ..errors import BoostError


from mutmut.mutation.trampoline import wrap_in_trampoline as _mutmut_mutated, MutantDict
mutants_x_has_git__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_has_git__mutmut)
def has_git() -> bool:
    return shutil.which("git") is not None


def x_has_git__mutmut_orig() -> bool:
    return shutil.which("git") is not None


def x_has_git__mutmut_1() -> bool:
    return shutil.which(None) is not None


def x_has_git__mutmut_2() -> bool:
    return shutil.which("XXgitXX") is not None


def x_has_git__mutmut_3() -> bool:
    return shutil.which("GIT") is not None


def x_has_git__mutmut_4() -> bool:
    return shutil.which("git") is None

mutants_x_has_git__mutmut['_mutmut_orig'] = x_has_git__mutmut_orig # type: ignore # mutmut generated
mutants_x_has_git__mutmut['x_has_git__mutmut_1'] = x_has_git__mutmut_1 # type: ignore # mutmut generated
mutants_x_has_git__mutmut['x_has_git__mutmut_2'] = x_has_git__mutmut_2 # type: ignore # mutmut generated
mutants_x_has_git__mutmut['x_has_git__mutmut_3'] = x_has_git__mutmut_3 # type: ignore # mutmut generated
mutants_x_has_git__mutmut['x_has_git__mutmut_4'] = x_has_git__mutmut_4 # type: ignore # mutmut generated
mutants_x_run__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_run__mutmut)
def run(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_orig(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_1(args: List[str], cwd: Optional[Path] = None, check: bool = False,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_2(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 301) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_3(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_4(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError(None,
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_5(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint=None)
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_6(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError(hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_7(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        )
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_8(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("XXgit is required but was not found on PATHXX",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_9(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on path",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_10(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("GIT IS REQUIRED BUT WAS NOT FOUND ON PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_11(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="XXinstall git, e.g. `xcode-select --install` or `brew install git`XX")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_12(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="INSTALL GIT, E.G. `XCODE-SELECT --INSTALL` OR `BREW INSTALL GIT`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_13(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = None
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_14(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            None, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_15(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_16(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=None, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_17(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=None, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_18(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=None,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_19(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_20(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_21(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_22(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_23(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_24(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] - args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_25(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["XXgitXX"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_26(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["GIT"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_27(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(None) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_28(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=False, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_29(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_30(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError(None)
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_31(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" / (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_32(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("XXgit %s timed out after %dsXX" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_33(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("GIT %S TIMED OUT AFTER %DS" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_34(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[1], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_35(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check or proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_36(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode == 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_37(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 1:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_38(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = None
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_39(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout and "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_40(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr and proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_41(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "XXXX").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_42(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError(None)
    return proc


def x_run__mutmut_43(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" / (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_44(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("XXgit %s failed: %sXX" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_45(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("GIT %S FAILED: %S" % (args[0], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_46(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[1], detail[-1] if detail else "unknown error"))
    return proc


def x_run__mutmut_47(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[+1] if detail else "unknown error"))
    return proc


def x_run__mutmut_48(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-2] if detail else "unknown error"))
    return proc


def x_run__mutmut_49(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "XXunknown errorXX"))
    return proc


def x_run__mutmut_50(args: List[str], cwd: Optional[Path] = None, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    if not has_git():
        raise BoostError("git is required but was not found on PATH",
                        hint="install git, e.g. `xcode-select --install` or `brew install git`")
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=str(cwd) if cwd else None,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise BoostError("git %s timed out after %ds" % (args[0], timeout))
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise BoostError("git %s failed: %s" % (args[0], detail[-1] if detail else "UNKNOWN ERROR"))
    return proc

mutants_x_run__mutmut['_mutmut_orig'] = x_run__mutmut_orig # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_1'] = x_run__mutmut_1 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_2'] = x_run__mutmut_2 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_3'] = x_run__mutmut_3 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_4'] = x_run__mutmut_4 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_5'] = x_run__mutmut_5 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_6'] = x_run__mutmut_6 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_7'] = x_run__mutmut_7 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_8'] = x_run__mutmut_8 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_9'] = x_run__mutmut_9 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_10'] = x_run__mutmut_10 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_11'] = x_run__mutmut_11 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_12'] = x_run__mutmut_12 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_13'] = x_run__mutmut_13 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_14'] = x_run__mutmut_14 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_15'] = x_run__mutmut_15 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_16'] = x_run__mutmut_16 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_17'] = x_run__mutmut_17 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_18'] = x_run__mutmut_18 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_19'] = x_run__mutmut_19 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_20'] = x_run__mutmut_20 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_21'] = x_run__mutmut_21 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_22'] = x_run__mutmut_22 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_23'] = x_run__mutmut_23 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_24'] = x_run__mutmut_24 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_25'] = x_run__mutmut_25 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_26'] = x_run__mutmut_26 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_27'] = x_run__mutmut_27 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_28'] = x_run__mutmut_28 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_29'] = x_run__mutmut_29 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_30'] = x_run__mutmut_30 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_31'] = x_run__mutmut_31 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_32'] = x_run__mutmut_32 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_33'] = x_run__mutmut_33 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_34'] = x_run__mutmut_34 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_35'] = x_run__mutmut_35 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_36'] = x_run__mutmut_36 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_37'] = x_run__mutmut_37 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_38'] = x_run__mutmut_38 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_39'] = x_run__mutmut_39 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_40'] = x_run__mutmut_40 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_41'] = x_run__mutmut_41 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_42'] = x_run__mutmut_42 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_43'] = x_run__mutmut_43 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_44'] = x_run__mutmut_44 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_45'] = x_run__mutmut_45 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_46'] = x_run__mutmut_46 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_47'] = x_run__mutmut_47 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_48'] = x_run__mutmut_48 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_49'] = x_run__mutmut_49 # type: ignore # mutmut generated
mutants_x_run__mutmut['x_run__mutmut_50'] = x_run__mutmut_50 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_clone_shallow__mutmut)
def clone_shallow(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["clone", "--depth", "1", "--quiet", url, str(dest)], timeout=600)


def x_clone_shallow__mutmut_orig(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["clone", "--depth", "1", "--quiet", url, str(dest)], timeout=600)


def x_clone_shallow__mutmut_1(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=None, exist_ok=True)
    run(["clone", "--depth", "1", "--quiet", url, str(dest)], timeout=600)


def x_clone_shallow__mutmut_2(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=None)
    run(["clone", "--depth", "1", "--quiet", url, str(dest)], timeout=600)


def x_clone_shallow__mutmut_3(url: str, dest: Path) -> None:
    dest.parent.mkdir(exist_ok=True)
    run(["clone", "--depth", "1", "--quiet", url, str(dest)], timeout=600)


def x_clone_shallow__mutmut_4(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, )
    run(["clone", "--depth", "1", "--quiet", url, str(dest)], timeout=600)


def x_clone_shallow__mutmut_5(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=False, exist_ok=True)
    run(["clone", "--depth", "1", "--quiet", url, str(dest)], timeout=600)


def x_clone_shallow__mutmut_6(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=False)
    run(["clone", "--depth", "1", "--quiet", url, str(dest)], timeout=600)


def x_clone_shallow__mutmut_7(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(None, timeout=600)


def x_clone_shallow__mutmut_8(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["clone", "--depth", "1", "--quiet", url, str(dest)], timeout=None)


def x_clone_shallow__mutmut_9(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(timeout=600)


def x_clone_shallow__mutmut_10(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["clone", "--depth", "1", "--quiet", url, str(dest)], )


def x_clone_shallow__mutmut_11(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["XXcloneXX", "--depth", "1", "--quiet", url, str(dest)], timeout=600)


def x_clone_shallow__mutmut_12(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["CLONE", "--depth", "1", "--quiet", url, str(dest)], timeout=600)


def x_clone_shallow__mutmut_13(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["clone", "XX--depthXX", "1", "--quiet", url, str(dest)], timeout=600)


def x_clone_shallow__mutmut_14(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["clone", "--DEPTH", "1", "--quiet", url, str(dest)], timeout=600)


def x_clone_shallow__mutmut_15(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["clone", "--depth", "XX1XX", "--quiet", url, str(dest)], timeout=600)


def x_clone_shallow__mutmut_16(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["clone", "--depth", "1", "XX--quietXX", url, str(dest)], timeout=600)


def x_clone_shallow__mutmut_17(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["clone", "--depth", "1", "--QUIET", url, str(dest)], timeout=600)


def x_clone_shallow__mutmut_18(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["clone", "--depth", "1", "--quiet", url, str(None)], timeout=600)


def x_clone_shallow__mutmut_19(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["clone", "--depth", "1", "--quiet", url, str(dest)], timeout=601)

mutants_x_clone_shallow__mutmut['_mutmut_orig'] = x_clone_shallow__mutmut_orig # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_1'] = x_clone_shallow__mutmut_1 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_2'] = x_clone_shallow__mutmut_2 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_3'] = x_clone_shallow__mutmut_3 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_4'] = x_clone_shallow__mutmut_4 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_5'] = x_clone_shallow__mutmut_5 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_6'] = x_clone_shallow__mutmut_6 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_7'] = x_clone_shallow__mutmut_7 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_8'] = x_clone_shallow__mutmut_8 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_9'] = x_clone_shallow__mutmut_9 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_10'] = x_clone_shallow__mutmut_10 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_11'] = x_clone_shallow__mutmut_11 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_12'] = x_clone_shallow__mutmut_12 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_13'] = x_clone_shallow__mutmut_13 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_14'] = x_clone_shallow__mutmut_14 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_15'] = x_clone_shallow__mutmut_15 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_16'] = x_clone_shallow__mutmut_16 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_17'] = x_clone_shallow__mutmut_17 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_18'] = x_clone_shallow__mutmut_18 # type: ignore # mutmut generated
mutants_x_clone_shallow__mutmut['x_clone_shallow__mutmut_19'] = x_clone_shallow__mutmut_19 # type: ignore # mutmut generated
mutants_x_pull__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_pull__mutmut)
def pull(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_orig(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_1(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = None
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_2(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(None)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_3(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(None)
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_4(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["XX-CXX", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_5(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-c", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_6(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(None), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_7(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "XXfetchXX", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_8(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "FETCH", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_9(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "XX--depthXX", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_10(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--DEPTH", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_11(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "XX1XX", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_12(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "XX--quietXX", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_13(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--QUIET", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_14(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "XXoriginXX"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_15(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "ORIGIN"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_16(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(None, check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_17(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=None)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_18(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_19(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], )
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_20(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["XX-CXX", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_21(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-c", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_22(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(None), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_23(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "XXresetXX", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_24(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "RESET", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_25(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "XX--hardXX", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_26(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--HARD", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_27(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "XX--quietXX", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_28(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--QUIET", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_29(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "XXorigin/HEADXX"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_30(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/head"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_31(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "ORIGIN/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_32(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=True)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_33(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(None) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_34(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) != before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_35(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(None)
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_36(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["XX-CXX", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_37(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-c", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_38(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(None), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_39(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "XXresetXX", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_40(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "RESET", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_41(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "XX--hardXX", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_42(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--HARD", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_43(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "XX--quietXX", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_44(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--QUIET", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_45(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "XXFETCH_HEADXX"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_46(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "fetch_head"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_47(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = None
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_48(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(None)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_49(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "XXalready up to dateXX" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_50(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "ALREADY UP TO DATE" if before == after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_51(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before != after else "%s → %s" % (before[:7], after[:7])


def x_pull__mutmut_52(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" / (before[:7], after[:7])


def x_pull__mutmut_53(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "XX%s → %sXX" % (before[:7], after[:7])


def x_pull__mutmut_54(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%S → %S" % (before[:7], after[:7])


def x_pull__mutmut_55(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:8], after[:7])


def x_pull__mutmut_56(repo: Path) -> str:
    """Update a shallow clone. Returns a one-line summary."""
    before = head_commit(repo)
    run(["-C", str(repo), "fetch", "--depth", "1", "--quiet", "origin"])
    run(["-C", str(repo), "reset", "--hard", "--quiet", "origin/HEAD"], check=False)
    # origin/HEAD may be unset on old git; fall back to the fetched head
    if head_commit(repo) == before:
        run(["-C", str(repo), "reset", "--hard", "--quiet", "FETCH_HEAD"])
    after = head_commit(repo)
    return "already up to date" if before == after else "%s → %s" % (before[:7], after[:8])

mutants_x_pull__mutmut['_mutmut_orig'] = x_pull__mutmut_orig # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_1'] = x_pull__mutmut_1 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_2'] = x_pull__mutmut_2 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_3'] = x_pull__mutmut_3 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_4'] = x_pull__mutmut_4 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_5'] = x_pull__mutmut_5 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_6'] = x_pull__mutmut_6 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_7'] = x_pull__mutmut_7 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_8'] = x_pull__mutmut_8 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_9'] = x_pull__mutmut_9 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_10'] = x_pull__mutmut_10 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_11'] = x_pull__mutmut_11 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_12'] = x_pull__mutmut_12 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_13'] = x_pull__mutmut_13 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_14'] = x_pull__mutmut_14 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_15'] = x_pull__mutmut_15 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_16'] = x_pull__mutmut_16 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_17'] = x_pull__mutmut_17 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_18'] = x_pull__mutmut_18 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_19'] = x_pull__mutmut_19 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_20'] = x_pull__mutmut_20 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_21'] = x_pull__mutmut_21 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_22'] = x_pull__mutmut_22 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_23'] = x_pull__mutmut_23 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_24'] = x_pull__mutmut_24 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_25'] = x_pull__mutmut_25 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_26'] = x_pull__mutmut_26 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_27'] = x_pull__mutmut_27 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_28'] = x_pull__mutmut_28 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_29'] = x_pull__mutmut_29 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_30'] = x_pull__mutmut_30 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_31'] = x_pull__mutmut_31 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_32'] = x_pull__mutmut_32 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_33'] = x_pull__mutmut_33 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_34'] = x_pull__mutmut_34 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_35'] = x_pull__mutmut_35 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_36'] = x_pull__mutmut_36 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_37'] = x_pull__mutmut_37 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_38'] = x_pull__mutmut_38 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_39'] = x_pull__mutmut_39 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_40'] = x_pull__mutmut_40 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_41'] = x_pull__mutmut_41 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_42'] = x_pull__mutmut_42 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_43'] = x_pull__mutmut_43 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_44'] = x_pull__mutmut_44 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_45'] = x_pull__mutmut_45 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_46'] = x_pull__mutmut_46 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_47'] = x_pull__mutmut_47 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_48'] = x_pull__mutmut_48 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_49'] = x_pull__mutmut_49 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_50'] = x_pull__mutmut_50 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_51'] = x_pull__mutmut_51 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_52'] = x_pull__mutmut_52 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_53'] = x_pull__mutmut_53 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_54'] = x_pull__mutmut_54 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_55'] = x_pull__mutmut_55 # type: ignore # mutmut generated
mutants_x_pull__mutmut['x_pull__mutmut_56'] = x_pull__mutmut_56 # type: ignore # mutmut generated
mutants_x_head_commit__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_head_commit__mutmut)
def head_commit(repo: Path) -> str:
    proc = run(["-C", str(repo), "rev-parse", "HEAD"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_head_commit__mutmut_orig(repo: Path) -> str:
    proc = run(["-C", str(repo), "rev-parse", "HEAD"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_head_commit__mutmut_1(repo: Path) -> str:
    proc = None
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_head_commit__mutmut_2(repo: Path) -> str:
    proc = run(None, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_head_commit__mutmut_3(repo: Path) -> str:
    proc = run(["-C", str(repo), "rev-parse", "HEAD"], check=None)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_head_commit__mutmut_4(repo: Path) -> str:
    proc = run(check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_head_commit__mutmut_5(repo: Path) -> str:
    proc = run(["-C", str(repo), "rev-parse", "HEAD"], )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_head_commit__mutmut_6(repo: Path) -> str:
    proc = run(["XX-CXX", str(repo), "rev-parse", "HEAD"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_head_commit__mutmut_7(repo: Path) -> str:
    proc = run(["-c", str(repo), "rev-parse", "HEAD"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_head_commit__mutmut_8(repo: Path) -> str:
    proc = run(["-C", str(None), "rev-parse", "HEAD"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_head_commit__mutmut_9(repo: Path) -> str:
    proc = run(["-C", str(repo), "XXrev-parseXX", "HEAD"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_head_commit__mutmut_10(repo: Path) -> str:
    proc = run(["-C", str(repo), "REV-PARSE", "HEAD"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_head_commit__mutmut_11(repo: Path) -> str:
    proc = run(["-C", str(repo), "rev-parse", "XXHEADXX"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_head_commit__mutmut_12(repo: Path) -> str:
    proc = run(["-C", str(repo), "rev-parse", "head"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_head_commit__mutmut_13(repo: Path) -> str:
    proc = run(["-C", str(repo), "rev-parse", "HEAD"], check=True)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_head_commit__mutmut_14(repo: Path) -> str:
    proc = run(["-C", str(repo), "rev-parse", "HEAD"], check=False)
    return proc.stdout.strip() if proc.returncode != 0 else ""


def x_head_commit__mutmut_15(repo: Path) -> str:
    proc = run(["-C", str(repo), "rev-parse", "HEAD"], check=False)
    return proc.stdout.strip() if proc.returncode == 1 else ""


def x_head_commit__mutmut_16(repo: Path) -> str:
    proc = run(["-C", str(repo), "rev-parse", "HEAD"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else "XXXX"

mutants_x_head_commit__mutmut['_mutmut_orig'] = x_head_commit__mutmut_orig # type: ignore # mutmut generated
mutants_x_head_commit__mutmut['x_head_commit__mutmut_1'] = x_head_commit__mutmut_1 # type: ignore # mutmut generated
mutants_x_head_commit__mutmut['x_head_commit__mutmut_2'] = x_head_commit__mutmut_2 # type: ignore # mutmut generated
mutants_x_head_commit__mutmut['x_head_commit__mutmut_3'] = x_head_commit__mutmut_3 # type: ignore # mutmut generated
mutants_x_head_commit__mutmut['x_head_commit__mutmut_4'] = x_head_commit__mutmut_4 # type: ignore # mutmut generated
mutants_x_head_commit__mutmut['x_head_commit__mutmut_5'] = x_head_commit__mutmut_5 # type: ignore # mutmut generated
mutants_x_head_commit__mutmut['x_head_commit__mutmut_6'] = x_head_commit__mutmut_6 # type: ignore # mutmut generated
mutants_x_head_commit__mutmut['x_head_commit__mutmut_7'] = x_head_commit__mutmut_7 # type: ignore # mutmut generated
mutants_x_head_commit__mutmut['x_head_commit__mutmut_8'] = x_head_commit__mutmut_8 # type: ignore # mutmut generated
mutants_x_head_commit__mutmut['x_head_commit__mutmut_9'] = x_head_commit__mutmut_9 # type: ignore # mutmut generated
mutants_x_head_commit__mutmut['x_head_commit__mutmut_10'] = x_head_commit__mutmut_10 # type: ignore # mutmut generated
mutants_x_head_commit__mutmut['x_head_commit__mutmut_11'] = x_head_commit__mutmut_11 # type: ignore # mutmut generated
mutants_x_head_commit__mutmut['x_head_commit__mutmut_12'] = x_head_commit__mutmut_12 # type: ignore # mutmut generated
mutants_x_head_commit__mutmut['x_head_commit__mutmut_13'] = x_head_commit__mutmut_13 # type: ignore # mutmut generated
mutants_x_head_commit__mutmut['x_head_commit__mutmut_14'] = x_head_commit__mutmut_14 # type: ignore # mutmut generated
mutants_x_head_commit__mutmut['x_head_commit__mutmut_15'] = x_head_commit__mutmut_15 # type: ignore # mutmut generated
mutants_x_head_commit__mutmut['x_head_commit__mutmut_16'] = x_head_commit__mutmut_16 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_remote_url__mutmut)
def remote_url(repo: Path) -> str:
    proc = run(["-C", str(repo), "remote", "get-url", "origin"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_remote_url__mutmut_orig(repo: Path) -> str:
    proc = run(["-C", str(repo), "remote", "get-url", "origin"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_remote_url__mutmut_1(repo: Path) -> str:
    proc = None
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_remote_url__mutmut_2(repo: Path) -> str:
    proc = run(None, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_remote_url__mutmut_3(repo: Path) -> str:
    proc = run(["-C", str(repo), "remote", "get-url", "origin"], check=None)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_remote_url__mutmut_4(repo: Path) -> str:
    proc = run(check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_remote_url__mutmut_5(repo: Path) -> str:
    proc = run(["-C", str(repo), "remote", "get-url", "origin"], )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_remote_url__mutmut_6(repo: Path) -> str:
    proc = run(["XX-CXX", str(repo), "remote", "get-url", "origin"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_remote_url__mutmut_7(repo: Path) -> str:
    proc = run(["-c", str(repo), "remote", "get-url", "origin"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_remote_url__mutmut_8(repo: Path) -> str:
    proc = run(["-C", str(None), "remote", "get-url", "origin"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_remote_url__mutmut_9(repo: Path) -> str:
    proc = run(["-C", str(repo), "XXremoteXX", "get-url", "origin"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_remote_url__mutmut_10(repo: Path) -> str:
    proc = run(["-C", str(repo), "REMOTE", "get-url", "origin"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_remote_url__mutmut_11(repo: Path) -> str:
    proc = run(["-C", str(repo), "remote", "XXget-urlXX", "origin"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_remote_url__mutmut_12(repo: Path) -> str:
    proc = run(["-C", str(repo), "remote", "GET-URL", "origin"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_remote_url__mutmut_13(repo: Path) -> str:
    proc = run(["-C", str(repo), "remote", "get-url", "XXoriginXX"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_remote_url__mutmut_14(repo: Path) -> str:
    proc = run(["-C", str(repo), "remote", "get-url", "ORIGIN"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_remote_url__mutmut_15(repo: Path) -> str:
    proc = run(["-C", str(repo), "remote", "get-url", "origin"], check=True)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def x_remote_url__mutmut_16(repo: Path) -> str:
    proc = run(["-C", str(repo), "remote", "get-url", "origin"], check=False)
    return proc.stdout.strip() if proc.returncode != 0 else ""


def x_remote_url__mutmut_17(repo: Path) -> str:
    proc = run(["-C", str(repo), "remote", "get-url", "origin"], check=False)
    return proc.stdout.strip() if proc.returncode == 1 else ""


def x_remote_url__mutmut_18(repo: Path) -> str:
    proc = run(["-C", str(repo), "remote", "get-url", "origin"], check=False)
    return proc.stdout.strip() if proc.returncode == 0 else "XXXX"

mutants_x_remote_url__mutmut['_mutmut_orig'] = x_remote_url__mutmut_orig # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_1'] = x_remote_url__mutmut_1 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_2'] = x_remote_url__mutmut_2 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_3'] = x_remote_url__mutmut_3 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_4'] = x_remote_url__mutmut_4 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_5'] = x_remote_url__mutmut_5 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_6'] = x_remote_url__mutmut_6 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_7'] = x_remote_url__mutmut_7 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_8'] = x_remote_url__mutmut_8 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_9'] = x_remote_url__mutmut_9 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_10'] = x_remote_url__mutmut_10 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_11'] = x_remote_url__mutmut_11 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_12'] = x_remote_url__mutmut_12 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_13'] = x_remote_url__mutmut_13 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_14'] = x_remote_url__mutmut_14 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_15'] = x_remote_url__mutmut_15 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_16'] = x_remote_url__mutmut_16 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_17'] = x_remote_url__mutmut_17 # type: ignore # mutmut generated
mutants_x_remote_url__mutmut['x_remote_url__mutmut_18'] = x_remote_url__mutmut_18 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_log_for_path__mutmut)
def log_for_path(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--date=short", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_orig(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--date=short", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_1(repo: Path, rel_path: str = "XX.XX", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--date=short", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_2(repo: Path, rel_path: str = ".", n: int = 21) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--date=short", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_3(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = None
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_4(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(None, check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_5(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--date=short", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=None)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_6(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_7(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--date=short", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], )
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_8(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["XX-CXX", str(repo), "log", "--date=short", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_9(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-c", str(repo), "log", "--date=short", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_10(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(None), "log", "--date=short", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_11(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "XXlogXX", "--date=short", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_12(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "LOG", "--date=short", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_13(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "XX--date=shortXX", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_14(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--DATE=SHORT", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_15(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--date=short", "XX-nXX", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_16(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--date=short", "-N", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_17(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--date=short", "-n", str(None),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_18(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--date=short", "-n", str(n),
                "XX--pretty=format:%h  %ad  %an  %sXX", "--", rel_path], check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_19(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--date=short", "-n", str(n),
                "--PRETTY=FORMAT:%H  %AD  %AN  %S", "--", rel_path], check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_20(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--date=short", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "XX--XX", rel_path], check=False)
    return [l for l in proc.stdout.splitlines() if l.strip()]


def x_log_for_path__mutmut_21(repo: Path, rel_path: str = ".", n: int = 20) -> List[str]:
    """Formatted one-line log entries for a path inside a repo."""
    proc = run(["-C", str(repo), "log", "--date=short", "-n", str(n),
                "--pretty=format:%h  %ad  %an  %s", "--", rel_path], check=True)
    return [l for l in proc.stdout.splitlines() if l.strip()]

mutants_x_log_for_path__mutmut['_mutmut_orig'] = x_log_for_path__mutmut_orig # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_1'] = x_log_for_path__mutmut_1 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_2'] = x_log_for_path__mutmut_2 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_3'] = x_log_for_path__mutmut_3 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_4'] = x_log_for_path__mutmut_4 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_5'] = x_log_for_path__mutmut_5 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_6'] = x_log_for_path__mutmut_6 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_7'] = x_log_for_path__mutmut_7 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_8'] = x_log_for_path__mutmut_8 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_9'] = x_log_for_path__mutmut_9 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_10'] = x_log_for_path__mutmut_10 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_11'] = x_log_for_path__mutmut_11 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_12'] = x_log_for_path__mutmut_12 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_13'] = x_log_for_path__mutmut_13 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_14'] = x_log_for_path__mutmut_14 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_15'] = x_log_for_path__mutmut_15 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_16'] = x_log_for_path__mutmut_16 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_17'] = x_log_for_path__mutmut_17 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_18'] = x_log_for_path__mutmut_18 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_19'] = x_log_for_path__mutmut_19 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_20'] = x_log_for_path__mutmut_20 # type: ignore # mutmut generated
mutants_x_log_for_path__mutmut['x_log_for_path__mutmut_21'] = x_log_for_path__mutmut_21 # type: ignore # mutmut generated
mutants_x_is_repo__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_is_repo__mutmut)
def is_repo(path: Path) -> bool:
    return (Path(path) / ".git").exists()


def x_is_repo__mutmut_orig(path: Path) -> bool:
    return (Path(path) / ".git").exists()


def x_is_repo__mutmut_1(path: Path) -> bool:
    return (Path(path) * ".git").exists()


def x_is_repo__mutmut_2(path: Path) -> bool:
    return (Path(None) / ".git").exists()


def x_is_repo__mutmut_3(path: Path) -> bool:
    return (Path(path) / "XX.gitXX").exists()


def x_is_repo__mutmut_4(path: Path) -> bool:
    return (Path(path) / ".GIT").exists()

mutants_x_is_repo__mutmut['_mutmut_orig'] = x_is_repo__mutmut_orig # type: ignore # mutmut generated
mutants_x_is_repo__mutmut['x_is_repo__mutmut_1'] = x_is_repo__mutmut_1 # type: ignore # mutmut generated
mutants_x_is_repo__mutmut['x_is_repo__mutmut_2'] = x_is_repo__mutmut_2 # type: ignore # mutmut generated
mutants_x_is_repo__mutmut['x_is_repo__mutmut_3'] = x_is_repo__mutmut_3 # type: ignore # mutmut generated
mutants_x_is_repo__mutmut['x_is_repo__mutmut_4'] = x_is_repo__mutmut_4 # type: ignore # mutmut generated
