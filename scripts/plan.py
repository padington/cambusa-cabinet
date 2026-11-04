"""Derive stock, layouts and a transparent estimate from the v18 GLB."""
from argparse import ArgumentParser
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from html import escape
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/vendor'))
import trimesh

MODEL = ROOT / 'outputs/cambusa-frame-v18/closed.glb'
parser = ArgumentParser(description=__doc__)
parser.add_argument('--stock', type=Path, default=ROOT / 'inputs/stock.json')
parser.add_argument('--prices', type=Path, default=ROOT / 'inputs/prices.json')
parser.add_argument('--output', type=Path)
args = parser.parse_args()
STOCK_FILE = args.stock
PRICES_FILE = args.prices
default = STOCK_FILE == ROOT / 'inputs/stock.json' and PRICES_FILE == ROOT / 'inputs/prices.json'
OUT = args.output or (ROOT / 'outputs/cambusa-frame-v18/planning' if default else ROOT / 'local-estimate')
OUT.mkdir(parents=True, exist_ok=True)
stock = json.loads(STOCK_FILE.read_text())
prices = json.loads(PRICES_FILE.read_text())
sheet_types = stock['sheets']
bar_types = stock['bars']
hardware = stock['hardware']
scene = trimesh.load(MODEL, force='scene')
wood, bars = defaultdict(list), defaultdict(list)
parts = []
feet = 0


def wood_kind(name):
    if name == 'B04-back':
        return 'plywood-9', 1
    if name.endswith('-front-panel'):
        return 'plywood-12', 1
    if '-shelf-' in name:
        return 'plywood-12', 2
    if '-lip-' in name:
        return 'plywood-9', 1
    if name.startswith(('B02-', 'B03-')):
        return 'plywood-12', 0
    if name.startswith('B05-'):
        return 'plywood-18', 0
    if name.startswith(('B01-','B10-','B11-','B20-','B21-')):
        return 'plywood-12', 2
    return 'plywood-18', 2


for node in sorted(scene.graph.nodes_geometry):
    transform, geometry = scene.graph[node]
    mesh = scene.geometry[geometry].copy()
    mesh.apply_transform(transform)
    a, b, c = [round(float(v) * 1000, 2) for v in mesh.extents]
    x, y, z = a, c, b  # Convert GLTF axes to cabinet axes.
    dimensions = [x, y, z]
    item = {'id':node, 'dimensions_mm':dimensions}
    parts.append(item)
    if node.startswith('Foot-'):
        feet += 1
        item.update(stock='foot', unit='piece')
    elif node.startswith('ShelfAngle-'):
        item.update(stock='shelf-angle', cut_mm=max(dimensions))
        bars[item['stock']].append(item)
    elif node.startswith(('Post-', 'Beam-')):
        item.update(stock='profile-30', cut_mm=max(dimensions))
        bars[item['stock']].append(item)
    elif node.endswith(('-jamb', '-hinge-stile', '-meeting-stile')):
        code = 'wood-40x45' if node.endswith('-jamb') else 'wood-45x90'
        item.update(stock=code, cut_mm=z + 2 * stock['wood_blank_trim_each_end_mm'])
        bars[code].append(item)
    else:
        code, thickness_axis = wood_kind(node)
        thickness = dimensions[thickness_axis]
        spec = sheet_types[code]
        assert math.isclose(thickness, spec['thickness_mm'], abs_tol=.01), (node, thickness)
        width, length = sorted(value for i, value in enumerate(dimensions) if i != thickness_axis)
        trim = stock['wood_blank_trim_each_edge_mm']
        item.update(stock=code, blank_mm=[width+2*trim, length+2*trim])
        wood[code].append(item)

