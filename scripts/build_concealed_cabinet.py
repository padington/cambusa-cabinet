"""Cambusa v29. Upper corner cubes, levelling feet and a full right side."""
import json
from collections import Counter

import numpy as np
import trimesh as tm

from build_aluminum_corner import add, cube, cut, overlap_volume
from build_frame_joinery import bore, revolve_at
from build_frame_joinery import is_same_connector
from build_pegboard_cabinet import drill_x, pegboard
from build_simple_left_door import ROOT, cabinet as previous_cabinet
from build_slotted_panels import profile_mesh
from review_current_hardware import source_mesh

OUT = ROOT / 'outputs/cambusa-v29-concealed-hardware'
POST_BOTTOM, POST_TOP = 44.0, 1770.0


def reflected(mesh):
    result = mesh.copy()
    result.vertices[:, 0] = 1000 - result.vertices[:, 0]
    result.invert()
    return result


def hex_nut(center, direction, across_flats, thickness, hole_radius):
    mesh = tm.creation.cylinder(radius=across_flats / np.sqrt(3),
                                height=thickness, sections=6)
    mesh.apply_transform(tm.geometry.align_vectors([0, 0, 1], direction))
    mesh.apply_translation(center)
    return cut(mesh, [bore(center, direction, -thickness, thickness, hole_radius)])


def cube_transform(x, y):
    sx, sy = (1 if x == 4 else -1), (1 if y == 23 else -1)
    # Native small fixing holes face -X,+Y,+Z. Map these to the post below
    # and the two inward-facing horizontal members using a proper rotation.
    axes = np.column_stack(([0, 0, 1], [sx, 0, 0], [0, sy, 0]))
    if np.linalg.det(axes) < 0:
        axes = axes[:, [0, 2, 1]]
    transform = np.eye(4)
    transform[:3, :3] = axes
    transform[:3, 3] = [x + 15, y + 15, 1785]
    return transform


def normalized_cube():
    mesh = source_mesh('rsi-2069')
    return mesh.apply_translation(-mesh.bounds.mean(axis=0))


def cube_bolt(axis, side, distance):
    direction = np.eye(3)[axis] * side
    start = direction * (15 - distance)
    return revolve_at(start, direction,
                      [(0, 0), (8, 0), (4, 4), (4, 25), (0, 25)])


def cube_seats():
    mesh = normalized_cube()
    seats = []
    for axis, side in ((0, -1), (1, 1), (2, 1)):
        for distance in np.arange(4, 12.01, .1):
            bolt = cube_bolt(axis, side, distance)
            if overlap_volume(mesh, bolt) < .02:
                seats.append((axis, side, round(float(distance), 2)))
                break
        else:
            raise ValueError(f'No M8 bolt seat in supplier cube on axis {axis}')
    return seats


def upper_corners(fixed):
    seats = cube_seats()
    source = normalized_cube()
    for x in (4, 966):
        for y in (23, 470):
            transform = cube_transform(x, y)
            tag = f'{x}-{y}'
            add(fixed, f'Cube-2069-{tag}', source.copy().apply_transform(transform), 'handle')
            for axis, side, distance in seats:
                direction = transform[:3, :3] @ (np.eye(3)[axis] * side)
                interface = transform[:3, 3] + direction * 15
                target = (f'Post-{tag}' if direction[2] < 0 else
                          f'Beam-top-side-{x}' if abs(direction[1]) > .5 else
                          'Beam-top-front' if y == 23 else 'Beam-top-rear')
                add(fixed, f'Cube-bolt-M8x25-{tag}-{axis}',
                    cube_bolt(axis, side, distance).apply_transform(transform), 'fastener',
                    thread_targets={target:bore(interface, direction, -.01, 19, 4.05)})
            # Supplier includes caps but publishes the connector as one solid.
            # Represent the included caps by clearance envelopes at its ports.
            for axis, side, radius in ((0, 1, 8.7), (1, -1, 9.7), (2, -1, 9.7)):
                outward = np.eye(3)[axis] * side
                if axis == 0:
                    cap = bore(outward * 15, outward, -1.3, 0, radius)
                else:
                    cap = revolve_at(outward * 15, outward,
                                     [(0, -1.3), (radius - 1.3, -1.3), (radius, 0), (0, 0)])
                add(fixed, f'Cube-cap-{tag}-{axis}', cap.apply_transform(transform), 'frame')
    return seats


