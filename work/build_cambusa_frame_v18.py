"""Build a lightweight full-height aluminum-frame variant with 12 mm infill."""
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'work/vendor')]
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Point, box
from shapely.ops import unary_union
import trimesh as tm
from geometry import COLORS, add, cube, panel, render, scene

VERSION = 'cambusa-v18'
OUT = ROOT / 'outputs/cambusa-frame-v18'
SOURCE = ROOT / 'outputs/cambusa-doors-v15/closed.glb'
OUT.mkdir(exist_ok=True)
WIDTH, HEIGHT, DEPTH = 1000, 1800, 500
POST = 30
INFILL = 12
SETBACK = 18 - INFILL
JAMB_SHIFT = POST + 1
TOP_RAIL_BOTTOM = 1770
FOOT = 12
PROFILE = 'https://www.boschrexroth.com/en/de/p/strut-profile-3842990723/'
COLORS.update(
    wood=[104, 74, 52, 255], back=[78, 54, 39, 255], frame=[48, 52, 53, 255],
    rail=[66, 70, 71, 255], rubber=[35, 38, 38, 255], door=[98, 67, 46, 255], skin=[127, 92, 64, 255],
    tray=[136, 97, 68, 255],
)

# All calculations use millimeters and axes X right, Y back, Z up.
reference = tm.load(SOURCE, force='scene')
old = {}
for node in reference.graph.nodes_geometry:
    transform, geom = reference.graph[node]
    mesh = reference.geometry[geom].copy()
    mesh.apply_transform(transform)
    mesh.vertices = np.round(mesh.vertices[:, [0, 2, 1]] * [1000, -1000, 1000], 3)
    old[node] = mesh

parts = []
frame = []
lengths = Counter()
section = box(0, 0, POST, POST).difference(unary_union([
    box(11, -1, 19, 2.4), box(11, 27.6, 19, 31),
    box(-1, 11, 2.4, 19), box(27.6, 11, 31, 19),
]))


def profile(name, axis, origin, length):
    # Envelope with visual slots. Internal cavities and joining hardware
    # depend on the actual purchased extrusion and are outside this sketch.
    mesh = panel(section, axis, 0, length)
    mesh.apply_translation(origin)
    add(frame, name, mesh, 'frame', 'profile')
    lengths[length] += 1


for x, y in itertools.product((0, WIDTH - POST), (0, DEPTH - POST)):
    profile(f'Post-{x}-{y}', 2, [x, y, FOOT], HEIGHT - FOOT)
    add(frame, f'Foot-{x}-{y}', cube([x + 1, y + 1, 0], [x + 29, y + 29, FOOT]), 'rubber', 'foot')
for level, z in [('lower', 72), ('body', 770), ('top', TOP_RAIL_BOTTOM)]:
    profile(f'Beam-{level}-rear', 0, [POST, DEPTH - POST, z], WIDTH - 2 * POST)
    if level != 'lower':
        profile(f'Beam-{level}-front', 0, [POST, 0, z], WIDTH - 2 * POST)
    for x in (0, WIDTH - POST):
        profile(f'Beam-{level}-side-{x}', 1, [x, POST, z], DEPTH - 2 * POST)

