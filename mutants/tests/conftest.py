"""Shared pytest configuration for the test suite."""
from __future__ import annotations

import sys
import os
from importlib import import_module
from pathlib import Path
from typing import Iterable


def _discover_src_roots() -> tuple[Path | None, Path | None]:
    """Return paths to the regular and mutants src directories."""
    tests_dir = Path(__file__).resolve().parent
    immediate_root = tests_dir.parent

    if immediate_root.name == "mutants":
        repo_root = immediate_root.parent
        mutants_root = immediate_root
    else:
        repo_root = immediate_root
        mutants_root_candidate = repo_root / "mutants"
        mutants_root = mutants_root_candidate if mutants_root_candidate.exists() else None

    regular_src = repo_root / "src"
    mutants_src = mutants_root / "src" if mutants_root else None

    return (regular_src if regular_src.exists() else None, mutants_src if mutants_src and mutants_src.exists() else None)


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _update_pythonpath(new_entries: list[str]) -> None:
    """Ensure child processes inherit paths to project sources."""
    existing = os.environ.get("PYTHONPATH", "")
    existing_parts = [part for part in existing.split(os.pathsep) if part] if existing else []
    merged = _unique(new_entries + existing_parts)
    if merged:
        os.environ["PYTHONPATH"] = os.pathsep.join(merged)


def ensure_src_on_path() -> None:
    """Ensure the project source directory is importable before tests run."""
    regular_src, mutants_src = _discover_src_roots()

    candidate_order: list[str] = []
    if regular_src is not None:
        candidate_order.append(str(regular_src))
    if mutants_src is not None:
        candidate_order.append(str(mutants_src))

    unique_candidates = _unique(candidate_order)

    for candidate in reversed(unique_candidates):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)

    _update_pythonpath(unique_candidates)

    if regular_src is None or mutants_src is None:
        return

    mutants_pkg = mutants_src / "kira"
    if not mutants_pkg.exists():
        return

    try:
        kira = import_module("kira")
    except ImportError:
        return

    mutants_pkg_str = str(mutants_pkg)
    if mutants_pkg_str not in kira.__path__:
        kira.__path__.insert(0, mutants_pkg_str)


ensure_src_on_path()
