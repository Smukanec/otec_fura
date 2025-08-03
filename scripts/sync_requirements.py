#!/usr/bin/env python3
"""Generate requirements.txt from pyproject.toml dependencies.

This script ensures that requirements.txt mirrors the dependencies
specified in pyproject.toml. Run it whenever the dependency list
in pyproject.toml changes.

It keeps only the direct dependencies without pinning versions.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
REQ_FILE = ROOT / "requirements.txt"

def main() -> None:
    data = tomllib.loads(PYPROJECT.read_text("utf-8"))
    deps = data.get("project", {}).get("dependencies", [])
    content = "# Generated from pyproject.toml. Do not edit manually.\n" + "\n".join(deps) + "\n"
    REQ_FILE.write_text(content, encoding="utf-8")

if __name__ == "__main__":
    main()