def levelling_feet(fixed):
    source = source_mesh('rsi-d49m8h30-simple')
    for x in (4, 966):
        for y in (23, 470):
            transform = np.array([[1, 0, 0, x + 15], [0, 0, -1, y + 15],
                                  [0, 1, 0, 21], [0, 0, 0, 1]], dtype=float)
            add(fixed, f'Levelling-foot-D49M8H30-{x}-{y}',
                source.copy().apply_transform(transform), 'frame', thread_targets={
                    f'Post-{x}-{y}':bore([x+15,y+15,44], [0,0,1], -.01, 20.1, 4.05),
                    f'Foot-locknut-M8-{x}-{y}':bore([x+15,y+15,37.5], [0,0,1], -.01, 6.51, 4.05)})
            add(fixed, f'Foot-locknut-M8-{x}-{y}',
                hex_nut([x + 15, y + 15, POST_BOTTOM - 3.25],
                        [0, 0, 1], 13, 6.5, 3.95), 'fastener')


def right_side(fixed):
    bores = [drill_x(28, y, z, -10.3, .1, 3.03)
             for z in (1127, 1448) for y in (100, 405)]
    wall, hardware, mortises = pegboard(bores, pattern=[])
    add(fixed, 'Right-wall-18', reflected(wall), 'wood')
    for part in hardware:
        add(fixed, part['name'].replace('Pegboard-', 'Right-wall-'),
            reflected(part['mesh']), part['material'])
    parts = {p['name']:p for p in fixed}
    for name, tools in mortises.items():
        target = name.replace('-4', '-966')
        parts[target]['mesh'] = cut(parts[target]['mesh'], [reflected(t) for t in tools])
    for index, z in enumerate((1127, 1448), 1):
        shelf = cube([510, 23, z], [971.5, 458, z + 12])
        tools = [drill_x(509, y, z, -.1, 11.35, 3.1) for y in (100, 405)]
        tools += [drill_x(972, y, z, -11, .1, 3.1) for y in (100, 405)]
        tools.append(cube([965.5, 22, z-.1], [972, 53.5, z+12.1]))
        add(fixed, f'Shelf-Right-{index}', cut(shelf, tools), 'wood')
        for y in (100, 405):
            add(fixed, f'Shelf-pin-Right-{index}-wall-{y}',
                drill_x(972, y, z, -10, 10, 3), 'fastener')
    for index, top in enumerate((1127, 1448, 1770), 1):
        z = top - 52
        # Prepared aluminum spacer backs the right runner. It shares the
        # 6 mm stock used for the concealed hinge mounting spacers.
        spacer = cube([966, 105, z - 22], [972, 365, z + 10])
        holes = []
        wall_holes = []
        for y in (140, 330):
            point = [991.6, y, z - 6]
            holes.append(bore(point, [-1, 0, 0], 19.5, 25.1, 2.5))
            wall_holes.append(bore(point, [-1, 0, 0], 1.5, 19.7, 2.7))
            add(fixed, f'Runner-spacer-bolt-M5x25-{index}-{y}',
                bore(point, [-1, 0, 0], 0, 25, 2.5), 'fastener')
            add(fixed, f'Runner-spacer-head-M5-{index}-{y}',
                bore(point, [-1, 0, 0], -5, 0, 4.25), 'fastener')
            washer = cut(bore(point, [-1, 0, 0], 0, 1.6, 5),
                         [bore(point, [-1, 0, 0], -.1, 1.7, 2.7)])
            add(fixed, f'Runner-spacer-washer-{index}-{y}', washer, 'fastener')
        add(fixed, f'Right-runner-spacer-6-{index}', cut(spacer, holes), 'angle')
        parts['Right-wall-18']['mesh'] = cut(parts['Right-wall-18']['mesh'], wall_holes)


