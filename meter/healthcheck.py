"""Docker HEALTHCHECK: exit 0 if updated.log is fresh."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def main() -> int:
    path = Path(os.environ.get("HEALTHCHECK_LOG", "updated.log"))
    max_age = int(os.environ.get("HEALTHCHECK_MAX_AGE_SEC", "2400"))
    if not path.is_file():
        return 1
    age = time.time() - path.stat().st_mtime
    return 0 if age < max_age else 1


if __name__ == "__main__":
    sys.exit(main())