bottom = box(18, 0, 982, 500).difference(unary_union([
    box(x0, y0, x1, y1)
    for (x0, x1), (y0, y1) in itertools.product(((17, 31), (969, 983)), ((-1, 31), (469, 501)))
]))
add(parts, 'B00-bottom-notched', panel(bottom, 2, 800, 18), 'wood')
add(parts, 'B01-top-inset', cube([31, 31, 1782], [969, 469, 1782 + INFILL]), 'wood')
add(parts, 'B03-right-side', cube([982, 31, 800], [982 + INFILL, 469, 1769]), 'wood')
holes = [(y, z) for y in range(50, 451, 50) for z in range(840, 1741, 50)]
pegboard = box(31, 800, 469, 1769).difference(unary_union([
    Point(y, z).buffer(6, quad_segs=6) for y, z in holes
]))
add(parts, 'B02-left-pegboard', panel(pegboard, 0, SETBACK, INFILL), 'wood')
back = box(18, 818, 982, 1769).union(box(31, 1769, 969, 1782))
add(parts, 'B04-back', panel(back, 1, 461, 9), 'back')
for name in ('B05-divider', 'B10-left-shelf', 'B11-left-shelf', 'B20-right-shelf', 'B21-right-shelf'):
    lo, hi = old[name].bounds.copy()
    hi[1] = 461
    if name != 'B05-divider':
        # Keep the usable shelf level. Add an angle under each long side.
        lo[2] = hi[2] - INFILL
        left = name.startswith('B1')
        z = lo[2]
        for position, edge, sign, start, length in (
            ('outer', 18 if left else 982, 1 if left else -1, 39, 422),
            ('inner', 491 if left else 509, -1 if left else 1, 104, 357),
        ):
            toe0, toe1 = sorted((edge, edge + 20 * sign))
            stem0, stem1 = sorted((edge, edge + 2 * sign))
            section = box(toe0, z - 2, toe1, z).union(box(stem0, z - 20, stem1, z - 2))
            add(frame, f'ShelfAngle-{name[:3]}-{position}', panel(section, 1, start, length), 'rail', 'profile')
    add(parts, name, cube(lo, hi), 'wood')


def shift_height(mesh):
    z = mesh.vertices[:, 2]
    # Shift the top groove and rail as a group, leaving the hinge pockets intact.
    mesh.vertices[:, 2] = z - 12 * np.clip((z - 1710) / 40, 0, 1)


for side in ('L', 'R'):
    jamb = old[f'{side}-jamb']
    jamb.apply_translation([JAMB_SHIFT if side == 'L' else -JAMB_SHIFT, 0, 0])
    shift_height(jamb)
    add(parts, f'{side}-jamb', jamb, 'door')
    for name, mesh in old.items():
        if not name.startswith(f'{side}-') or name.endswith('-jamb'):
            continue
        x = mesh.vertices[:, 0]
        from_left = x if side == 'L' else WIDTH - x
        # Translate the entire hinge stile, preserve the meeting stile and
        # shorten only the clear span between these two zones.
        shift = JAMB_SHIFT * np.clip((454 - from_left) / (454 - 84), 0, 1)
        mesh.vertices[:, 0] = x + shift * (1 if side == 'L' else -1)
        shift_height(mesh)
        material = 'skin' if name.endswith('front-panel') else 'tray' if '-shelf-' in name else 'door'
        add(parts, name, mesh, material, 'door', side=side)

# Preserve the same schematic 180-degree mortise pose as v15, translated
# by 31 mm per leaf. This is a static state, not the hinge's swing path.
def opened(part):
    if part['group'] != 'door':
        return part
    mesh = part['mesh'].copy()
    x_translate = 36 + 39.5 + 2 * JAMB_SHIFT
    if part['side'] == 'R':
        x_translate = 2 * WIDTH - x_translate
    matrix = np.diag([-1., -1., 1., 1.])
    matrix[:3, 3] = [x_translate, -5, 0]
    mesh.apply_transform(matrix)
    return dict(part, mesh=mesh)


closed = frame + parts
wide = [opened(p) for p in closed]


def check_assembly(parts):
    for part in parts:
        assert part['mesh'].is_volume, part['name']
    checked = 0
    for a, b in itertools.combinations(parts, 2):
        av, bv = a['mesh'], b['mesh']
        intersection = np.minimum(av.bounds[1], bv.bounds[1]) - np.maximum(av.bounds[0], bv.bounds[0])
        if np.min(intersection) <= .002:
            continue
        actual = tm.boolean.intersection([av, bv], engine='manifold')
        volume = abs(float(actual.volume))
        assert volume <= .08, (a['name'], b['name'], volume)
        checked += 1
    return checked


