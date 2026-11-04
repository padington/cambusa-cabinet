"""Build a three-compartment lift-and-slide study using fixed pins and door-edge slots."""
from pathlib import Path
import json
import math

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union
import trimesh as tm

from build_aluminum_corner import ROOT, add, collision_pairs, cube, cut, cylinder, load_parts, panel, scene, swept_clearance
from build_glass_corner import glass_infill
from geometry import COLORS

OUT = ROOT / 'outputs/cambusa-v22-right-lift'
REFERENCE = ROOT / 'outputs/cambusa-v21-glass'
SECTIONS = [(818,1127), (1139,1448), (1460,1770)]
PIVOT_Y = 51
PIVOT_BELOW_TOP = 22
PIN_RADIUS = 3
SLOT_RADIUS = 3.65
SLOT_START, SLOT_END = 16,282
CLOSED_TILT = 6
DOOR_WIDTH, DOOR_HEIGHT = 448,300
X0 = 514
AXIS_LEFT = [-3.5,-19.]
COLORS.update(panel6=[151,113,80,255], handle=[184,190,193,255], pin=[205,153,63,255],
              guide=[117,145,152,255])


def leaf_parts():
    x1 = X0 + DOOR_WIDTH
    parts = []
    slot = LineString([(0,-SLOT_START),(0,-SLOT_END)]).buffer(SLOT_RADIUS,quad_segs=16)
    for label, start, cutter_x in [('L',X0,X0-.1),('R',x1-22,x1-6.5)]:
        stile = cube([start,-9,-DOOR_HEIGHT],[start+22,9,0])
        add(parts,f'Stile-{label}',cut(stile,[panel(slot,0,cutter_x,6.6)]),'door')
    add(parts,'Top-rail',cube([X0+22,-9,-14],[x1-22,9,0]),'door')
    add(parts,'Bottom-rail',cube([X0+22,-9,-300],[x1-22,9,-284]),'door')
    add(parts,'Plywood-infill-6',cube([X0+22,-9,-284],[x1-22,-3,-14]),'panel6')
    handle = box(-15,-301,-9,-289).union(box(-9,-301,9,-300))
    add(parts,'Edge-pull',panel(handle,0,X0+2,DOOR_WIDTH-4),'handle')
    return parts


def mechanism(bottom, ceiling):
    z = ceiling-PIVOT_BELOW_TOP
    parts = []
    for label, a, b, pin_lo, pin_hi in [('L',509,512,512,519),('R',964,966,957,964)]:
        add(parts,f'Pin-carrier-{label}',cube([a,44,z-9],[b,76,z+9]),'guide')
        add(parts,f'Pin-{label}',cylinder(0,pin_lo,pin_hi,PIVOT_Y,z,PIN_RADIUS),'pin')
    for label,a,b in [('L',509,526),('R',950,966)]:
        add(parts,f'Runner-{label}',cube([a,76,z-17.5],[b,365,z-9.5]),'guide')
    return parts


def state(progress):
    # First the door pivots about the front end of its slot, then it translates.
    angle = CLOSED_TILT+(90-CLOSED_TILT)*min(progress,1)
    pin_s = SLOT_START+(SLOT_END-SLOT_START)*max(0,progress-1)
    return angle,pin_s


def pose(part, ceiling, progress):
    angle,pin_s = state(progress)
    transform = tm.transformations.rotation_matrix(math.radians(-angle),[1,0,0])
    mesh = part['mesh'].copy().apply_translation([0,0,pin_s])
    mesh.apply_transform(transform).apply_translation([0,PIVOT_Y,ceiling-PIVOT_BELOW_TOP])
    return dict(part,mesh=mesh)


def named(parts):
    return {part['name']:part['mesh'] for part in parts}


