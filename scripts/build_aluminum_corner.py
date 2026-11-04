"""Compare v19 with a 30 mm upright and a single offset bracket per hinge."""
import json
import math
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely import affinity
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
import trimesh as tm

from audit_assembly import intersections, load_parts

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work'))
from geometry import COLORS, add, cube, panel, render, scene

REFERENCE = ROOT / 'outputs/cambusa-hybrid-v19-corner'
OUT = ROOT / 'outputs/cambusa-aluminum-v20-corner'
POST_FRONT = 23
POST_LEFT = 4
POST_SLOT_X = POST_LEFT + 15
POST_BOTTOM, POST_TOP = 818, 1782
BRACKET_HEIGHT = 96
SLOT_BOLT_OFFSETS = (-39, 39)
HINGE_BOLT_OFFSETS = (-25.5, 25.5)
BORE_RADIUS = 3.3
HEAD_RADIUS = 5.5
NUT_RADIUS = 6
COLORS.update(wood=[113, 81, 58, 255], door=[107, 73, 50, 255], back=[75, 55, 42, 255],
              frame=[41, 49, 51, 255], rail=[161, 169, 174, 255], tray=[139, 105, 76, 255],
              bracket=[103, 141, 152, 255], hardware=[106, 109, 112, 255])


def cylinder(axis, start, end, first, z, radius):
    mesh = tm.creation.cylinder(radius=radius, height=end-start, sections=48)
    translation = [first, first, z]
    translation[axis] = (start+end)/2
    rotation_axis = [0, 1, 0] if axis == 0 else [-1, 0, 0]
    mesh.apply_transform(tm.transformations.rotation_matrix(math.pi/2, rotation_axis))
    mesh.apply_translation(translation)
    return mesh


def cut(stock, holes):
    result = tm.boolean.difference([stock, *holes], engine='manifold')
    assert result.is_volume
    return result


def overlap_volume(first, second):
    result = tm.boolean.intersection([first, second], engine='manifold')
    return abs(float(result.volume)) if len(result.faces) else 0.0


def collision_pairs(parts):
    # A coplanar contact can return a zero-volume mesh. Trimesh still
    # computes its unused center of mass when reading the volume.
    with np.errstate(invalid='ignore'):
        return intersections(parts)['overlapping_volumes']


def footprint(mesh):
    triangles = (Polygon(triangle[:, :2]) for triangle in mesh.triangles)
    return unary_union([shape for shape in triangles if shape.area > .0001])


def pose(fixed, moving, axis, angle):
    transform = tm.transformations.rotation_matrix(math.radians(-angle), [0, 0, 1], [*axis, 0])
    return fixed + [dict(part, mesh=part['mesh'].copy().apply_transform(transform)) for part in moving]


def swept_clearance(fixed, moving, axis):
    fixed_shapes = [(part['name'], footprint(part['mesh']), part['mesh'].bounds[:, 2]) for part in fixed]
    checks = []
    for part in moving:
        z0, z1 = part['mesh'].bounds[:, 2]
        obstacles = [(name, shape) for name, shape, (bottom, top) in fixed_shapes
                     if min(z1, top) - max(z0, bottom) > .001]
        checks.append((part['name'], footprint(part['mesh']), obstacles))
    step = .125
    closest = (math.inf, None, None, None)
    for index in range(round(270/step)+1):
        angle = index * step
        for moving_name, shape, obstacles in checks:
            transformed = affinity.rotate(shape, -angle, origin=tuple(axis))
            for fixed_name, obstacle in obstacles:
                distance = transformed.distance(obstacle)
                if distance < closest[0]:
                    closest = (distance, angle, moving_name, fixed_name)
    reach = max(np.linalg.norm(v[:2]-axis) for part in moving for v in part['mesh'].vertices)
    between_samples = 2 * reach * math.sin(math.radians(step/4))
    return closest, step, float(closest[0]-between_samples)


