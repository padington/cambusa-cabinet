"""Regenerate geometry, the stock plan and the browser viewer."""
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
for script in ('work/build_cambusa_frame_v17.py', 'scripts/plan.py', 'scripts/audit_assembly.py',
               'scripts/study_270.py', 'scripts/draw_storage.py', 'work/build_cambusa_view.py'):
    subprocess.run([sys.executable, str(root / script)], check=True)
shutil.copy2(root / 'outputs/cambusa-frame-v17/planning/cut-plan.svg', root / 'docs')
