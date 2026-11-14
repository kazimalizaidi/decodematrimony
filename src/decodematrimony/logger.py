"""🎀 Coquette terminal logger: one tiny typed module, every other module reuses it. ✨

Palette (ANSI):
  🎀 Coquette Pink  \033[95m  milestones / headers
  ✨ Sage Green      \033[92m  success / significant insights
  🧸 Warm Cream      \033[93m  missingness / anomalies / non-significant
  💗 Strawberry Blush \033[91m failures / rollbacks
  🌸 Reset           \033[0m
"""
from __future__ import annotations

import sys
from types import TracebackType
from typing import IO, Optional, Type

PINK = "\033[95m"
SAGE = "\033[92m"
CREAM = "\033[93m"
BLUSH = "\033[91m"
RESET = "\033[0m"


def _emit(color: str, tag: str, msg: str, stream: Optional[IO[str]] = None) -> None:
    out: IO[str] = stream if stream is not None else sys.stdout
    print(f"{color}{tag} {msg}{RESET}", file=out)


def milestone(msg: str) -> None:
    """🎀 Pipeline headers and operational milestones (pink)."""
    _emit(PINK, "🎀", msg)


def success(msg: str) -> None:
    """✨ Cleaning success, SQL commits, significant insights (sage)."""
    _emit(SAGE, "✨", msg)


def missing(msg: str) -> None:
    """🧸 Missing variables, format anomalies, non-significant results (cream)."""
    _emit(CREAM, "🧸", msg)


def failure(msg: str) -> None:
    """💗 Parsing failures, constraint violations, rollbacks (blush)."""
    _emit(BLUSH, "💗", msg, sys.stderr)


def stat_result(label: str, estimate: float, p: Optional[float], significant: bool) -> None:
    """📉 Significant -> sage, otherwise cream. Descriptive rows (p=None) -> pink."""
    p_txt = "n/a" if p is None else f"{p:.4f}"
    line = f"📉 {label}: est={estimate:.4f} p={p_txt}"
    if p is None:
        milestone(line)
    elif significant:
        success(line)
    else:
        missing(line)


def _excepthook(
    exc_type: Type[BaseException], exc: BaseException, tb: Optional[TracebackType]
) -> None:
    failure(f"Unhandled {exc_type.__name__}: {exc}")


def install_excepthook() -> None:
    """💗 Route uncaught exceptions through the blush palette."""
    sys.excepthook = _excepthook