def preview(fixed, moving, axis):
    image = Image.new('RGB', (1380, 970), '#f6f5f1')
    draw = ImageDraw.Draw(image)
    font_dir = Path('/System/Library/Fonts/Supplemental')
    try:
        heading = ImageFont.truetype(str(font_dir / 'Arial Bold.ttf'), 36)
        label = ImageFont.truetype(str(font_dir / 'Arial.ttf'), 25)
    except OSError:
        heading, label = ImageFont.load_default(size=36), ImageFont.load_default(size=25)
    draw.text((38, 27), 'Cambusa v20  /  Угол на алюминиевой стойке', font=heading, fill='#25352b')
    detail = [part for part in fixed if part['name'].startswith(
        ('Post-', 'Bracket-1', 'DIRAK-fixed-flat-1', 'Fixed-head-1', 'Fixed-nut-1', 'Slot-head-1'))]
    window = cube([-100, -100, 880], [100, 100, 1055])
    detail = [dict(part, mesh=tm.boolean.intersection([part['mesh'], window], engine='manifold'))
              if part['name'].startswith('Post-') else part for part in detail]
    image.paste(render(pose(fixed, moving, axis, 270), 760, 760, yaw=-42, pitch=15), (0, 95))
    image.paste(render(detail, 580, 730, yaw=36, pitch=25), (780, 110))
    draw.line((756, 112, 756, 852), fill='#c3c8c3', width=1)
    draw.text((38, 873), 'Левая створка  /  расчётное положение 270°', font=label, fill='#25352b')
    draw.text((788, 873), 'Узел со стороны каркаса', font=label, fill='#25352b')
    draw.text((788, 911), 'Стойка 30 × 30 мм · стальной уголок 6 мм', font=label, fill='#25352b')
    image.save(OUT / 'preview.png')


