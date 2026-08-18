"""Test configuration: isolated SQLite DB and a FastAPI TestClient."""

from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Point settings at an in-memory DB BEFORE importing app modules that cache it.
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'test.db')}"


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def sample_files() -> dict[str, str]:
    from app.services.analysis.demo_data import load_sample_files

    return load_sample_files()
