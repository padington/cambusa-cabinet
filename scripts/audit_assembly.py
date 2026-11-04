"""Independently inspect exported GLBs against the v18 part list and assembly pose."""
from collections import Counter
from itertools import combinations, product
import json
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'outputs/cambusa-frame-v18'


def load_parts(path):
    scene = trimesh.load(path, force='scene')
    parts = {}
    for node in scene.graph.nodes_geometry:
        transform, geometry = scene.graph[node]
        mesh = scene.geometry[geometry].copy()
        mesh.apply_transform(transform)
        mesh.vertices = np.round(mesh.vertices[:, [0, 2, 1]] * [1000, -1000, 1000], 3)
        if node in parts:
            raise ValueError(f'Повтор ID: {node}')
        parts[node] = mesh
    return parts


def expected_ids():
    corners = [f'{prefix}-{x}-{y}' for prefix,x,y in product(('Post','Foot'),(0,970),(0,470))]
    beams = [f'Beam-{level}-{end}' for level,end in product(('lower','body','top'),('rear','front','side-0','side-970'))
             if (level,end) != ('lower','front')]
    body = ['B00-bottom-notched','B01-top-inset','B02-left-pegboard','B03-right-side','B04-back','B05-divider',
            'B10-left-shelf','B11-left-shelf','B20-right-shelf','B21-right-shelf']
    doors = [f'{side}-{name}' for side,name in product(('L','R'),(
        'jamb','hinge-stile','meeting-stile','top-rail','bottom-rail','front-panel',
        'shelf-1','shelf-2','shelf-3','lip-1','lip-2','lip-3',
    ))]
    angles = [f'ShelfAngle-{shelf}-{side}' for shelf,side in product(('B10','B11','B20','B21'),('inner','outer'))]
    return set(corners + beams + body + doors + angles)


def intersections(parts):
    collisions = []
    contacts = []
    candidates = 0
    for (aid,a),(bid,b) in combinations(sorted(parts.items()),2):
        overlap = np.minimum(a.bounds[1],b.bounds[1]) - np.maximum(a.bounds[0],b.bounds[0])
        if np.min(overlap) < -.002:
            continue
        if np.min(overlap) <= .002:
            contacts.append([aid,bid])
            continue
        candidates += 1
        intersection = trimesh.boolean.intersection([a,b],engine='manifold')
        volume = abs(float(intersection.volume)) if len(intersection.faces) else 0.
        if volume > .08:
            collisions.append({'parts':[aid,bid], 'volume_mm3':round(volume,3)})
    return {'narrow_phase_pairs':candidates,'overlapping_volumes':collisions,
            'bounding_box_contacts_for_review':contacts}


def main():
    closed, opened = [load_parts(MODEL / f'{pose}.glb') for pose in ('closed','open')]
    expected = expected_ids()
    plan = json.loads((MODEL/'planning/plan.json').read_text())
    counts = Counter(item['id'] for item in plan['parts'])
    plan_sizes = {item['id']: item['dimensions_mm'] for item in plan['parts']}
    checks = {'positions':{},'poses':{},'scope':'Exported geometry, both static states'}
    assert expected == set(closed) == set(opened)
    assert counts == Counter({name:1 for name in expected})
    assert all(mesh.is_volume for p in (closed,opened) for mesh in p.values())
    assert all(np.allclose(mesh.extents,plan_sizes[name],atol=.011) for name,mesh in closed.items())
    for name,mesh in closed.items():
        same_pose = not (name.startswith(('L-','R-')) and not name.endswith('-jamb'))
        vertices = mesh.vertices.copy()
        if not same_pose:
            vertices[:,0] = (137.5 if name.startswith('L-') else 1862.5) - vertices[:,0]
            vertices[:,1] = -5 - vertices[:,1]
        assert np.allclose(vertices,opened[name].vertices,atol=.002), name
    pegboard = closed['B02-left-pegboard']
    right = closed['B03-right-side']
    assert np.allclose(pegboard.bounds,[[6,31,800],[18,469,1769]])
    assert np.allclose(right.bounds,[[982,31,800],[994,469,1769]])
    # An extruded panel's genus equals its number of through holes.
    hole_count = (2 - pegboard.euler_number)//2
    assert hole_count == 171 and right.euler_number == 2
    checks['positions'] = {'all_exported_ids_and_sizes_match_plan':True,
                           'unchanged_cabinet_and_correct_door_endpoint':True,
                           'pegboard_side':'left','pegboard_through_holes':hole_count}
    for shelf in ('B10','B11','B20','B21'):
        board = next(mesh for name,mesh in closed.items() if name.startswith(shelf+'-'))
        assert abs(board.extents[2] - 12) < .002
        for position in ('inner','outer'):
            angle = closed[f'ShelfAngle-{shelf}-{position}']
            assert abs(angle.bounds[1,2] - board.bounds[0,2]) < .002
            overlap = np.minimum(angle.bounds[1,:2],board.bounds[1,:2])-np.maximum(angle.bounds[0,:2],board.bounds[0,:2])
            assert min(overlap) > 19.99
    checks['positions']['each_shelf_bears_on_two_modeled_angles'] = True
    checks['part_count'] = len(expected)
    for name,model in [('closed',closed),('open_180_schematic',opened)]:
        checks['poses'][name] = intersections(model)
    checks['volume_threshold_mm3'] = .08
    checks['outside_scope'] = [
        'Actual hinge linkage and its complete swing',
        'Fasteners, corner brackets, catches, anti-tip attachment and retainers',
        'Pegs and loads placed in the cabinet or on the pegboard',
        'Tolerance stacks, loads and physical assembly',
    ]
    (MODEL/'АУДИТ-3D.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    assert all(not pose['overlapping_volumes'] for pose in checks['poses'].values()), checks['poses']
    print(f'{len(expected)} parts; {hole_count} through-holes on left; no modeled volume intersections')


if __name__ == '__main__':
    main()
