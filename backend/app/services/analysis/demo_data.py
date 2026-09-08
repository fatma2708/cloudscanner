"""Demo data: embedded sample Terraform project used by /demo endpoints and tests."""

from __future__ import annotations

import importlib.resources as resources
from pathlib import Path

_SAMPLE_DIR = Path(__file__).resolve().parents[3] / "scripts" / "sample_project"


def load_sample_files() -> dict[str, str]:
    """Load the sample project's .tf files as ``{path: content}``."""
    files: dict[str, str] = {}
    if not _SAMPLE_DIR.exists():
        # fall back to package resources (installed wheel)
        ref = resources.files("app.services.analysis")
        try:
            for child in ref.joinpath("sample_project").iterdir():
                if child.name.endswith((".tf", ".tofu")):
                    files[child.name] = child.read_text(encoding="utf-8")
        except FileNotFoundError:
            pass
        return files
    for child in sorted(_SAMPLE_DIR.iterdir()):
        # ``overrides.tf`` contains a duplicate declaration used during local
        # development. It is not a Terraform override filename and would make
        # the public demo double-count that resource.
        if child.name == "overrides.tf":
            continue
        if child.is_file() and child.name.endswith((".tf", ".tofu")):
            files[child.name] = child.read_text(encoding="utf-8")
    return files