def cabinet_structure():
    fixed, _, rows, joints, _, _ = previous_cabinet()
    joints = [j for j in joints if not j['beam'].startswith(('Beam-top-', 'Beam-right-shelf-'))]
    joint_ids = {j['id'] for j in joints}
    fixed = [p for p in fixed
             if not p['name'].startswith(('Left-hinge-', 'Left-profile-', 'Foot-',
                                          'Beam-right-shelf-', 'Right-infill-8-',
                                          'Shelf-Right-', 'Right-cheek-'))
             and (not p['name'].startswith('RSI-') or p['name'].split('::')[1] in joint_ids)]
    _, _, pegboard_mortises = pegboard([], pattern=[])
    for part in fixed:
        name = part['name']
        if name.startswith('Post-'):
            low, high = part['mesh'].bounds.copy()
            low[2], high[2] = POST_BOTTOM, POST_TOP
            part['mesh'] = profile_mesh(low, high)
        if name.startswith('Beam-top-'):
            part['mesh'] = profile_mesh(*part['mesh'].bounds)
            if name in pegboard_mortises:
                part['mesh'] = cut(part['mesh'], pegboard_mortises[name])
        if name == 'Back-infill-8':
            part['mesh'] = cut(part['mesh'], [cube([x, 479, 1769.7], [x + 8, 491, 1801])
                                            for x in (26.4, 965.6)])
    seats = upper_corners(fixed)
    levelling_feet(fixed)
    right_side(fixed)
    rows = [row for row in rows if not row[0].startswith(('Right-infill-', 'Shelf-Right-',
                                                        'Left-door-face-'))]
    rows += [['Right-wall-18', 416, 969, 18, 1],
             ['Shelf-Right-1', 461.5, 435, 12, 1], ['Shelf-Right-2', 461.5, 435, 12, 1]]
    assert Counter(j['sku'] for j in joints) == {'5212':14, '5211':2}
    return fixed, rows, joints, seats


def audit_contacts(parts):
    from build_aluminum_corner import collision_pairs
    from build_right_lift import named
    by_name = {p['name']:p for p in parts}
    unexpected, threads = [], []
    for pair in collision_pairs(named(parts)):
        if is_same_connector(pair):
            continue
        from build_simple_left_door import allowed_thread_contact
        if allowed_thread_contact(pair):
            continue
        first, second = (by_name[name] for name in pair['parts'])
        if first.get('hinge') and first.get('hinge') == second.get('hinge'):
            # Commercial hinge internals include dimensional envelopes.
            # Their internal mating geometry is outside this cabinet audit.
            continue
        region = first.get('thread_targets', {}).get(second['name'])
        if region is None:
            region = second.get('thread_targets', {}).get(first['name'])
        if region is None:
            unexpected.append(pair)
            continue
        common = tm.boolean.intersection([first['mesh'], second['mesh']], engine='manifold')
        outside = tm.boolean.difference([common, region], engine='manifold')
        outside_volume = abs(float(outside.volume)) if len(outside.faces) else 0
        if outside_volume > .08:
            unexpected.append(dict(pair, outside_thread_region_mm3=outside_volume))
        else:
            threads.append(dict(pair, outside_thread_region_mm3=round(outside_volume, 6)))
    return unexpected, threads


def reviewed_structure_with_previous_door():
    """Keep the verified v28 hinge until the concealed-hinge sweep is resolved.

    A closed pose alone is insufficient to promote the new concealed hinge.
    The v29 panel/foot/cube checkpoint therefore retains the previous door.
    """
    fixed, rows, joints, seats = cabinet_structure()
    old_fixed, left, _, _, _, _ = previous_cabinet()
    fixed += [p for p in old_fixed if p['name'].startswith(('Left-hinge-', 'Left-profile-'))]
    rows.append(['Left-door-face-18', 452, 964, 18, 1])
    return fixed, left, rows, joints, seats


if __name__ == '__main__':
    fixed, rows, joints, seats = cabinet_structure()
    print('cube seats', seats)
    print('parts', len(fixed), 'frame connectors', Counter(j['sku'] for j in joints))