# First-fit guillotine placement. The long blank dimension follows the grain.
# Edge trim and clearance are charged once here, in addition to blank oversize.
sheets = []
for code, items in sorted(wood.items()):
    spec = sheet_types[code]
    width, height = spec['size_mm']
    trim, gap = spec['edge_trim_mm'], spec['gap_mm']
    layouts = []
    for item in sorted(items, key=lambda p: (p['blank_mm'][0]*p['blank_mm'][1], p['id']), reverse=True):
        blank_width, blank_height = item['blank_mm']
        needed_w, needed_h = blank_width + gap, blank_height + gap
        initial = (trim, trim, width-2*trim+gap, height-2*trim+gap)
        if needed_w > initial[2] or needed_h > initial[3]:
            raise ValueError(f'{item["id"]} не помещается на лист {code}')
        placement = next(
            ((layout, i) for layout in layouts for i, rect in enumerate(layout['free'])
             if needed_w <= rect[2] and needed_h <= rect[3]), None
        )
        if placement is None:
            layout = {'stock':code, 'sheet':len(layouts)+1, 'size_mm':[width,height], 'free':[initial], 'pieces':[]}
            layouts.append(layout)
            placement = (layout, 0)
        layout, index = placement
        px, py, avail_w, avail_h = layout['free'].pop(index)
        layout['free'].extend([
            (px+needed_w, py, avail_w-needed_w, needed_h),
            (px, py+needed_h, avail_w, avail_h-needed_h),
        ])
        layout['pieces'].append({'id':item['id'], 'xy_mm':[px,py], 'size_mm':[blank_width,blank_height]})
    for layout in layouts:
        layout.pop('free')
    sheets.extend(layouts)

bar_layout = []
for code, items in sorted(bars.items()):
    spec = bar_types[code]
    kerf = spec['kerf_mm']
    layouts = []
    for item in sorted(items, key=lambda p: (p['cut_mm'],p['id']), reverse=True):
        required = item['cut_mm'] + kerf
        available = spec['length_mm'] - 2*spec['edge_trim_mm']
        if required > available:
            raise ValueError(f'{item["id"]} не помещается на заготовку {code}')
        layout = next((layout for layout in layouts if layout['remainder_mm'] >= required), None)
        if layout is None:
            layout = {'stock':code, 'bar':len(layouts)+1, 'stock_mm':spec['length_mm'],
                      'remainder_mm':available, 'pieces':[]}
            layouts.append(layout)
        position = spec['length_mm'] - spec['edge_trim_mm'] - layout['remainder_mm']
        layout['pieces'].append({'id':item['id'], 'start_mm':position, 'cut_mm':item['cut_mm']})
        layout['remainder_mm'] -= required
    bar_layout.extend(layouts)

# Verify coverage and sheet separation independently from the packer.
seen = Counter(p['id'] for layout in sheets + bar_layout for p in layout['pieces'])
assert seen == Counter(p['id'] for p in parts if p['stock'] != 'foot')
for layout in sheets:
    spec = sheet_types[layout['stock']]
    trim, gap = spec['edge_trim_mm'], spec['gap_mm']
    for i, a in enumerate(layout['pieces']):
        x, y = a['xy_mm']
        w, h = a['size_mm']
        assert x >= trim and y >= trim and x+w <= layout['size_mm'][0]-trim and y+h <= layout['size_mm'][1]-trim
        for b in layout['pieces'][i+1:]:
            bx, by = b['xy_mm']
            bw, bh = b['size_mm']
            assert x+w+gap <= bx or bx+bw+gap <= x or y+h+gap <= by or by+bh+gap <= y
assert all(layout['remainder_mm'] >= 0 for layout in bar_layout)

rows = []
for catalog, layouts in [(sheet_types, sheets), (bar_types, bar_layout)]:
    for code, count in sorted(Counter(layout['stock'] for layout in layouts).items()):
        rows.append({'id':code, 'description':catalog[code]['name'], 'quantity':count, 'unit':catalog[code]['unit']})
for item in hardware:
    row = item.copy()
    if row['id'] == 'foot':
        row['quantity'] = feet
    if row['id'] == 'hinge':
        row['quantity'] = 2 * sum(p['id'].endswith('-hinge-stile') for p in parts)
    rows.append(row)
unknown_keys = prices['unit_prices'].keys() - {row['id'] for row in rows}
if unknown_keys:
    raise ValueError(f'Неизвестные позиции в ценах: {sorted(unknown_keys)}')

subtotal = Decimal(0)
priced_count = 0
for row in rows:
    raw_price = prices['unit_prices'].get(row['id'])
    unit_price = None
    if raw_price is not None:
        try:
            unit_price = Decimal(str(raw_price))
        except InvalidOperation:
            raise ValueError(f'Некорректная цена: {row["id"]}') from None
        if not unit_price.is_finite() or unit_price < 0:
            raise ValueError(f'Некорректная цена: {row["id"]}')
    row['unit_price'] = None if unit_price is None else str(unit_price)
    cost = None if row['quantity'] is None or unit_price is None else row['quantity'] * unit_price
    row['amount'] = None if cost is None else str(cost)
    if cost is not None:
        subtotal += cost
        priced_count += 1

