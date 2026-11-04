"""Regenerate geometry, the stock plan and the browser viewer."""
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
for script in ('work/build_cambusa_frame_v18.py', 'scripts/plan.py', 'scripts/audit_assembly.py',
               'scripts/compare_thickness.py', 'work/build_cambusa_view.py'):
    subprocess.run([sys.executable, str(root / script)], check=True)
subprocess.run([sys.executable, str(root / 'scripts/study_270.py'), '--version', 'v18'], check=True)
shutil.copy2(root / 'outputs/cambusa-frame-v18/planning/cut-plan.svg', root / 'docs')
