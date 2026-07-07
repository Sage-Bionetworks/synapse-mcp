"""Guard that README.md's tool table stays in sync with the code.

Shells out to ``scripts/gen_tool_table.py --check`` so CI fails (with a diff)
whenever a tool is added, renamed, or re-described without regenerating the
README table. Run ``uv run python scripts/gen_tool_table.py`` to fix.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "gen_tool_table.py"


def test_readme_tool_table_in_sync():
    # Force PAT auth in the child: strip any OAuth vars the developer env may
    # carry, otherwise app.py would select OAuth mode and change import
    # side effects.
    env = {**os.environ, "SYNAPSE_PAT": "dummy-for-tests"}
    env.pop("SYNAPSE_OAUTH_CLIENT_ID", None)
    env.pop("SYNAPSE_OAUTH_CLIENT_SECRET", None)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        "README.md tool table is out of sync with the tool catalog.\n"
        "Run: uv run python scripts/gen_tool_table.py\n\n"
        f"{result.stdout}\n{result.stderr}"
    )
