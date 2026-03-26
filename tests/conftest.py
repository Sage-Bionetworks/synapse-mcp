"""Test configuration for synapse-mcp."""

import os
import sys
from pathlib import Path

# Ensure package can be imported without real credentials.
# The app module raises ValueError at import time when no auth env var is set,
# which blocks test collection even though all tests use mocked clients.
os.environ.setdefault("SYNAPSE_PAT", "fake-for-tests")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