def main():
    reference = json.loads((REFERENCE / 'ПРОВЕРКА.json').read_text())
    axis = np.asarray(reference['axis_xy_mm'])
    centers = reference['hinge_centers_z_mm']
    fixed, moving = [], []
    source_parts = load_parts(REFERENCE / 'closed.glb')
    for name, mesh in source_parts.items():
        if name == 'Side-18-rebated':
            continue
        if name.startswith(('Door-', 'DIRAK-moving-')):
            color = 'rail' if name.startswith('DIRAK') else 'tray' if name.startswith(('Door-lip', 'Door-tray')) else 'door'
            add(moving, name, mesh, color, 'door')
        else:
            add(fixed, name, mesh, 'rail' if name.startswith('DIRAK') else 'wood')

    direct_post = cube([6, -15, POST_BOTTOM], [36, 15, POST_TOP])
    direct_overlap = overlap_volume(direct_post, source_parts['Door-face-18'])
    assert direct_overlap > 0

    # Use a full exterior box in the sweep. Only the narrow slot mouth
    # is represented in the export, so the walls of the selected profile
    # and the T-nut engagement must be verified separately.
    post_section = box(POST_LEFT, POST_FRONT, POST_LEFT+30, POST_FRONT+30)
    post_envelope = panel(post_section, 2, POST_BOTTOM, POST_TOP-POST_BOTTOM)
    slot_mouth = box(POST_SLOT_X-4, POST_FRONT-1, POST_SLOT_X+4, POST_FRONT+2.5)
    add(fixed, 'Post-30x30', panel(post_section.difference(slot_mouth), 2, POST_BOTTOM,
                                POST_TOP-POST_BOTTOM), 'frame')
    add(fixed, 'Side-12', cube([6, POST_FRONT+30, POST_BOTTOM], [18, 488, POST_TOP]), 'wood')
    bracket_section = box(6, -8, 12, POST_FRONT).union(box(6, POST_FRONT-6, 31, POST_FRONT))
    open_channels = 0
    for index, z in enumerate(centers, 1):
        blank = panel(bracket_section, 2, z-BRACKET_HEIGHT/2, BRACKET_HEIGHT)
        holes = [cylinder(0, 5.9, 12.1, 0, z+offset, BORE_RADIUS) for offset in HINGE_BOLT_OFFSETS]
        holes += [cylinder(1, POST_FRONT-6.1, POST_FRONT+.1, POST_SLOT_X, z+offset, BORE_RADIUS)
                  for offset in SLOT_BOLT_OFFSETS]
        bracket = cut(blank, holes)
        add(fixed, f'Bracket-{index}', bracket, 'bracket')
        for j, offset in enumerate(HINGE_BOLT_OFFSETS, 1):
            z_bolt = z + offset
            probe = cylinder(0, 1.9, 12.1, 0, z_bolt, 3.2)
            assert overlap_volume(probe, bracket) < .01
            assert overlap_volume(probe, source_parts[f'DIRAK-fixed-flat-{index}']) < .01
            open_channels += 1
            add(fixed, f'Fixed-head-{index}-{j}', cylinder(0, -4, 2, 0, z_bolt, HEAD_RADIUS), 'hardware')
            add(fixed, f'Fixed-nut-{index}-{j}', cylinder(0, 12, 20, 0, z_bolt, NUT_RADIUS), 'hardware')
        for j, offset in enumerate(SLOT_BOLT_OFFSETS, 1):
            z_bolt = z + offset
            probe = cylinder(1, POST_FRONT-6.1, POST_FRONT+.1, POST_SLOT_X, z_bolt, 3.2)
            assert overlap_volume(probe, bracket) < .01
            open_channels += 1
            driver = cylinder(1, -25, POST_FRONT-6.01, POST_SLOT_X, z_bolt, 6.5)
            assert overlap_volume(driver, bracket) < .01
            head = cylinder(1, POST_FRONT-12, POST_FRONT-6, POST_SLOT_X, z_bolt, HEAD_RADIUS)
            add(fixed, f'Slot-head-{index}-{j}', head, 'hardware')
        for j, (x, offset) in enumerate(zip(reference['door_holes_x_mm'], (-25.5, 25.5, 0)), 1):
            add(moving, f'Door-head-{index}-{j}', cylinder(1, -19.5, -13.5, x, z+offset, HEAD_RADIUS), 'hardware')
            add(moving, f'Door-nut-{index}-{j}', cylinder(1, 8.5, 14.5, x, z+offset, NUT_RADIUS), 'hardware')

    assert open_channels == 8
    endpoints = {}
    for angle in (0, 90, 180, 270):
        parts = {part['name']: part['mesh'] for part in pose(fixed, moving, axis, angle)}
        endpoints[str(angle)] = collision_pairs(parts)
    assert not any(endpoints.values()), endpoints

    conservative_fixed = [dict(part, mesh=post_envelope) if part['name'] == 'Post-30x30' else part
                          for part in fixed]
    closest, step, lower_bound = swept_clearance(conservative_fixed, moving, axis)
    assert lower_bound > 0, (closest, lower_bound)
    OUT.mkdir(exist_ok=True)
    for angle, file in ((0, 'closed.glb'), (270, 'open-270.glb')):
        assembly = pose(fixed, moving, axis, angle)
        path = OUT / file
        path.write_bytes(scene(assembly).export(file_type='glb'))
        exported = load_parts(path)
        assert set(exported) == {part['name'] for part in assembly}
        for part in assembly:
            assert np.allclose(exported[part['name']].vertices, part['mesh'].vertices, atol=.002)
        assert not collision_pairs(exported)

    report = {
        'iteration': 'cambusa-v20-aluminum-corner',
        'reference': 'cambusa-v19-corner',
        'axis_xy_mm_assumed': axis.tolist(),
        'door_wood_ligament_mm': reference['minimum_wood_ligament_to_near_door_bore_mm'],
        'direct_side_mount': {'profile_and_closed_door_width_overlap_mm': 14.5,
                              'bounding_box_intersection_with_drilled_door_face_mm3': round(direct_overlap, 1)},
        'offset_mount': {
            'profile_bounds_xy_mm': [[POST_LEFT, POST_FRONT], [POST_LEFT+30, POST_FRONT+30]],
            'front_slot_width_mm': 8,
            'brackets_per_hinge': 1,
            'bracket_bounds_mm': [25, 31, BRACKET_HEIGHT],
            'bracket_wall_mm': 6,
            'dirak_hole_centers': {'y_mm': 0, 'z_from_hinge_center_mm': HINGE_BOLT_OFFSETS},
            'slot_hole_centers': {'x_mm': POST_SLOT_X, 'z_from_hinge_center_mm': SLOT_BOLT_OFFSETS},
            'hinge_center_heights_mm': centers,
            'bore_diameter_mm': 2*BORE_RADIUS,
            'aligned_fixed_channels': open_channels,
            'head_envelopes_mm': {'diameter': 2*HEAD_RADIUS, 'depth': 6},
        },
        'endpoint_overlapping_volumes': endpoints,
        'sample_step_deg': step,
        'minimum_sample_clearance_mm': round(closest[0], 3),
        'closest_sample_deg_and_parts': closest[1:],
        'continuous_clearance_lower_bound_mm': round(lower_bound, 3),
        'scope': 'Single left-door corner. Assumed rigid-axis leaf and fastener envelopes. No pegboard.',
        'not_checked': ['Actual hinge knuckles and mounting offset', 'Actual profile and T-nut engagement',
                        'Full cabinet frame, tolerances, strength and loaded cycle test'],
        'release_for_machining': False,
    }
    (OUT / 'ПРОВЕРКА.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    preview(fixed, moving, axis)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
