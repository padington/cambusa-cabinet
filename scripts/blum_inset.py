"""Blum inset hinge layout and four-bar motion read from its factory CAD.

The commercial mechanism is trusted internally. Three readable factory solids
are retained. The cup, housing and plate are dimensional representations, so
this module does not claim a complete reconstruction of the supplier B-rep.
"""
import json
import math

import numpy as np
import trimesh as tm
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

from build_aluminum_corner import add, cube, cut, panel
from build_frame_joinery import bore
from build_simple_left_door import ROOT

SPEC = json.loads((ROOT / 'inputs/blum-71b3750-linkage.json').read_text())
P, Q = (np.array(SPEC[k]) for k in ('fixed_p', 'fixed_q'))
B, A = (np.array(SPEC[k]) for k in ('moving_b', 'moving_a'))
OFFSET = np.array(SPEC['world_offset_xy'])
CENTERS = SPEC['centers_z_mm']
MAX_ANGLE = SPEC['maximum_angle_deg']


def rotation(angle):
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, -s], [s, c]])


def native_pose(degrees):
    matrix = rotation(np.radians(degrees))
    delta = matrix @ (A - B)
    center = Q - delta
    span = center - P
    distance = np.linalg.norm(span)
    unit = span / distance
    first_radius, second_radius = np.linalg.norm(B - P), np.linalg.norm(A - Q)
    along = (first_radius**2 - second_radius**2 + distance**2) / (2 * distance)
    height_squared = first_radius**2 - along**2
    assert height_squared > 0, (degrees, height_squared)
    initial_span = Q - (A - B) - P
    initial_arm = B - P
    side = np.sign(initial_span[0] * initial_arm[1] - initial_span[1] * initial_arm[0])
    moving_b = P + along * unit + side * math.sqrt(height_squared) * np.array([-unit[1], unit[0]])
    moving_a = moving_b + delta
    return matrix, moving_b, moving_a


def world_xy(point, offset_y=0):
    return OFFSET + [0,offset_y] + np.asarray(point) * [-1, 1]


def transform_for(kind, degrees, offset_y=0):
    matrix, b, a = native_pose(degrees)
    if kind == 'cup':
        angle = -np.radians(degrees)
        anchor, position = world_xy(B,offset_y), world_xy(b,offset_y)
    else:
        origin, old, new = (P, B, b) if kind == 'link2' else (Q, A, a)
        before, after = (old - origin) * [-1, 1], (new - origin) * [-1, 1]
        angle = np.arctan2(after[1], after[0]) - np.arctan2(before[1], before[0])
        anchor = position = world_xy(origin,offset_y)
    transform = np.eye(4)
    transform[:2, :2] = rotation(angle)
    transform[:2, 3] = position - transform[:2, :2] @ anchor
    return transform


def posed(parts, degrees, offset_y=0):
    result = []
    for part in parts:
        if not part.get('motion'):
            result.append(part)
            continue
        transform = transform_for(part['motion'], degrees,offset_y)
        result.append(dict(part, mesh=part['mesh'].copy().apply_transform(transform),
                           thread_targets={name:region.copy().apply_transform(transform)
                                           for name,region in part.get('thread_targets', {}).items()}))
    return result


def world_mesh(mesh, center, offset_y=0):
    transform = np.array([[-1, 0, 0, OFFSET[0]], [0, 1, 0, OFFSET[1]+offset_y],
                          [0, 0, -1, center], [0, 0, 0, 1]], dtype=float)
    return mesh.copy().apply_transform(transform)


def dimensional_cup(center):
    shell = cut(bore([58.5, 41, center], [0, -1, 0], 0, 13, 17.5),
                [bore([58.5, 41, center], [0, -1, 0], -.1, 12.4, 16.9)])
    outline = Point(58.5, center).buffer(18.5, quad_segs=16).union(
        box(57, center - 28.5, 79, center + 28.5))
    flange = panel(outline, 1, 41, 3.2)
    holes = [bore([68, 41, z], [0, 1, 0], -.1, 3.3, 1.85)
             for z in (center - 22.5, center + 22.5)]
    return tm.boolean.union([shell, cut(flange, holes)], engine='manifold')


def wood_screw(origin, direction, length):
    shank = bore(origin, direction, 0, length, 1.75)
    head = bore(origin, direction, -2.2, 0, 3.5)
    return tm.boolean.union([shank, head], engine='manifold')