checks = {name: check_assembly(model) for name, model in [('closed', closed), ('open', wide)]}
bounds = tm.util.concatenate([part['mesh'] for part in closed]).bounds
assert np.allclose(bounds, [[0, 0, 0], [WIDTH, DEPTH, HEIGHT]])
assert lengths == Counter({1788: 4, 940: 5, 440: 6})
source_mortises = json.loads(SOURCE.with_name('ПРОВЕРКА.json').read_text())['mortises']
for cut in source_mortises:
    cut['edge_face_x_mm'] += JAMB_SHIFT if cut['id'].startswith('L-') else -JAMB_SHIFT
    # Vertical and depth datums are unchanged in the mortised region.

report = {
    'version': VERSION, 'basis': 'cambusa-v15', 'status': 'geometry study',
    'profile_reference': PROFILE, 'envelope_mm': [WIDTH, HEIGHT, DEPTH],
    'profile_section_mm': [POST, POST], 'infill_mm': INFILL, 'reveal_mm': SETBACK,
    'shelf_angle_section_mm': [20, 20, 2], 'shelf_angle_counts': {'422': 4, '357': 4}, 'profile_lengths_mm': dict(sorted(lengths.items(), reverse=True)),
    'foot_height_allowance_mm': FOOT, 'cabinet_bottom_at_mm': 800,
    'door_each_mm': [426.5, 946, 85], 'pegboard_side': 'left', 'pegboard_holes': len(holes),
    'shelf_clearance_at_closed_doors_mm': 17, 'drawer_clear_opening_mm': 424,
    'candidate_hinge': 'Sugatsune HES3D-120BL', 'mortises': source_mortises,
    'tests': {'closed_and_open_static_collisions': False, 'narrow_phase_pairs': checks,
              'hinge_swing_verified': False, 'joint_strength_verified': False},
    'sha256': {},
}
for name, model in [('closed', closed), ('open', wide), ('frame', frame)]:
    path = OUT / f'{name}.glb'
    path.write_bytes(scene(model).export(file_type='glb'))
    assert len(tm.load(path, force='scene').geometry) == len(model)
    report['sha256'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()

preview = Image.new('RGB', (1536, 780), '#f6f5f1')
draw = ImageDraw.Draw(preview)
fonts = Path('/System/Library/Fonts/Supplemental')
def preview_font(size, bold=False):
    stem = 'Arial Bold.ttf' if bold else 'Arial.ttf'
    candidates = [str(fonts / stem), 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf', stem]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)
font = preview_font(32, bold=True)
small = preview_font(23)
draw.text((30, 25), 'Cambusa v18 · облицовка и полки 12 мм', font=font, fill='#25352b')
for offset, width, label, model, yaw in [
    (0, 465, 'Закрыто', closed, -26), (465, 650, 'Расчётный вид на 180°', wide, -20),
    (1115, 421, 'Каркас', frame, 27),
]:
    preview.paste(render(model, width, 640, yaw=yaw, pitch=12), (offset, 80))
    draw.text((offset + 30, 737), label, font=small, fill='#25352b')
preview.save(OUT / 'preview.png')

# The inline and standalone viewers use these very same meshes and endpoint transform.
inline = {'parts': []}
for part in closed:
    mesh = part['mesh']
    item = {
        'g': part['group'], 'm': part['material'],
        'v': np.round(mesh.vertices, 2).tolist(), 'f': mesh.faces.tolist(),
    }
    if part['group'] == 'door':
        left_offset = 36 + 39.5 + 2 * JAMB_SHIFT
        item['a'] = left_offset if part['side'] == 'L' else 2 * WIDTH - left_offset
    inline['parts'].append(item)
(OUT / 'ПРОВЕРКА.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
(ROOT / 'work/cambusa-frame-v18-meshes.json').write_text(json.dumps(inline, separators=(',', ':')))
print(json.dumps({key: report[key] for key in ('envelope_mm', 'door_each_mm', 'tests', 'profile_lengths_mm')}))
