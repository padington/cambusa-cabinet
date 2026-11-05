"""Cambusa v28. A flat plywood door on directly mounted RSI 3025 hinges."""
import csv
import hashlib
import json

import numpy as np
import trimesh as tm
from shapely.geometry import LineString

from build_aluminum_corner import (
    add, collision_pairs, cube, cut, overlap_volume, panel, pose,
    swept_clearance,
)
from build_frame_joinery import (
    cabinet as v27_cabinet, bore, is_same_connector, revolve_at,
)
from build_right_lift import ROOT, SECTIONS, audit_leaf, export, named
from build_pegboard_cabinet import right_leaf, right_parts, slot_end

OUT = ROOT / 'outputs/cambusa-v28-simple-left-door'
AXIS_LEFT = np.array([34.0, 16.5])
HINGE_CENTERS = (893.0, 1285.0, 1677.0)
MAX_ANGLE = 180
DOOR_LOW = [36, 23, 803]
DOOR_HIGH = [488, 41, 1767]
NUT_FRONT_OFFSET = 4.964530067816615


def supplier_meshes(sku):
    source = json.loads((ROOT / 'inputs/rsi-simple-hinge.json').read_text())[sku]
    step = ROOT / f'inputs/supplier-cad/rsi-{sku}.step'
    assert hashlib.sha256(step.read_bytes()).hexdigest() == source['step_sha256']
    with np.load(ROOT / 'inputs/rsi-simple-hinge.npz') as data:
        return [tm.Trimesh(vertices=data[f'{sku}_{i}_v'], faces=data[f'{sku}_{i}_f'],
                           process=False) for i in range(len(source['parts']))]


def countersunk_bolt(x, z, length):
    # DIN 7991 M6, nominal envelope. Threads use the major diameter.
    return revolve_at([x, 16.5, z], [0, 1, 0],
                      [(0, 0), (6, 0), (3, 3), (3, length), (0, length)])


def washer(x, z):
    return cut(bore([x, 41, z], [0, 1, 0], 0, 1.6, 9),
               [bore([x, 41, z], [0, 1, 0], -.1, 1.7, 3.2)])


def locknut(x, z):
    mesh = tm.creation.cylinder(radius=10 / np.sqrt(3), height=6, sections=6)
    mesh.apply_transform(tm.geometry.align_vectors([0, 0, 1], [0, 1, 0]))
    mesh.apply_translation([x, 45.6, z])
    return cut(mesh, [bore([x, 42.6, z], [0, 1, 0], -.1, 6.1, 3.05)])


def cabinet():
    fixed, old_left, rows, joints = v27_cabinet()
    removed = ('DIRAK-', 'Bracket-', 'Fixed-head-', 'Fixed-nut-', 'Slot-head-')
    fixed = [p for p in fixed if not p['name'].startswith(removed)]
    left, holes, machining = [], [], []
    hinge = supplier_meshes('3025')
    nuts = supplier_meshes('5049')
    for index, center in enumerate(HINGE_CENTERS, 1):
        transform = np.array([[1, 0, 0, AXIS_LEFT[0]],
                              [0, 0, -1, AXIS_LEFT[1]],
                              [0, 1, 0, center - 25],
                              [0, 0, 0, 1]], dtype=float)
        for i, part in enumerate(hinge):
            target = left if i == 1 else fixed
            add(target, f'Left-hinge-{index}-3025-{i}',
                part.copy().apply_transform(transform), 'handle')
        for offset in (-15, 15):
            z = center + offset
            add(fixed, f'Left-profile-bolt-{index}-{offset}',
                countersunk_bolt(19, z, 14), 'fastener')
            for i, nut in enumerate(nuts):
                placed = nut.copy()
                placed.vertices[:, 1] += 23 + NUT_FRONT_OFFSET
                placed.vertices[:, 0] += 19
                placed.vertices[:, 2] += z
                add(fixed, f'Left-profile-nut-{index}-{offset}-5049-{i}', placed, 'fastener')
            add(left, f'Left-panel-bolt-{index}-{offset}',
                countersunk_bolt(49, z, 35), 'fastener')
            add(left, f'Left-panel-washer-{index}-{offset}', washer(49, z), 'fastener')
            add(left, f'Left-panel-locknut-{index}-{offset}', locknut(49, z), 'fastener')
            holes.append(bore([49, 23, z], [0, 1, 0], -.1, 18.1, 3.3))
            machining.append(['Left-door-face-18', 'through-hole', 13, z - 803, 6.6, 18])
    # A blind finger recess leaves 6 mm of plywood at the back of the door.
    grip = LineString([(470, 1250), (470, 1322)]).buffer(9, quad_segs=16)
    holes.append(panel(grip, 1, 22.9, 12.1))
    machining.append(['Left-door-face-18', 'blind-grip-pocket', 434, 483, 18, 12])
    add(left, 'Left-door-face-18', cut(cube(DOOR_LOW, DOOR_HIGH), holes), 'door')
    rows.append(['Left-door-face-18', 452, 964, 18, 1])
    assert not any(p['name'].startswith(removed) for p in fixed)
    assert not any('tray' in p['name'].lower() for p in left)
    return fixed, left, rows, joints, machining, old_left