def build(fixed, cup_spacer_mm=0):
    moving, door_tools, pegboard_tools, machining = [], [], [], []
    with np.load(ROOT / 'inputs/blum-71b3750-readable.npz') as data:
        native = {i:tm.Trimesh(vertices=data[f'blum-71b3750-{i}-v'],
                               faces=data[f'blum-71b3750-{i}-f'], process=True)
                  for i in (0, 2, 3)}
    for index, center in enumerate(CENTERS, 1):
        add(fixed, f'Blum-{index}-factory-clip', world_mesh(native[0], center,cup_spacer_mm), 'handle', hinge=index)
        for number in (2, 3):
            add(moving, f'Blum-{index}-factory-link{number}',
                world_mesh(native[number], center,cup_spacer_mm), 'handle', hinge=index, motion=f'link{number}')
        add(moving, f'Blum-{index}-cup-envelope', dimensional_cup(center).apply_translation([0,cup_spacer_mm,0]),
            'handle', hinge=index, motion='cup')
        if cup_spacer_mm:
            # 70T3507.21 is a non-stackable 1.5 mm factory cup spacer.
            # The outline is a 58 x 39 dimensional envelope, not its CAD.
            assert cup_spacer_mm==1.5
            outline=Point(58.5,center).buffer(18.5,quad_segs=16).union(
                box(57,center-29,79,center+29))
            spacer_tools=[bore([58.5,41,center],[0,1,0],-.1,1.6,17.6)]
            spacer_tools += [bore([68,41,z],[0,1,0],-.1,1.6,1.85)
                             for z in (center-22.5,center+22.5)]
            add(moving,f'Blum-{index}-70T3507.21-envelope',
                cut(panel(outline,1,41,1.5),spacer_tools),
                'frame',hinge=index,motion='cup')
        path = LineString([tuple(P), tuple(Q), (-7, 4)])
        housing = panel(path.buffer(2.4, quad_segs=8), 2, -8.3, 16.6)
        add(fixed, f'Blum-{index}-housing-envelope', world_mesh(housing, center,cup_spacer_mm), 'handle', hinge=index)
        # The plate envelope retains the mounting surface and the 32 mm
        # fixing pattern of the factory 175H3100 CAD.
        plate = cube([34, 57.285+cup_spacer_mm, center - 9.325], [35.25, 100.955+cup_spacer_mm, center + 9.325])
        spacer = cube([28, 54+cup_spacer_mm, center - 12], [34, 105+cup_spacer_mm, center + 12])
        plate_holes, spacer_holes = [], []
        for y in (62.5+cup_spacer_mm,94.5+cup_spacer_mm):
            plate_holes.append(bore([34, y, center], [1, 0, 0], -.1, 1.4, 2.8))
            spacer_holes.append(bore([28, y, center], [1, 0, 0], -.1, 6.1, 1.85))
            pegboard_tools.append(bore([28, y, center], [-1, 0, 0], -.1, 12.85, 1.25))
            add(fixed, f'Blum-{index}-plate-screw-{y}', wood_screw([35.25,y,center], [-1,0,0], 20),
                'fastener', hinge=index, thread_targets={
                    'Left-pegboard-18':bore([28,y,center], [-1,0,0], -.01, 12.8, 1.8)})
            machining.append(['Left-pegboard-18','pilot from inner face', y-53.5, center-800, 2.5,12.8])
        add(fixed, f'Blum-{index}-plate-envelope', cut(plate, plate_holes), 'handle', hinge=index)
        add(fixed, f'Blum-{index}-spacer-6', cut(spacer, spacer_holes), 'angle')
        door_tools.append(bore([58.5,41,center], [0,-1,0], -.1,13.05-cup_spacer_mm,17.55))
        machining.append(['Left-door-face-18','cup from back',22.5,center-803,35.1,13.05-cup_spacer_mm])
        for z in (center-22.5,center+22.5):
            door_tools.append(bore([68,41,z],[0,-1,0],-.1,12.85-cup_spacer_mm,1.25))
            add(moving, f'Blum-{index}-cup-screw-{z}', wood_screw([68,44.2+cup_spacer_mm,z],[0,-1,0],16),
                'fastener', hinge=index, motion='cup', thread_targets={
                    'Left-door-face-18':bore([68,41,z],[0,-1,0],-.01,12.81-cup_spacer_mm,1.8)})
            machining.append(['Left-door-face-18','pilot from back',32,z-803,2.5,12.8-cup_spacer_mm])
    grip = panel(LineString([(470,1250),(470,1322)]).buffer(9,quad_segs=16),1,22.9,12.1)
    add(moving,'Left-door-face-18',cut(cube([36,23,803],[488,41,1767]),door_tools+[grip]),
        'door',motion='cup')
    pegboard = next(p for p in fixed if p['name']=='Left-pegboard-18')
    pegboard['mesh'] = cut(pegboard['mesh'],pegboard_tools)
    machining.append(['Left-door-face-18','blind grip from front',434,483,18,12])
    return moving, machining


def linkage_residual(degrees):
    _, b, a = native_pose(degrees)
    return max(abs(np.linalg.norm(b-P)-np.linalg.norm(B-P)),
               abs(np.linalg.norm(a-Q)-np.linalg.norm(A-Q)),
               abs(np.linalg.norm(a-b)-np.linalg.norm(A-B)))