def full_fixed():
    parts,left = [],[]
    original = load_parts(REFERENCE/'closed.glb')
    for name,mesh in original.items():
        if name in ('Bottom-18','Top-18','Back-12','Opposite-side-18','Post-30x30') or name.startswith(
            ('Left-glass-','Glazing-','Glass-pad-')
        ):
            continue
        if name.startswith(('Door-','DIRAK-moving-')):
            mat='rail' if name.startswith(('Door-head','Door-nut','DIRAK')) else 'door'
            add(left,name,mesh,mat)
        else:
            if name.startswith(('Center-','Left-shelf-')):
                mesh.vertices[:,1] = np.minimum(mesh.vertices[:,1],458)
            if name.startswith('Center-'):
                mesh.vertices[:,1] = np.where(mesh.vertices[:,1] < 104, 23, mesh.vertices[:,1])
                mesh.vertices[:,2] = np.minimum(mesh.vertices[:,2],1770)
            mat='rail' if name.startswith(('DIRAK','Fixed-','Slot-head-')) else 'frame' if name.startswith('Bracket') else 'wood'
            add(parts,name,mesh,mat)
    parts += glass_infill(cube([6,53,818],[18,470,1770]))
    add(parts,'Right-panel',cube([982,53,818],[994,470,1770]),'wood')
    add(parts,'Back-12',cube([18,458,818],[982,470,1770]),'back')
    add(parts,'Top-18',cube([34,53,1782],[966,470,1800]),'wood')
    add(parts,'Right-roof',cube([509,53,1770],[966,458,1782]),'wood')
    for x in (4,966):
        for y in (23,470):
            post = original['Post-30x30'].copy()
            post.vertices[:,2] = 12+(post.vertices[:,2]-818)*(1788/964)
            post.apply_translation([x-4,y-23,0])
            add(parts,f'Post-{x}-{y}',post,'frame')
            add(parts,f'Foot-{x}-{y}',cube([x+1,y+1,0],[x+29,y+29,12]),'frame')
    for level,z in [('lower',72),('body',770),('top',1770)]:
        add(parts,f'Beam-{level}-rear',cube([34,470,z],[966,500,z+30]),'frame')
        if level!='lower':
            add(parts,f'Beam-{level}-front',cube([34,23,z],[966,53,z+30]),'frame')
        for x in (4,966):
            add(parts,f'Beam-{level}-side-{x}',cube([x,53,z],[x+30,470,z+30]),'frame')
    notches=unary_union([box(x,y,x+30,y+30) for x in (4,966) for y in (23,470)])
    add(parts,'Bottom-18',panel(box(4,0,996,500).difference(notches),2,800,18),'wood')
    for index,(bottom,ceiling) in enumerate(SECTIONS,1):
        if index<3:
            outline = box(509,23,966,458).union(box(966,53,982,458))
            add(parts,f'Right-floor-{index}',panel(outline,2,ceiling,12),'wood')
        # At the outer side the rear part of the runner is backed by this cheek.
        add(parts,f'Right-cheek-{index}',cube([966,76,ceiling-44],[982,365,ceiling-12]),'wood')
        parts += [dict(p,name=f'{p["name"]}-{index}') for p in mechanism(bottom,ceiling)]
    return parts,left


def isolated():
    bottom,ceiling=SECTIONS[0]
    parts=mechanism(bottom,ceiling)
    add(parts,'Left-cheek',cube([497,23,bottom],[509,388,ceiling]),'wood')
    add(parts,'Right-cheek',cube([966,23,bottom],[982,388,ceiling]),'wood')
    add(parts,'Roof',cube([497,23,ceiling],[982,388,ceiling+12]),'wood')
    add(parts,'Sill',cube([497,23,bottom-12],[982,388,bottom]),'wood')
    return parts


def yz(mesh):
    triangles=(Polygon(t[:,1:]) for t in mesh.triangles)
    return unary_union([p for p in triangles if p.area>1e-5])


