import os
import time
from pathlib import Path

import pytest

from meter import healthcheck


def test_healthcheck_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HEALTHCHECK_LOG", raising=False)
    assert healthcheck.main() == 1


def test_healthcheck_fresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "updated.log"
    p.write_text("x")
    monkeypatch.setenv("HEALTHCHECK_LOG", str(p))
    monkeypatch.setenv("HEALTHCHECK_MAX_AGE_SEC", "3600")
    assert healthcheck.main() == 0


def test_healthcheck_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "updated.log"
    p.write_text("x")
    os.utime(p, (time.time() - 5000, time.time() - 5000))
    monkeypatch.setenv("HEALTHCHECK_LOG", str(p))
    monkeypatch.setenv("HEALTHCHECK_MAX_AGE_SEC", "60")
    assert healthcheck.main() == 1
