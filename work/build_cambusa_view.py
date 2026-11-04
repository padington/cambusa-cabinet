"""Build the chat fragment and static GitHub Pages viewer from the same meshes."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
work = root / 'work'
fragment = (work / 'cambusa-frame-v17-view.html').read_text().replace(
    '__MODEL_DATA__', (work / 'cambusa-frame-v17-meshes.json').read_text()
)
assert len(fragment.encode()) < 1_000_000 and '__MODEL_DATA__' not in fragment
if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(fragment)
docs = root / 'docs'
docs.mkdir(exist_ok=True)
start = """<!doctype html>
<html lang="ru">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Интерактивная 3D-модель шкафа Cambusa v17 с алюминиевым каркасом.">
<title>Cambusa · 3D-модель шкафа</title>
<style>
:root {color-scheme:light dark;--font-size-base:16px;font:16px/1.45 system-ui,sans-serif}
body {max-width:850px;padding:24px 18px;margin:auto}
h2,p {margin:0}
.viz-controls {display:flex;gap:12px 22px;flex-wrap:wrap;align-items:center}
.form-label {display:grid;gap:4px}
.form-select {font:inherit;padding:6px;border-radius:4px}
.form-range {width:min(220px,100%);margin:0}
.text-small {font-size:14px}
.sr-only {position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
footer {display:flex;gap:10px 18px;flex-wrap:wrap;margin-top:20px}
</style>
<main>
"""
end = """
<footer aria-label="Модели для скачивания">
  <a href="closed.glb">Закрытый шкаф · GLB</a>
  <a href="open.glb">Открытый шкаф · GLB</a>
  <a href="frame.glb">Каркас · GLB</a>
  <a href="cut-plan.svg">Раскладка на листах</a>
  <a href="variants/v18/">Сравнить облегчённую v18</a>
  <a href="https://github.com/padington/cambusa-cabinet/tree/main/outputs/cambusa-frame-v17/storage">Коллажи хранения</a>
</footer>
</main>
"""
(docs / 'index.html').write_text(start + fragment + end)
(docs / '.nojekyll').touch()
for name in ('closed.glb', 'open.glb', 'frame.glb'):
    (docs / name).write_bytes((root / 'outputs/cambusa-frame-v17' / name).read_bytes())