def audit_leaf(leaf,fixed,ceiling):
    obstacles=[]
    for part in fixed:
        if part['name'].startswith(('Pin-L','Pin-R')):
            continue
        bounds=part['mesh'].bounds
        if bounds[1,0] > X0 and bounds[0,0] < X0+DOOR_WIDTH:
            obstacles.append((part['name'],bounds[:,0],yz(part['mesh'])))
    candidates=[]
    for part in leaf:
        low,high=part['mesh'].bounds[:,0]
        matching=[(name,shape) for name,(a,b),shape in obstacles if min(high,b)>max(low,a)+.001]
        if matching:
            candidates.append((part['name'],yz(part['mesh']),matching))
    best=(math.inf,None,None,None)
    # Nearest sample is at most 0.05 degrees / 0.05 mm away.
    steps=(840,2660)
    for segment,n in enumerate(steps):
        for i in range(n+1):
            progress=segment+i/n
            angle,pin_s=state(progress)
            c,s=math.cos(math.radians(angle)),math.sin(math.radians(angle))
            matrix=(c,s,-s,c,PIVOT_Y+s*pin_s,ceiling-PIVOT_BELOW_TOP+c*pin_s)
            for part,footprint,targets in candidates:
                shape=affinity.affine_transform(footprint,matrix)
                for name,obstacle in targets:
                    gap=shape.distance(obstacle)
                    if gap<best[0]:
                        best=(gap,progress,part,name)
    max_shift=max(2*math.hypot(DOOR_HEIGHT-SLOT_START+1,15)*math.sin(math.radians(.025)),.05)
    return best,float(best[0]-max_shift)


def export(path,parts):
    export=scene(parts)
    for node in export.graph.nodes_geometry:
        if node!='Left-glass-6':
            continue
        _,geom=export.graph[node]
        export.geometry[geom].visual=tm.visual.TextureVisuals(
            material=tm.visual.material.PBRMaterial(baseColorFactor=[177,220,223,75],roughnessFactor=.18,
                                                    alphaMode='BLEND',doubleSided=True))
    path.write_bytes(export.export(file_type='glb'))
    assert set(load_parts(path))==set(named(parts))


def main():
    OUT.mkdir(exist_ok=True)
    leaf=leaf_parts()
    fixed,left=full_fixed()
    export(OUT/'door-leaf.glb',leaf)
    close_parts=isolated()
    _,ceiling=SECTIONS[0]
    # Verify pins at both rounded ends and at several positions along the channel.
    for progress in (0,.5,1,1.25,1.5,1.75,2):
        expected=close_parts+[pose(p,ceiling,progress) for p in leaf]
        assert not collision_pairs(named(expected)),(progress,collision_pairs(named(expected)))
    result={}
    for progress,label in [(0,'closed'),(1,'raised'),(2,'stowed')]:
        parts=close_parts+[pose(p,ceiling,progress) for p in leaf]
        export(OUT/f'mechanism-{label}.glb',parts)
        cabinet=fixed+left
        for index,(_,top) in enumerate(SECTIONS,1):
            cabinet += [dict(pose(p,top,progress),name=f'{p["name"]}-{index}') for p in leaf]
        result[label]=collision_pairs(named(cabinet))
        assert not result[label],result[label]
        if label!='raised':
            export(OUT/f'cabinet-{label}.glb',cabinet)
    clearance=[audit_leaf(leaf,fixed,top) for _,top in SECTIONS]
    assert all(bound>0 for _,bound in clearance),clearance
    left_min,_,left_bound=swept_clearance(fixed,left,np.asarray(AXIS_LEFT))
    assert left_bound>0,(left_min,left_bound)
    record={
        'section_clear_height_mm':[hi-lo for lo,hi in SECTIONS],
        'door_width_height_mm':[DOOR_WIDTH,DOOR_HEIGHT],
        'infill_thickness_mm':6,
        'pin_diameter_mm':6,
        'channel_width_mm':2*SLOT_RADIUS,
        'channel_depth_mm':6.5,
        'channel_center_limits_from_top_edge_mm':[SLOT_START,SLOT_END],
        'pivot_depth_from_cabinet_front_mm':PIVOT_Y,
        'pivot_below_section_roof_mm':PIVOT_BELOW_TOP,
        'slide_mm':SLOT_END-SLOT_START,
        'closed_tilt_from_vertical_deg':CLOSED_TILT,
        'projection_from_cabinet_front_raised_mm':DOOR_HEIGHT-SLOT_START-PIVOT_Y,
        'all_cabinet_endpoint_collisions':result,
        'closest_sample_mm_by_compartment':[round(closest[0],3) for closest,_ in clearance],
        'body_clearance_bound_mm_by_compartment':[round(bound,3) for _,bound in clearance],
        'left_door_continuous_clearance_bound_mm':round(left_bound,3),
        'release_for_machining':False,
    }
    (OUT/'ПРОВЕРКА.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(record,ensure_ascii=False))


if __name__=='__main__':
    main()
