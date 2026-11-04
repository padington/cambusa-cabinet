"""Replace the left-side infill in the v20 hinge test with captured glazing."""
import json
from pathlib import Path

import numpy as np
from PIL import Image
from shapely.geometry import box
import trimesh as tm

from build_aluminum_corner import (
    ROOT, add, collision_pairs, cube, load_parts, panel, pose, scene, swept_clearance,
)
from geometry import COLORS, render

SOURCE = ROOT / 'outputs/cambusa-aluminum-v20-corner'
OUT = ROOT / 'outputs/cambusa-v21-glass'
GLASS = 'Left-glass-6'
COLORS.update(glass=[172, 218, 221, 100], rubber=[47, 51, 51, 255])


def glass_infill(side):
    """Model the retaining borders and two pads that carry the glass weight."""
    (_, front, bottom), (_, rear, top) = side.bounds
    parts = []
    opening = box(front, bottom, rear, top)
    glass_outline = box(front+3, bottom+4, rear-3, top-4)
    clear_opening = box(front+10, bottom+10, rear-10, top-10)
    gasket = glass_outline.difference(clear_opening)
    add(parts, GLASS, panel(glass_outline, 0, 8, 6), 'glass')
    # Removable inner stop and fixed outer stop, with no metal-glass contact.
    for name, x, thickness, gasket_x in (('outer', 6, 1, 7), ('inner', 15, 3, 14)):
        add(parts, f'Glazing-stop-{name}', panel(opening.difference(clear_opening), 0, x, thickness), 'frame')
        add(parts, f'Glazing-gasket-{name}', panel(gasket, 0, gasket_x, 1), 'rubber')
    for index, y in enumerate((front+72, rear-102), 1):
        add(parts, f'Glass-pad-{index}', cube([7, y, bottom], [15, y+30, bottom+4]), 'rubber')
    return parts


def main():
    prior = json.loads((SOURCE / 'ПРОВЕРКА.json').read_text())
    axis = np.array(prior['axis_xy_mm_assumed'])
    parts = load_parts(SOURCE / 'closed.glb')
    glazing = glass_infill(parts.pop('Side-12'))
    fixed, moving = list(glazing), []
    for name, mesh in parts.items():
        target = moving if name.startswith(('Door-', 'DIRAK-moving-')) else fixed
        color = 'wood'
        if name.startswith('Door-'):
            color = 'hardware' if name.startswith(('Door-head-', 'Door-nut-')) else 'door'
        elif name.startswith('DIRAK-'):
            color = 'rail'
        elif name.startswith(('Fixed-', 'Slot-head-')):
            color = 'hardware'
        elif name.startswith(('Post-', 'Bracket-')):
            color = 'frame'
        add(target, name, mesh, color, 'door' if target is moving else 'body')

    OUT.mkdir(exist_ok=True)
    endpoints = {}
    for angle in (0, 90, 180, 270):
        assembly = pose(fixed, moving, axis, angle)
        meshes = {part['name']: part['mesh'] for part in assembly}
        endpoints[str(angle)] = collision_pairs(meshes)
        if angle in (0, 270):
            export = scene(assembly)
            _, geometry = export.graph[GLASS]
            export.geometry[geometry].visual = tm.visual.TextureVisuals(
                material=tm.visual.material.PBRMaterial(
                    baseColorFactor=[177, 220, 223, 75], roughnessFactor=.18, alphaMode='BLEND', doubleSided=True,
                )
            )
            path = OUT / ('closed.glb' if angle == 0 else 'open-270.glb')
            path.write_bytes(export.export(file_type='glb'))
            reopened = load_parts(path)
            assert set(meshes) == set(reopened)
            assert not collision_pairs(reopened)
    assert not any(endpoints.values()), endpoints
    image = Image.new('RGB', (1400, 680), '#f6f5f1')
    for offset, angle in ((0, 0), (700, 270)):
        assembly = pose(fixed, moving, axis, angle)
        opaque = render(assembly, 700, 680, yaw=-45, pitch=13)
        interior = render([part for part in assembly if part['name'] != GLASS],
                          700, 680, yaw=-45, pitch=13)
        image.paste(Image.blend(interior, opaque, .24), (offset, 0))
    image.save(OUT / 'preview.png')

    closest, step, glazing_clearance = swept_clearance(glazing, moving, axis)
    glass = next(part['mesh'] for part in glazing if part['name'] == GLASS)
    dims = glass.extents[[1, 2, 0]].tolist()
    assert glazing_clearance > 0
    report = {
        'model': 'cambusa-v21-glass',
        'basis': 'cambusa-v20-aluminum-corner',
        'scope': 'Geometric comparison of the left corner, not a full frame assembly',
        'glass_depth_height_thickness_mm': dims,
        'glazing_support_pads': 2,
        'gasket_contact_perimeter_mm_per_face': 2 * (dims[0] + dims[1]),
        'endpoint_overlapping_volumes': endpoints,
        'glazing_sample_step_deg': step,
        'glazing_closest_sample_mm_deg_moving_fixed': closest,
        'glazing_continuous_clearance_lower_bound_mm': round(glazing_clearance, 3),
        'whole_corner_lower_bound_mm': min(prior['continuous_clearance_lower_bound_mm'], round(glazing_clearance, 3)),
        'release_for_machining': False,
    }
    (OUT / 'ПРОВЕРКА.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
