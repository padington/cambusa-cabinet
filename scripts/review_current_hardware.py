"""Check candidate hardware against v28 without changing its cabinet assembly."""
import hashlib
import json

import numpy as np
import trimesh as tm

from build_aluminum_corner import cube, overlap_volume
from build_simple_left_door import ROOT, cabinet

OUT = ROOT / 'outputs/cambusa-v28-simple-left-door'


def source_mesh(name):
    meta = json.loads((ROOT / 'inputs/rsi-hardware-review.json').read_text())[name]
    path = ROOT / f'inputs/supplier-cad/{name}.step'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == meta['sha256']
    with np.load(ROOT / 'inputs/rsi-hardware-review.npz') as data:
        return tm.Trimesh(vertices=data[f'{name}-0-v'], faces=data[f'{name}-0-f'], process=False)


def main():
    fixed, _, _, _, _, _ = cabinet()
    meshes = {p['name']:p['mesh'] for p in fixed}
    corners = []
    for x in (4, 966):
        for y in (23, 470):
            block = source_mesh('rsi-2069')
            block.apply_translation(np.array([x, y, 1770]) - block.bounds[0])
            post = meshes[f'Post-{x}-{y}']
            cropped = tm.boolean.intersection([post, cube([x-1,y-1,11],
                                                          [x+31,y+31,1770])], engine='manifold')
            panels = []
            for name, mesh in meshes.items():
                if not name.startswith(('Back-infill-', 'Right-infill-', 'Left-pegboard-', 'Top-18')):
                    continue
                if np.min(np.minimum(block.bounds[1],mesh.bounds[1]) -
                          np.maximum(block.bounds[0],mesh.bounds[0])) <= .002:
                    continue
                volume = overlap_volume(block,mesh)
                if volume > .08:
                    panels.append(dict(part=name,volume_mm3=round(volume,3)))
            corners.append(dict(corner_xy_mm=[x,y],
                                current_post_overlap_mm3=round(overlap_volume(block,post),3),
                                shortened_post_overlap_mm3=round(overlap_volume(block,cropped),3),
                                affected_panels=panels))
    # Probe the foot body against the existing 12 mm placeholder clearance.
    foot = source_mesh('rsi-d49m8h30-simple')
    body = tm.boolean.intersection([foot,cube([-26,-22,-26],[26,13,26])], engine='manifold')
    transform = np.array([[1,0,0,19],[0,0,-1,38],[0,1,0,21],[0,0,0,1]],dtype=float)
    body.apply_transform(transform)
    report = dict(
        baseline='cambusa-v28-simple-left-door',
        cube_2069_probes=dict(
            note='Position probes preserve native CAD orientation. Fastener routing and assembly are pending.',
            top_corner_count=4, shorten_post_top_by_mm=30, placements=corners),
        feet=dict(quantity=4, sku='D49M8H30', base_diameter_mm=49,
                  body_height_below_thread_mm=34, existing_placeholder_height_mm=12,
                  current_post_vs_foot_body_overlap_mm3=round(overlap_volume(body,meshes['Post-4-23']),3),
                  mounting='M8 tapping in lower profile ends and locking nuts to be specified',
                  stock_post_lengths_pending=True),
        endcaps=dict(sku='4002',quantity=4, locations='Upper ends of the four full-height posts'),
        right_side=dict(current_blanks_depth_height_mm=[[432,312],[432,306],[432,337]],
                        current_thickness_mm=8, beam_count=2, beam_length_mm=417,
                        continuous_slot_panel_blank_depth_height_mm=[432,985],
                        continuous_panel_requires_new_shelf_supports=True),
        fabrication_release=False)
    assert all(c['current_post_overlap_mm3']>0 for c in corners)
    assert all(c['shortened_post_overlap_mm3']==0 for c in corners)
    assert report['feet']['current_post_vs_foot_body_overlap_mm3']>0
    (OUT/'hardware-review-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
