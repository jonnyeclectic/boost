"""Terminal output helpers — colors, symbols, tables.

Conventions used across all commands:
  ok("copied to ...")    ->  "  ✓ copied to ..."           (green check)
  warn("...")            ->  "  ! ..."                     (yellow)
  err("...")             ->  "Error: ..." on stderr        (red)
  info("...")            ->  plain indented line
  heading("...")         ->  bold section header
"""
from __future__ import annotations

import os
import sys

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"


from mutmut.mutation.trampoline import wrap_in_trampoline as _mutmut_mutated, MutantDict
mutants_x_use_color__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_use_color__mutmut)
def use_color(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CLICOLOR_FORCE"):
        return True
    stream = stream or sys.stdout
    return hasattr(stream, "isatty") and stream.isatty()


def x_use_color__mutmut_orig(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CLICOLOR_FORCE"):
        return True
    stream = stream or sys.stdout
    return hasattr(stream, "isatty") and stream.isatty()


def x_use_color__mutmut_1(stream=None) -> bool:
    if os.environ.get(None):
        return False
    if os.environ.get("CLICOLOR_FORCE"):
        return True
    stream = stream or sys.stdout
    return hasattr(stream, "isatty") and stream.isatty()


def x_use_color__mutmut_2(stream=None) -> bool:
    if os.environ.get("XXNO_COLORXX"):
        return False
    if os.environ.get("CLICOLOR_FORCE"):
        return True
    stream = stream or sys.stdout
    return hasattr(stream, "isatty") and stream.isatty()


def x_use_color__mutmut_3(stream=None) -> bool:
    if os.environ.get("no_color"):
        return False
    if os.environ.get("CLICOLOR_FORCE"):
        return True
    stream = stream or sys.stdout
    return hasattr(stream, "isatty") and stream.isatty()


def x_use_color__mutmut_4(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return True
    if os.environ.get("CLICOLOR_FORCE"):
        return True
    stream = stream or sys.stdout
    return hasattr(stream, "isatty") and stream.isatty()


def x_use_color__mutmut_5(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get(None):
        return True
    stream = stream or sys.stdout
    return hasattr(stream, "isatty") and stream.isatty()


def x_use_color__mutmut_6(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("XXCLICOLOR_FORCEXX"):
        return True
    stream = stream or sys.stdout
    return hasattr(stream, "isatty") and stream.isatty()


def x_use_color__mutmut_7(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("clicolor_force"):
        return True
    stream = stream or sys.stdout
    return hasattr(stream, "isatty") and stream.isatty()


def x_use_color__mutmut_8(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CLICOLOR_FORCE"):
        return False
    stream = stream or sys.stdout
    return hasattr(stream, "isatty") and stream.isatty()


def x_use_color__mutmut_9(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CLICOLOR_FORCE"):
        return True
    stream = None
    return hasattr(stream, "isatty") and stream.isatty()


def x_use_color__mutmut_10(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CLICOLOR_FORCE"):
        return True
    stream = stream and sys.stdout
    return hasattr(stream, "isatty") and stream.isatty()


def x_use_color__mutmut_11(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CLICOLOR_FORCE"):
        return True
    stream = stream or sys.stdout
    return hasattr(stream, "isatty") or stream.isatty()


def x_use_color__mutmut_12(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CLICOLOR_FORCE"):
        return True
    stream = stream or sys.stdout
    return hasattr(None, "isatty") and stream.isatty()


def x_use_color__mutmut_13(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CLICOLOR_FORCE"):
        return True
    stream = stream or sys.stdout
    return hasattr(stream, None) and stream.isatty()


def x_use_color__mutmut_14(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CLICOLOR_FORCE"):
        return True
    stream = stream or sys.stdout
    return hasattr("isatty") and stream.isatty()


def x_use_color__mutmut_15(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CLICOLOR_FORCE"):
        return True
    stream = stream or sys.stdout
    return hasattr(stream, ) and stream.isatty()


def x_use_color__mutmut_16(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CLICOLOR_FORCE"):
        return True
    stream = stream or sys.stdout
    return hasattr(stream, "XXisattyXX") and stream.isatty()


def x_use_color__mutmut_17(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CLICOLOR_FORCE"):
        return True
    stream = stream or sys.stdout
    return hasattr(stream, "ISATTY") and stream.isatty()

mutants_x_use_color__mutmut['_mutmut_orig'] = x_use_color__mutmut_orig # type: ignore # mutmut generated
mutants_x_use_color__mutmut['x_use_color__mutmut_1'] = x_use_color__mutmut_1 # type: ignore # mutmut generated
mutants_x_use_color__mutmut['x_use_color__mutmut_2'] = x_use_color__mutmut_2 # type: ignore # mutmut generated
mutants_x_use_color__mutmut['x_use_color__mutmut_3'] = x_use_color__mutmut_3 # type: ignore # mutmut generated
mutants_x_use_color__mutmut['x_use_color__mutmut_4'] = x_use_color__mutmut_4 # type: ignore # mutmut generated
mutants_x_use_color__mutmut['x_use_color__mutmut_5'] = x_use_color__mutmut_5 # type: ignore # mutmut generated
mutants_x_use_color__mutmut['x_use_color__mutmut_6'] = x_use_color__mutmut_6 # type: ignore # mutmut generated
mutants_x_use_color__mutmut['x_use_color__mutmut_7'] = x_use_color__mutmut_7 # type: ignore # mutmut generated
mutants_x_use_color__mutmut['x_use_color__mutmut_8'] = x_use_color__mutmut_8 # type: ignore # mutmut generated
mutants_x_use_color__mutmut['x_use_color__mutmut_9'] = x_use_color__mutmut_9 # type: ignore # mutmut generated
mutants_x_use_color__mutmut['x_use_color__mutmut_10'] = x_use_color__mutmut_10 # type: ignore # mutmut generated
mutants_x_use_color__mutmut['x_use_color__mutmut_11'] = x_use_color__mutmut_11 # type: ignore # mutmut generated
mutants_x_use_color__mutmut['x_use_color__mutmut_12'] = x_use_color__mutmut_12 # type: ignore # mutmut generated
mutants_x_use_color__mutmut['x_use_color__mutmut_13'] = x_use_color__mutmut_13 # type: ignore # mutmut generated
mutants_x_use_color__mutmut['x_use_color__mutmut_14'] = x_use_color__mutmut_14 # type: ignore # mutmut generated
mutants_x_use_color__mutmut['x_use_color__mutmut_15'] = x_use_color__mutmut_15 # type: ignore # mutmut generated
mutants_x_use_color__mutmut['x_use_color__mutmut_16'] = x_use_color__mutmut_16 # type: ignore # mutmut generated
mutants_x_use_color__mutmut['x_use_color__mutmut_17'] = x_use_color__mutmut_17 # type: ignore # mutmut generated
mutants_x_c__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_c__mutmut)
def c(text: str, *styles: str) -> str:
    if not styles or not use_color():
        return text
    return "".join(styles) + text + RESET


def x_c__mutmut_orig(text: str, *styles: str) -> str:
    if not styles or not use_color():
        return text
    return "".join(styles) + text + RESET


def x_c__mutmut_1(text: str, *styles: str) -> str:
    if not styles and not use_color():
        return text
    return "".join(styles) + text + RESET


def x_c__mutmut_2(text: str, *styles: str) -> str:
    if styles or not use_color():
        return text
    return "".join(styles) + text + RESET


def x_c__mutmut_3(text: str, *styles: str) -> str:
    if not styles or use_color():
        return text
    return "".join(styles) + text + RESET


def x_c__mutmut_4(text: str, *styles: str) -> str:
    if not styles or not use_color():
        return text
    return "".join(styles) + text - RESET


def x_c__mutmut_5(text: str, *styles: str) -> str:
    if not styles or not use_color():
        return text
    return "".join(styles) - text + RESET


def x_c__mutmut_6(text: str, *styles: str) -> str:
    if not styles or not use_color():
        return text
    return "".join(None) + text + RESET


def x_c__mutmut_7(text: str, *styles: str) -> str:
    if not styles or not use_color():
        return text
    return "XXXX".join(styles) + text + RESET

mutants_x_c__mutmut['_mutmut_orig'] = x_c__mutmut_orig # type: ignore # mutmut generated
mutants_x_c__mutmut['x_c__mutmut_1'] = x_c__mutmut_1 # type: ignore # mutmut generated
mutants_x_c__mutmut['x_c__mutmut_2'] = x_c__mutmut_2 # type: ignore # mutmut generated
mutants_x_c__mutmut['x_c__mutmut_3'] = x_c__mutmut_3 # type: ignore # mutmut generated
mutants_x_c__mutmut['x_c__mutmut_4'] = x_c__mutmut_4 # type: ignore # mutmut generated
mutants_x_c__mutmut['x_c__mutmut_5'] = x_c__mutmut_5 # type: ignore # mutmut generated
mutants_x_c__mutmut['x_c__mutmut_6'] = x_c__mutmut_6 # type: ignore # mutmut generated
mutants_x_c__mutmut['x_c__mutmut_7'] = x_c__mutmut_7 # type: ignore # mutmut generated
mutants_x_ok__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_ok__mutmut)
def ok(msg: str) -> None:
    print("  " + c("✓", GREEN) + " " + msg)


def x_ok__mutmut_orig(msg: str) -> None:
    print("  " + c("✓", GREEN) + " " + msg)


def x_ok__mutmut_1(msg: str) -> None:
    print(None)


def x_ok__mutmut_2(msg: str) -> None:
    print("  " + c("✓", GREEN) + " " - msg)


def x_ok__mutmut_3(msg: str) -> None:
    print("  " + c("✓", GREEN) - " " + msg)


def x_ok__mutmut_4(msg: str) -> None:
    print("  " - c("✓", GREEN) + " " + msg)


def x_ok__mutmut_5(msg: str) -> None:
    print("XX  XX" + c("✓", GREEN) + " " + msg)


def x_ok__mutmut_6(msg: str) -> None:
    print("  " + c(None, GREEN) + " " + msg)


def x_ok__mutmut_7(msg: str) -> None:
    print("  " + c("✓", None) + " " + msg)


def x_ok__mutmut_8(msg: str) -> None:
    print("  " + c(GREEN) + " " + msg)


def x_ok__mutmut_9(msg: str) -> None:
    print("  " + c("✓", ) + " " + msg)


def x_ok__mutmut_10(msg: str) -> None:
    print("  " + c("XX✓XX", GREEN) + " " + msg)


def x_ok__mutmut_11(msg: str) -> None:
    print("  " + c("✓", GREEN) + "XX XX" + msg)

mutants_x_ok__mutmut['_mutmut_orig'] = x_ok__mutmut_orig # type: ignore # mutmut generated
mutants_x_ok__mutmut['x_ok__mutmut_1'] = x_ok__mutmut_1 # type: ignore # mutmut generated
mutants_x_ok__mutmut['x_ok__mutmut_2'] = x_ok__mutmut_2 # type: ignore # mutmut generated
mutants_x_ok__mutmut['x_ok__mutmut_3'] = x_ok__mutmut_3 # type: ignore # mutmut generated
mutants_x_ok__mutmut['x_ok__mutmut_4'] = x_ok__mutmut_4 # type: ignore # mutmut generated
mutants_x_ok__mutmut['x_ok__mutmut_5'] = x_ok__mutmut_5 # type: ignore # mutmut generated
mutants_x_ok__mutmut['x_ok__mutmut_6'] = x_ok__mutmut_6 # type: ignore # mutmut generated
mutants_x_ok__mutmut['x_ok__mutmut_7'] = x_ok__mutmut_7 # type: ignore # mutmut generated
mutants_x_ok__mutmut['x_ok__mutmut_8'] = x_ok__mutmut_8 # type: ignore # mutmut generated
mutants_x_ok__mutmut['x_ok__mutmut_9'] = x_ok__mutmut_9 # type: ignore # mutmut generated
mutants_x_ok__mutmut['x_ok__mutmut_10'] = x_ok__mutmut_10 # type: ignore # mutmut generated
mutants_x_ok__mutmut['x_ok__mutmut_11'] = x_ok__mutmut_11 # type: ignore # mutmut generated
mutants_x_warn__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_warn__mutmut)
def warn(msg: str) -> None:
    print("  " + c("!", YELLOW) + " " + c(msg, YELLOW))


def x_warn__mutmut_orig(msg: str) -> None:
    print("  " + c("!", YELLOW) + " " + c(msg, YELLOW))


def x_warn__mutmut_1(msg: str) -> None:
    print(None)


def x_warn__mutmut_2(msg: str) -> None:
    print("  " + c("!", YELLOW) + " " - c(msg, YELLOW))


def x_warn__mutmut_3(msg: str) -> None:
    print("  " + c("!", YELLOW) - " " + c(msg, YELLOW))


def x_warn__mutmut_4(msg: str) -> None:
    print("  " - c("!", YELLOW) + " " + c(msg, YELLOW))


def x_warn__mutmut_5(msg: str) -> None:
    print("XX  XX" + c("!", YELLOW) + " " + c(msg, YELLOW))


def x_warn__mutmut_6(msg: str) -> None:
    print("  " + c(None, YELLOW) + " " + c(msg, YELLOW))


def x_warn__mutmut_7(msg: str) -> None:
    print("  " + c("!", None) + " " + c(msg, YELLOW))


def x_warn__mutmut_8(msg: str) -> None:
    print("  " + c(YELLOW) + " " + c(msg, YELLOW))


def x_warn__mutmut_9(msg: str) -> None:
    print("  " + c("!", ) + " " + c(msg, YELLOW))


def x_warn__mutmut_10(msg: str) -> None:
    print("  " + c("XX!XX", YELLOW) + " " + c(msg, YELLOW))


def x_warn__mutmut_11(msg: str) -> None:
    print("  " + c("!", YELLOW) + "XX XX" + c(msg, YELLOW))


def x_warn__mutmut_12(msg: str) -> None:
    print("  " + c("!", YELLOW) + " " + c(None, YELLOW))


def x_warn__mutmut_13(msg: str) -> None:
    print("  " + c("!", YELLOW) + " " + c(msg, None))


def x_warn__mutmut_14(msg: str) -> None:
    print("  " + c("!", YELLOW) + " " + c(YELLOW))


def x_warn__mutmut_15(msg: str) -> None:
    print("  " + c("!", YELLOW) + " " + c(msg, ))

mutants_x_warn__mutmut['_mutmut_orig'] = x_warn__mutmut_orig # type: ignore # mutmut generated
mutants_x_warn__mutmut['x_warn__mutmut_1'] = x_warn__mutmut_1 # type: ignore # mutmut generated
mutants_x_warn__mutmut['x_warn__mutmut_2'] = x_warn__mutmut_2 # type: ignore # mutmut generated
mutants_x_warn__mutmut['x_warn__mutmut_3'] = x_warn__mutmut_3 # type: ignore # mutmut generated
mutants_x_warn__mutmut['x_warn__mutmut_4'] = x_warn__mutmut_4 # type: ignore # mutmut generated
mutants_x_warn__mutmut['x_warn__mutmut_5'] = x_warn__mutmut_5 # type: ignore # mutmut generated
mutants_x_warn__mutmut['x_warn__mutmut_6'] = x_warn__mutmut_6 # type: ignore # mutmut generated
mutants_x_warn__mutmut['x_warn__mutmut_7'] = x_warn__mutmut_7 # type: ignore # mutmut generated
mutants_x_warn__mutmut['x_warn__mutmut_8'] = x_warn__mutmut_8 # type: ignore # mutmut generated
mutants_x_warn__mutmut['x_warn__mutmut_9'] = x_warn__mutmut_9 # type: ignore # mutmut generated
mutants_x_warn__mutmut['x_warn__mutmut_10'] = x_warn__mutmut_10 # type: ignore # mutmut generated
mutants_x_warn__mutmut['x_warn__mutmut_11'] = x_warn__mutmut_11 # type: ignore # mutmut generated
mutants_x_warn__mutmut['x_warn__mutmut_12'] = x_warn__mutmut_12 # type: ignore # mutmut generated
mutants_x_warn__mutmut['x_warn__mutmut_13'] = x_warn__mutmut_13 # type: ignore # mutmut generated
mutants_x_warn__mutmut['x_warn__mutmut_14'] = x_warn__mutmut_14 # type: ignore # mutmut generated
mutants_x_warn__mutmut['x_warn__mutmut_15'] = x_warn__mutmut_15 # type: ignore # mutmut generated
mutants_x_err__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_err__mutmut)
def err(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def x_err__mutmut_orig(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def x_err__mutmut_1(msg: str, hint: str = None) -> None:
    print(None, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def x_err__mutmut_2(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, BOLD) + msg, file=None)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def x_err__mutmut_3(msg: str, hint: str = None) -> None:
    print(file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def x_err__mutmut_4(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, BOLD) + msg, )
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def x_err__mutmut_5(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, BOLD) - msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def x_err__mutmut_6(msg: str, hint: str = None) -> None:
    print(c(None, RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def x_err__mutmut_7(msg: str, hint: str = None) -> None:
    print(c("Error: ", None, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def x_err__mutmut_8(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, None) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def x_err__mutmut_9(msg: str, hint: str = None) -> None:
    print(c(RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def x_err__mutmut_10(msg: str, hint: str = None) -> None:
    print(c("Error: ", BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def x_err__mutmut_11(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, ) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def x_err__mutmut_12(msg: str, hint: str = None) -> None:
    print(c("XXError: XX", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def x_err__mutmut_13(msg: str, hint: str = None) -> None:
    print(c("error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def x_err__mutmut_14(msg: str, hint: str = None) -> None:
    print(c("ERROR: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=sys.stderr)


def x_err__mutmut_15(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(None, file=sys.stderr)


def x_err__mutmut_16(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), file=None)


def x_err__mutmut_17(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(file=sys.stderr)


def x_err__mutmut_18(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, DIM), )


def x_err__mutmut_19(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c(None, DIM), file=sys.stderr)


def x_err__mutmut_20(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, None), file=sys.stderr)


def x_err__mutmut_21(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c(DIM), file=sys.stderr)


def x_err__mutmut_22(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " + hint, ), file=sys.stderr)


def x_err__mutmut_23(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  hint: " - hint, DIM), file=sys.stderr)


def x_err__mutmut_24(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("XX  hint: XX" + hint, DIM), file=sys.stderr)


def x_err__mutmut_25(msg: str, hint: str = None) -> None:
    print(c("Error: ", RED, BOLD) + msg, file=sys.stderr)
    if hint:
        print(c("  HINT: " + hint, DIM), file=sys.stderr)

mutants_x_err__mutmut['_mutmut_orig'] = x_err__mutmut_orig # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_1'] = x_err__mutmut_1 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_2'] = x_err__mutmut_2 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_3'] = x_err__mutmut_3 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_4'] = x_err__mutmut_4 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_5'] = x_err__mutmut_5 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_6'] = x_err__mutmut_6 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_7'] = x_err__mutmut_7 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_8'] = x_err__mutmut_8 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_9'] = x_err__mutmut_9 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_10'] = x_err__mutmut_10 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_11'] = x_err__mutmut_11 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_12'] = x_err__mutmut_12 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_13'] = x_err__mutmut_13 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_14'] = x_err__mutmut_14 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_15'] = x_err__mutmut_15 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_16'] = x_err__mutmut_16 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_17'] = x_err__mutmut_17 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_18'] = x_err__mutmut_18 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_19'] = x_err__mutmut_19 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_20'] = x_err__mutmut_20 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_21'] = x_err__mutmut_21 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_22'] = x_err__mutmut_22 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_23'] = x_err__mutmut_23 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_24'] = x_err__mutmut_24 # type: ignore # mutmut generated
mutants_x_err__mutmut['x_err__mutmut_25'] = x_err__mutmut_25 # type: ignore # mutmut generated
mutants_x_info__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_info__mutmut)
def info(msg: str = "") -> None:
    print("  " + msg if msg else "")


def x_info__mutmut_orig(msg: str = "") -> None:
    print("  " + msg if msg else "")


def x_info__mutmut_1(msg: str = "XXXX") -> None:
    print("  " + msg if msg else "")


def x_info__mutmut_2(msg: str = "") -> None:
    print(None)


def x_info__mutmut_3(msg: str = "") -> None:
    print("  " - msg if msg else "")


def x_info__mutmut_4(msg: str = "") -> None:
    print("XX  XX" + msg if msg else "")


def x_info__mutmut_5(msg: str = "") -> None:
    print("  " + msg if msg else "XXXX")

mutants_x_info__mutmut['_mutmut_orig'] = x_info__mutmut_orig # type: ignore # mutmut generated
mutants_x_info__mutmut['x_info__mutmut_1'] = x_info__mutmut_1 # type: ignore # mutmut generated
mutants_x_info__mutmut['x_info__mutmut_2'] = x_info__mutmut_2 # type: ignore # mutmut generated
mutants_x_info__mutmut['x_info__mutmut_3'] = x_info__mutmut_3 # type: ignore # mutmut generated
mutants_x_info__mutmut['x_info__mutmut_4'] = x_info__mutmut_4 # type: ignore # mutmut generated
mutants_x_info__mutmut['x_info__mutmut_5'] = x_info__mutmut_5 # type: ignore # mutmut generated
mutants_x_dim__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_dim__mutmut)
def dim(msg: str) -> None:
    print(c(msg, DIM))


def x_dim__mutmut_orig(msg: str) -> None:
    print(c(msg, DIM))


def x_dim__mutmut_1(msg: str) -> None:
    print(None)


def x_dim__mutmut_2(msg: str) -> None:
    print(c(None, DIM))


def x_dim__mutmut_3(msg: str) -> None:
    print(c(msg, None))


def x_dim__mutmut_4(msg: str) -> None:
    print(c(DIM))


def x_dim__mutmut_5(msg: str) -> None:
    print(c(msg, ))

mutants_x_dim__mutmut['_mutmut_orig'] = x_dim__mutmut_orig # type: ignore # mutmut generated
mutants_x_dim__mutmut['x_dim__mutmut_1'] = x_dim__mutmut_1 # type: ignore # mutmut generated
mutants_x_dim__mutmut['x_dim__mutmut_2'] = x_dim__mutmut_2 # type: ignore # mutmut generated
mutants_x_dim__mutmut['x_dim__mutmut_3'] = x_dim__mutmut_3 # type: ignore # mutmut generated
mutants_x_dim__mutmut['x_dim__mutmut_4'] = x_dim__mutmut_4 # type: ignore # mutmut generated
mutants_x_dim__mutmut['x_dim__mutmut_5'] = x_dim__mutmut_5 # type: ignore # mutmut generated
mutants_x_heading__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_heading__mutmut)
def heading(msg: str) -> None:
    print(c("==> ", BLUE, BOLD) + c(msg, BOLD))


def x_heading__mutmut_orig(msg: str) -> None:
    print(c("==> ", BLUE, BOLD) + c(msg, BOLD))


def x_heading__mutmut_1(msg: str) -> None:
    print(None)


def x_heading__mutmut_2(msg: str) -> None:
    print(c("==> ", BLUE, BOLD) - c(msg, BOLD))


def x_heading__mutmut_3(msg: str) -> None:
    print(c(None, BLUE, BOLD) + c(msg, BOLD))


def x_heading__mutmut_4(msg: str) -> None:
    print(c("==> ", None, BOLD) + c(msg, BOLD))


def x_heading__mutmut_5(msg: str) -> None:
    print(c("==> ", BLUE, None) + c(msg, BOLD))


def x_heading__mutmut_6(msg: str) -> None:
    print(c(BLUE, BOLD) + c(msg, BOLD))


def x_heading__mutmut_7(msg: str) -> None:
    print(c("==> ", BOLD) + c(msg, BOLD))


def x_heading__mutmut_8(msg: str) -> None:
    print(c("==> ", BLUE, ) + c(msg, BOLD))


def x_heading__mutmut_9(msg: str) -> None:
    print(c("XX==> XX", BLUE, BOLD) + c(msg, BOLD))


def x_heading__mutmut_10(msg: str) -> None:
    print(c("==> ", BLUE, BOLD) + c(None, BOLD))


def x_heading__mutmut_11(msg: str) -> None:
    print(c("==> ", BLUE, BOLD) + c(msg, None))


def x_heading__mutmut_12(msg: str) -> None:
    print(c("==> ", BLUE, BOLD) + c(BOLD))


def x_heading__mutmut_13(msg: str) -> None:
    print(c("==> ", BLUE, BOLD) + c(msg, ))

mutants_x_heading__mutmut['_mutmut_orig'] = x_heading__mutmut_orig # type: ignore # mutmut generated
mutants_x_heading__mutmut['x_heading__mutmut_1'] = x_heading__mutmut_1 # type: ignore # mutmut generated
mutants_x_heading__mutmut['x_heading__mutmut_2'] = x_heading__mutmut_2 # type: ignore # mutmut generated
mutants_x_heading__mutmut['x_heading__mutmut_3'] = x_heading__mutmut_3 # type: ignore # mutmut generated
mutants_x_heading__mutmut['x_heading__mutmut_4'] = x_heading__mutmut_4 # type: ignore # mutmut generated
mutants_x_heading__mutmut['x_heading__mutmut_5'] = x_heading__mutmut_5 # type: ignore # mutmut generated
mutants_x_heading__mutmut['x_heading__mutmut_6'] = x_heading__mutmut_6 # type: ignore # mutmut generated
mutants_x_heading__mutmut['x_heading__mutmut_7'] = x_heading__mutmut_7 # type: ignore # mutmut generated
mutants_x_heading__mutmut['x_heading__mutmut_8'] = x_heading__mutmut_8 # type: ignore # mutmut generated
mutants_x_heading__mutmut['x_heading__mutmut_9'] = x_heading__mutmut_9 # type: ignore # mutmut generated
mutants_x_heading__mutmut['x_heading__mutmut_10'] = x_heading__mutmut_10 # type: ignore # mutmut generated
mutants_x_heading__mutmut['x_heading__mutmut_11'] = x_heading__mutmut_11 # type: ignore # mutmut generated
mutants_x_heading__mutmut['x_heading__mutmut_12'] = x_heading__mutmut_12 # type: ignore # mutmut generated
mutants_x_heading__mutmut['x_heading__mutmut_13'] = x_heading__mutmut_13 # type: ignore # mutmut generated
mutants_x_kv__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_kv__mutmut)
def kv(key: str, value: str, width: int = 14) -> None:
    print("  " + c(key.ljust(width), DIM) + str(value))


def x_kv__mutmut_orig(key: str, value: str, width: int = 14) -> None:
    print("  " + c(key.ljust(width), DIM) + str(value))


def x_kv__mutmut_1(key: str, value: str, width: int = 15) -> None:
    print("  " + c(key.ljust(width), DIM) + str(value))


def x_kv__mutmut_2(key: str, value: str, width: int = 14) -> None:
    print(None)


def x_kv__mutmut_3(key: str, value: str, width: int = 14) -> None:
    print("  " + c(key.ljust(width), DIM) - str(value))


def x_kv__mutmut_4(key: str, value: str, width: int = 14) -> None:
    print("  " - c(key.ljust(width), DIM) + str(value))


def x_kv__mutmut_5(key: str, value: str, width: int = 14) -> None:
    print("XX  XX" + c(key.ljust(width), DIM) + str(value))


def x_kv__mutmut_6(key: str, value: str, width: int = 14) -> None:
    print("  " + c(None, DIM) + str(value))


def x_kv__mutmut_7(key: str, value: str, width: int = 14) -> None:
    print("  " + c(key.ljust(width), None) + str(value))


def x_kv__mutmut_8(key: str, value: str, width: int = 14) -> None:
    print("  " + c(DIM) + str(value))


def x_kv__mutmut_9(key: str, value: str, width: int = 14) -> None:
    print("  " + c(key.ljust(width), ) + str(value))


def x_kv__mutmut_10(key: str, value: str, width: int = 14) -> None:
    print("  " + c(key.ljust(None), DIM) + str(value))


def x_kv__mutmut_11(key: str, value: str, width: int = 14) -> None:
    print("  " + c(key.rjust(width), DIM) + str(value))


def x_kv__mutmut_12(key: str, value: str, width: int = 14) -> None:
    print("  " + c(key.ljust(width), DIM) + str(None))

mutants_x_kv__mutmut['_mutmut_orig'] = x_kv__mutmut_orig # type: ignore # mutmut generated
mutants_x_kv__mutmut['x_kv__mutmut_1'] = x_kv__mutmut_1 # type: ignore # mutmut generated
mutants_x_kv__mutmut['x_kv__mutmut_2'] = x_kv__mutmut_2 # type: ignore # mutmut generated
mutants_x_kv__mutmut['x_kv__mutmut_3'] = x_kv__mutmut_3 # type: ignore # mutmut generated
mutants_x_kv__mutmut['x_kv__mutmut_4'] = x_kv__mutmut_4 # type: ignore # mutmut generated
mutants_x_kv__mutmut['x_kv__mutmut_5'] = x_kv__mutmut_5 # type: ignore # mutmut generated
mutants_x_kv__mutmut['x_kv__mutmut_6'] = x_kv__mutmut_6 # type: ignore # mutmut generated
mutants_x_kv__mutmut['x_kv__mutmut_7'] = x_kv__mutmut_7 # type: ignore # mutmut generated
mutants_x_kv__mutmut['x_kv__mutmut_8'] = x_kv__mutmut_8 # type: ignore # mutmut generated
mutants_x_kv__mutmut['x_kv__mutmut_9'] = x_kv__mutmut_9 # type: ignore # mutmut generated
mutants_x_kv__mutmut['x_kv__mutmut_10'] = x_kv__mutmut_10 # type: ignore # mutmut generated
mutants_x_kv__mutmut['x_kv__mutmut_11'] = x_kv__mutmut_11 # type: ignore # mutmut generated
mutants_x_kv__mutmut['x_kv__mutmut_12'] = x_kv__mutmut_12 # type: ignore # mutmut generated
mutants_x_table__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_table__mutmut)
def table(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_orig(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_1(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = None
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_2(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(None) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_3(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = None
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_4(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) - rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_5(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(None)] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_6(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(None, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_7(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, None))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_8(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_9(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, ))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_10(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_11(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = None
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_12(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(None)
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_13(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i <= len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_14(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(None)]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_15(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(None))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_16(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = None
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_17(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(None)
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_18(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "XX  XX".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_19(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(None) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_20(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).rjust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_21(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(None).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_22(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(None))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_23(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(None)
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_24(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(None, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_25(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, None))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_26(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_27(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, ))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_28(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print(None)


def x_table__mutmut_29(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).lstrip())


def x_table__mutmut_30(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(None).rstrip())


def x_table__mutmut_31(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("XX  XX".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_32(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(None) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_33(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.rjust(widths[i]) for i, cell in enumerate(r)).rstrip())


def x_table__mutmut_34(rows, headers=None) -> None:
    """Print an aligned table. rows: list of tuples of strings."""
    rows = [[str(x) for x in r] for r in rows]
    all_rows = ([list(map(str, headers))] if headers else []) + rows
    if not all_rows:
        return
    widths = [max(len(r[i]) for r in all_rows if i < len(r))
              for i in range(max(len(r) for r in all_rows))]
    if headers:
        line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
        print(c(line, BOLD))
    for r in rows:
        print("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(None)).rstrip())

mutants_x_table__mutmut['_mutmut_orig'] = x_table__mutmut_orig # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_1'] = x_table__mutmut_1 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_2'] = x_table__mutmut_2 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_3'] = x_table__mutmut_3 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_4'] = x_table__mutmut_4 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_5'] = x_table__mutmut_5 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_6'] = x_table__mutmut_6 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_7'] = x_table__mutmut_7 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_8'] = x_table__mutmut_8 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_9'] = x_table__mutmut_9 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_10'] = x_table__mutmut_10 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_11'] = x_table__mutmut_11 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_12'] = x_table__mutmut_12 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_13'] = x_table__mutmut_13 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_14'] = x_table__mutmut_14 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_15'] = x_table__mutmut_15 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_16'] = x_table__mutmut_16 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_17'] = x_table__mutmut_17 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_18'] = x_table__mutmut_18 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_19'] = x_table__mutmut_19 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_20'] = x_table__mutmut_20 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_21'] = x_table__mutmut_21 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_22'] = x_table__mutmut_22 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_23'] = x_table__mutmut_23 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_24'] = x_table__mutmut_24 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_25'] = x_table__mutmut_25 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_26'] = x_table__mutmut_26 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_27'] = x_table__mutmut_27 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_28'] = x_table__mutmut_28 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_29'] = x_table__mutmut_29 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_30'] = x_table__mutmut_30 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_31'] = x_table__mutmut_31 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_32'] = x_table__mutmut_32 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_33'] = x_table__mutmut_33 # type: ignore # mutmut generated
mutants_x_table__mutmut['x_table__mutmut_34'] = x_table__mutmut_34 # type: ignore # mutmut generated
mutants_x_confirm__mutmut: MutantDict = {}  # type: ignore


@_mutmut_mutated(mutants_x_confirm__mutmut)
def confirm(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_orig(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_1(prompt: str, default: bool = True) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_2(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv and "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_3(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") and "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_4(prompt: str, default: bool = False) -> bool:
    if os.environ.get(None) or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_5(prompt: str, default: bool = False) -> bool:
    if os.environ.get("XXBOOST_ASSUME_YESXX") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_6(prompt: str, default: bool = False) -> bool:
    if os.environ.get("boost_assume_yes") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_7(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "XX--yesXX" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_8(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--YES" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_9(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" not in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_10(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "XX-yXX" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_11(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-Y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_12(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" not in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_13(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return False
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_14(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_15(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = None
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_16(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = "XX [Y/n] XX" if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_17(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_18(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/N] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_19(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else "XX [y/N] XX"
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_20(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/n] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_21(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [Y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_22(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = None
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_23(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().upper()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_24(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(None).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_25(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt - suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_26(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return True
    if not answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_27(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if answer:
        return default
    return answer in ("y", "yes")


def x_confirm__mutmut_28(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer not in ("y", "yes")


def x_confirm__mutmut_29(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("XXyXX", "yes")


def x_confirm__mutmut_30(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("Y", "yes")


def x_confirm__mutmut_31(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "XXyesXX")


def x_confirm__mutmut_32(prompt: str, default: bool = False) -> bool:
    if os.environ.get("BOOST_ASSUME_YES") or "--yes" in sys.argv or "-y" in sys.argv:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(prompt + suffix).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not answer:
        return default
    return answer in ("y", "YES")

mutants_x_confirm__mutmut['_mutmut_orig'] = x_confirm__mutmut_orig # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_1'] = x_confirm__mutmut_1 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_2'] = x_confirm__mutmut_2 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_3'] = x_confirm__mutmut_3 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_4'] = x_confirm__mutmut_4 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_5'] = x_confirm__mutmut_5 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_6'] = x_confirm__mutmut_6 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_7'] = x_confirm__mutmut_7 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_8'] = x_confirm__mutmut_8 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_9'] = x_confirm__mutmut_9 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_10'] = x_confirm__mutmut_10 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_11'] = x_confirm__mutmut_11 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_12'] = x_confirm__mutmut_12 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_13'] = x_confirm__mutmut_13 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_14'] = x_confirm__mutmut_14 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_15'] = x_confirm__mutmut_15 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_16'] = x_confirm__mutmut_16 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_17'] = x_confirm__mutmut_17 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_18'] = x_confirm__mutmut_18 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_19'] = x_confirm__mutmut_19 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_20'] = x_confirm__mutmut_20 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_21'] = x_confirm__mutmut_21 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_22'] = x_confirm__mutmut_22 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_23'] = x_confirm__mutmut_23 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_24'] = x_confirm__mutmut_24 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_25'] = x_confirm__mutmut_25 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_26'] = x_confirm__mutmut_26 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_27'] = x_confirm__mutmut_27 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_28'] = x_confirm__mutmut_28 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_29'] = x_confirm__mutmut_29 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_30'] = x_confirm__mutmut_30 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_31'] = x_confirm__mutmut_31 # type: ignore # mutmut generated
mutants_x_confirm__mutmut['x_confirm__mutmut_32'] = x_confirm__mutmut_32 # type: ignore # mutmut generated