def allowed_thread_contact(pair):
    if is_same_connector(pair):
        return True
    a, b = pair['parts']
    if a.startswith('Left-profile-') and b.startswith('Left-profile-'):
        # The supplier nut includes its threaded minor diameter. Only the
        # bolt and its own nut have intentional thread engagement.
        return a.split('-')[3:5] == b.split('-')[3:5]
    return False


def door_sweep(fixed, left):
    face = [p for p in left if p['name'] == 'Left-door-face-18']
    # Clearance from the cabinet and right doors. Hinge mating surfaces
    # receive a separate solid-intersection test throughout their motion.
    obstacles = [p for p in fixed + right_parts(0)
                 if not p['name'].startswith(('Left-hinge-', 'Left-profile-'))]
    return swept_clearance(obstacles, face, AXIS_LEFT, max_angle=MAX_ANGLE)


def hinge_motion(fixed, left):
    failures = []
    for index, center in enumerate(HINGE_CENTERS, 1):
        moving = [p for p in left if p['name'].startswith((
            f'Left-hinge-{index}-', f'Left-panel-bolt-{index}-',
            f'Left-panel-washer-{index}-', f'Left-panel-locknut-{index}-'))]
        stationary = [p for p in fixed if p['mesh'].bounds[0, 2] < center + 32 and
                      p['mesh'].bounds[1, 2] > center - 32 and
                      p['mesh'].bounds[0, 0] < 70 and p['mesh'].bounds[0, 1] < 65]
        for angle in range(0, MAX_ANGLE + 1, 5):
            for part in pose([], moving, AXIS_LEFT, angle):
                for obstacle in stationary:
                    if np.min(np.minimum(part['mesh'].bounds[1], obstacle['mesh'].bounds[1]) -
                              np.maximum(part['mesh'].bounds[0], obstacle['mesh'].bounds[0])) <= .002:
                        continue
                    volume = overlap_volume(part['mesh'], obstacle['mesh'])
                    if volume > .08:
                        failures.append([index, angle, part['name'], obstacle['name'], round(volume, 3)])
    return failures


def detail_parts(fixed, left):
    selected = []
    window = cube([3, 8, 848], [97, 60, 938])
    for part in fixed + left:
        name = part['name']
        if name in ('Post-4-23', 'Left-door-face-18'):
            mesh = tm.boolean.intersection([part['mesh'], window], engine='manifold')
            selected.append(dict(part, mesh=mesh, left=name == 'Left-door-face-18'))
        elif name.startswith(('Left-hinge-1-', 'Left-profile-bolt-1-', 'Left-profile-nut-1-',
                              'Left-panel-bolt-1-', 'Left-panel-washer-1-', 'Left-panel-locknut-1-')):
            selected.append(dict(part, left=part in left))
    return selected


def main():
    OUT.mkdir(exist_ok=True)
    fixed, left, rows, joints, machining, old_left = cabinet()
    endpoints = {}
    for angle in (0, 90, 180):
        assembly = pose(fixed + right_parts(0), left, AXIS_LEFT, angle)
        endpoints[str(angle)] = [p for p in collision_pairs(named(assembly))
                                 if not allowed_thread_contact(p)]
        print('angle', angle, endpoints[str(angle)], flush=True)
        export(OUT / f'cabinet-{angle}.glb', assembly)
    sweep = door_sweep(fixed, left)
    print('door sweep', sweep, flush=True)
    hinges = hinge_motion(fixed, left)
    print('hinge sweep', hinges[:10], flush=True)
    right = [audit_leaf(right_leaf(z), fixed + left, z, slot_end(z)) for _, z in SECTIONS]
    print('right sweep', right, flush=True)
    assert not any(endpoints.values()), endpoints
    assert sweep[2] > 0, sweep
    assert not hinges, hinges
    assert min(r[1] for r in right) > 0, right
    export(OUT / 'left-door.glb', left)
    export(OUT / 'left-hinge-detail.glb', detail_parts(fixed, left))
    with (OUT / 'panels-and-shelves.csv').open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['part', 'width_or_depth_mm', 'height_or_depth_mm', 'stock_mm', 'count'])
        writer.writerows(rows)
    with (OUT / 'door-machining.csv').open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['part', 'operation', 'x_from_left_mm', 'z_from_bottom_mm', 'diameter_or_width_mm', 'depth_mm'])
        writer.writerows(machining)
    report = dict(version='cambusa-v28-simple-left-door', axis_xy_mm=AXIS_LEFT.tolist(),
                  max_opening_deg=MAX_ANGLE, door_blank_mm=[452, 964, 18],
                  hinge_centers_from_bottom_mm=[z - 803 for z in HINGE_CENTERS],
                  endpoint_overlaps=endpoints, door_sweep=sweep,
                  hinge_sweep_step_deg=5, hinge_sweep_collisions=hinges,
                  right_sweep=right, hinge_count=3,
                  previous_door_wood_volume_mm3=sum(p['mesh'].volume for p in old_left if p['material'] == 'door'),
                  new_door_wood_volume_mm3=sum(p['mesh'].volume for p in left if p['material'] == 'door'),
                  fabrication_release=False,
                  pending=['Confirm hinge load rating and mounting on a sample',
                           'Choose the closing catch and seal for dust protection'])
    (OUT / 'checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
