import os
import subprocess
import sys
from pathlib import Path


def run_rustest(project_dir: Path) -> subprocess.CompletedProcess:
    # A wide COLUMNS keeps rustest's own output renderer from hard-wrapping
    # long error messages mid-word, which would break substring assertions.
    return subprocess.run(
        [sys.executable, "-m", "rustest", "--color=never", str(project_dir)],
        cwd=project_dir,
        capture_output=True,
        text=True,
        env={**os.environ, "COLUMNS": "300"},
    )