report = {'model':'cambusa-v18', 'currency':prices['currency'], 'parts':parts,
          'sheets':sheets, 'bars':bar_layout, 'estimate':rows, 'priced_rows':priced_count,
          'subtotal_known':str(subtotal) if priced_count else None,
          'total_complete':priced_count == len(rows)}
(OUT/'plan.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

md = [
    '# Ведомость и смета Cambusa v18', '',
    'Расчёт по габаритам деталей в closed.glb. Это план закупки и контроль раскладки. '
    'Карты используют прямоугольные заготовки с припуском, а пазы и отверстия задаются отдельно.', '',
    f'Деталей в модели — **{len(parts)}**, фанеры — **{len(sheets)} листов**, '
    f'длинномерных заготовок — **{len(bar_layout)}**.', '',
    '| Позиция | Количество | Единица | Цена | Сумма |',
    '|---|---:|---|---:|---:|',
]
for row in rows:
    cells = [row['description'],row['quantity'],row['unit'],row['unit_price'],row['amount']]
    md.append('| ' + ' | '.join('требует уточнения' if x is None else str(x) for x in cells) + ' |')
if priced_count:
    md.extend(['', f'**{"Итого" if report["total_complete"] else "Сумма оценённых позиций"} — {subtotal:,.2f} {prices["currency"]}.**'])
else:
    md.extend(['', 'Цены пока не внесены. Итог сметы не рассчитан.'])
md.extend(['', '## Детали по модели', '', '| Код | Габарит X × Y × Z, мм | Материал |',
           '|---|---:|---|'])
for part in parts:
    md.append(f'| {part["id"]} | {" × ".join(f"{d:g}" for d in part["dimensions_mm"])} | {part["stock"]} |')
md.extend(['', '## Раскрой длинномерных заготовок', '',
           '| Материал | Заготовка | Детали по порядку, мм | Остаток, мм |', '|---|---:|---|---:|'])
for layout in bar_layout:
    pieces = ', '.join(f'{p["id"]} — {p["cut_mm"]:g}' for p in layout['pieces'])
    md.append(f'| {layout["stock"]} | {layout["bar"]} | {pieces} | {layout["remainder_mm"]:g} |')
(OUT/'BOM.md').write_text('\n'.join(md) + '\n')

columns = 3
tile_w, tile_h = 340, 365
height = 48 + math.ceil(len(sheets)/columns)*tile_h
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {columns*tile_w} {height}" role="img">',
       '<title>Раскладка фанеры Cambusa v18</title>',
       '<rect width="100%" height="100%" fill="#f7f6f2"/>',
       '<text x="16" y="29" font-family="sans-serif" font-size="20">Cambusa v18 · фанера · заготовки с припуском</text>']
colors = ['#d9bf9b','#c3cbb4','#ced8dc','#e3c9b9']
for i, layout in enumerate(sheets):
    ox = (i % columns)*tile_w + 16
    oy = (i // columns)*tile_h + 60
    sw, sh = layout['size_mm']
    scale = min(306/sw,306/sh)
    name = sheet_types[layout['stock']]['name']
    svg.append(f'<text x="{ox}" y="{oy}" font-family="sans-serif" font-size="14">{escape(name)} · лист {layout["sheet"]} · {sw} × {sh}</text>')
    oy += 12
    svg.append(f'<rect x="{ox}" y="{oy}" width="{sw*scale:.2f}" height="{sh*scale:.2f}" fill="white" stroke="#444"/>')
    for j, p in enumerate(layout['pieces']):
        x,y = [d*scale for d in p['xy_mm']]
        w,h = [d*scale for d in p['size_mm']]
        px,py = ox+x,oy+y
        ident = escape(p['id'])
        svg.append(f'<rect x="{px:.2f}" y="{py:.2f}" width="{w:.2f}" height="{h:.2f}" fill="{colors[j%len(colors)]}" stroke="#685d4d" stroke-width=".45"><title>{ident} · {p["size_mm"][0]:g} × {p["size_mm"][1]:g} мм</title></rect>')
        if w>len(ident)*4.8 and h>14:
            svg.append(f'<text x="{px+3:.2f}" y="{py+11:.2f}" font-size="8" font-family="sans-serif">{ident}</text>')
svg.append('</svg>')
(OUT/'cut-plan.svg').write_text('\n'.join(svg) + '\n')
print(f'{len(parts)} деталей, {len(sheets)} листов, {len(bar_layout)} длинномерных заготовок, {priced_count}/{len(rows)} строк с ценами')
