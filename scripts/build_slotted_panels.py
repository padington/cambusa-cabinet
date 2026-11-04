"""Cambusa v24. Profile sections from STEP, slotted infill and shelf hardware."""
import csv
import json

import numpy as np
import trimesh as tm
from shapely import affinity
from shapely.geometry import Polygon, box

from build_aluminum_corner import add, collision_pairs, cube, cut, cylinder, overlap_volume, panel
from build_aluminum_corner import pose as swing_left
from build_aluminum_corner import swept_clearance
from build_right_lift import AXIS_LEFT, ROOT, SECTIONS, audit_leaf, export, full_fixed, leaf_parts, named, pose
from geometry import COLORS

OUT = ROOT / 'outputs/cambusa-v24-slotted-panels'
SOURCE = json.loads((ROOT / 'inputs/ob3030-cad-sections.json').read_text())
PROFILE = Polygon(SOURCE['profile']['outer'], SOURCE['profile']['holes'])
NUT = Polygon(SOURCE['nut']['outer'])
COLORS.update(angle=[51,128,141,255], fastener=[197,165,91,255], panel8=[141,96,65,255])
ENGAGE, THICKNESS = 7.5, 8.0
LOWER_CLEARANCE = 140
OUTER_Y = (27, 496)
ENDS_Y = (38, 485)
SCREW_OFFSETS = (12, 34)


def profile_mesh(low, high):
    lengths = high-low
    axis = int(np.argmax(lengths))
    others = [i for i in range(3) if i != axis]
    cross = affinity.translate(PROFILE, *((low[others]+high[others])/2))
    return panel(cross, axis, low[axis], lengths[axis])


def panel_blank(outline, axis, center, notches=()):
    blank = panel(outline, axis, center-THICKNESS/2, THICKNESS)
    return cut(blank, notches) if notches else blank


def cross_hole(start, end, y, z, radius1, radius2=None):
    if radius2 is None:
        return cylinder(0, min(start,end), max(start,end), y,z,radius1)
    sign = np.sign(end-start)
    sec = np.array([[0,0],[radius1,0],[radius2,abs(end-start)],[0,abs(end-start)]])
    mesh = tm.creation.revolve(sec, sections=48)
    mesh.apply_transform(tm.transformations.rotation_matrix(sign*np.pi/2,[0,1,0]))
    mesh.apply_translation([start,y,z])
    return mesh


def countersunk_screw(x, inward, y, z, length):
    head = cross_hole(x,x-inward*2.5,y,z,5,2.5)
    shank = cross_hole(x-inward*2.5,x-inward*length,y,z,2.5)
    return tm.boolean.union([head,shank],engine='manifold')


def angle(profile_x, inward, y0, y1, z, holes):
    def span(offset):
        return sorted((profile_x, profile_x+inward*offset))
    a,b=span(3)
    c,d=span(30)
    flange = cube([c,y0,z-3],[d,min(y1,478),z])
    web = cube([a,y0,z-40],[b,y1,z])
    part = tm.boolean.union([web,flange],engine='manifold')
    face=profile_x+inward*3
    for y,h in holes:
        through=cross_hole(profile_x-inward*.1,face+inward*.1,y,h,2.7)
        seat=cross_hole(face+inward*.02,face-inward*2.33,y,h,5.02,2.7)
        part=cut(part,[tm.boolean.union([through,seat],engine='manifold')])
    return part


def nut_at(x, inward, y, z):
    # Neck faces the entry, shoulder sits 2.2 mm behind the profile face.
    coords=[(x-inward*(v+4.9645301),y+u) for u,v in NUT.exterior.coords]
    body = panel(Polygon(coords), 2, z-5,20)
    body = cut(body, [cylinder(0,x-10,x+10,y,z,2.52)])
    return body


def cabinet():
    fixed,left = full_fixed()
    fixed=[p for p in fixed if p['name'] not in ('Right-panel','Back-12','Bottom-18') and
           not p['name'].startswith(('Left-shelf-', 'Right-floor-'))]
    divider = next(p for p in fixed if p['name']=='Center-18')
    mortises, notches, new, panel_cuts = [], [], [], []
    for part in fixed:
        mesh=part['mesh']
        if part['name'].startswith(('Post-','Beam-')):
            part['mesh']=profile_mesh(*mesh.bounds)
        if part['name'].startswith('Beam-lower-'):
            part['mesh'].apply_translation([0,0,LOWER_CLEARANCE-mesh.bounds[0,2]])
        if part['name'].startswith('Right-cheek-'):
            mesh.vertices[:,0]=np.minimum(mesh.vertices[:,0],976.5)

    shelf_rows=(('Left',1,1138,18),('Left',2,1458,18),
                ('Right',1,1127,12),('Right',2,1448,12))
    for side,index,z,thickness in shelf_rows:
        left_side=side=='Left'
        tag=f'{side}-{index}'
        x0,x1,y0=(35,490,103) if left_side else (509,966,23)
        add(new,f'Shelf-{tag}',cube([x0,y0,z],[x1,458,z+thickness]),'wood')
        panel_cuts.append([f'Shelf-{tag}',x1-x0,458-y0,thickness,1])
        out_x, inner_x, sign=(34,491,1) if left_side else (966,509,-1)
        outer_holes=[(y,z-dz) for y in ENDS_Y for dz in SCREW_OFFSETS]
        inner_holes=[(y,z-20) for y in ((120,265,410) if left_side else (145,290,435))]
        add(new,f'Angle-Outer-{tag}',angle(out_x,sign,*OUTER_Y,z,outer_holes),'angle')
        add(new,f'Angle-Inner-{tag}',angle(inner_x,-sign,106 if left_side else 70,455,z,inner_holes),'angle')
        for idx,(y,h) in enumerate(outer_holes,1):
            screw=countersunk_screw(out_x+sign*3,sign,y,h,10)
            add(new,f'M5x10-{tag}-{idx}',screw,'fastener')
            add(new,f'RSI-5048-{tag}-{idx}',nut_at(out_x,sign,y,h),'fastener')
        for idx,(y,h) in enumerate(inner_holes,1):
            sign_in=-sign
            screw=countersunk_screw(inner_x+sign_in*3,sign_in,y,h,12)
            blank=cross_hole(inner_x,inner_x-sign_in*12,y,h,5)
            add(new,f'M5x12-{tag}-{idx}',screw,'fastener')
            add(new,f'Insert-M5-{tag}-{idx}',cut(blank,[cross_hole(inner_x+sign_in*.1,inner_x-sign_in*12.1,y,h,2.52)]),'fastener')
            mortises.append(cross_hole(inner_x+sign_in*.1,inner_x-sign_in*12.05,y,h,5.01))
        nx0,nx1=(26,38) if left_side else (962,974)
        notches.append(cube([nx0,480,z-41],[nx1,490,z+4]))

    divider_mesh = divider['mesh']
    divider_mesh.vertices[:,2] = np.where(divider_mesh.vertices[:,2] < 819,800,divider_mesh.vertices[:,2])
    divider['mesh']=cut(divider_mesh,mortises)
    back=box(34-ENGAGE,800-ENGAGE,966+ENGAGE,1770+ENGAGE)
    side=box(53-ENGAGE,800-ENGAGE,470+ENGAGE,1770+ENGAGE)
    add(new,'Back-infill-8',panel_blank(back,1,485,notches),'panel8')
    add(new,'Right-infill-8',panel_blank(side,0,981),'panel8')
    center_beam = cube([485,53,770],[515,470,800])
    add(new,'Beam-body-center',profile_mesh(*center_beam.bounds),'frame')
    floor_bays=(('Front',53,246.5),('Rear',276.5,470))
    for label,a,b,sill_a,sill_b in [('Left',34,485,34,491),('Right',515,966,509,966)]:
        mid=cube([a,246.5,770],[b,276.5,800])
        add(new,f'Beam-body-mid-{label}',profile_mesh(*mid.bounds),'frame')
        outer_x0,outer_x1=(a-ENGAGE,a+1) if label=='Left' else (b-1,b+ENGAGE)
        for segment,front,rear in floor_bays:
            floor=box(a-ENGAGE,front-ENGAGE,b+ENGAGE,rear+ENGAGE)
            y0,y1=(53-ENGAGE,54) if segment=='Front' else (469,470+ENGAGE)
            floor=floor.difference(box(outer_x0,y0,outer_x1,y1))
            add(new,f'Floor-{label}-{segment}-8',panel_blank(floor,2,785),'panel8')
        add(new,f'Front-sill-{label}-18',cube([sill_a,23,800],[sill_b,53,818]),'wood')
    panel_cuts[0:0]=[
        ['Back-infill-8',back.bounds[2]-back.bounds[0],back.bounds[3]-back.bounds[1],8,1],
        ['Right-infill-8',side.bounds[2]-side.bounds[0],side.bounds[3]-side.bounds[1],8,1],
        ['Floor-8',485-34+2*ENGAGE,246.5-53+2*ENGAGE,8,4],['Front-sill-18',457,30,18,2],
        ['Center-18',435,970,18,1], ['Top-18',932,417,18,1], ['Right-roof',457,405,12,1],
    ]
    return fixed,new,left,panel_cuts



def shelf_sweep_obstacles(parts):
    """Split each angle's L shape in X before projecting into the YZ plane."""
    result = []
    for p in parts:
        if not p['name'].startswith('Angle-'):
            result.append(p)
            continue
        low,high = p['mesh'].bounds
        is_left_outer = p['name'].startswith('Angle-Outer-Left')
        is_right_inner = p['name'].startswith('Angle-Inner-Right')
        web_x = (low[0],low[0]+3) if is_left_outer or is_right_inner else (high[0]-3,high[0])
        result.extend([dict(p,name=p['name']+'-web',mesh=cube(
            [web_x[0],low[1],low[2]],[web_x[1],high[1],high[2]])),
            dict(p,name=p['name']+'-flange',mesh=cube(
            [low[0],low[1],high[2]-3],[high[0],min(high[1],478),high[2]]))])
    return result


def assembly_paths(parts):
    meshes = named(parts)
    # Bottom frame assembled. Feed from the still-open end and then close
    # the bay with the free upright and top beam.
    paths = [
        ('feed-back', 'Back-infill-8', [1,0,0],
         ['Beam-body-rear','Post-4-470'] + [f'RSI-5048-Left-{i}-{j}' for i in (1,2) for j in (3,4)], 950),
        ('close-back-right', 'Post-966-470', [1,0,0], ['Back-infill-8'], 12),
        *[(f'close-back-right-nut-{i}-{j}', f'RSI-5048-Right-{i}-{j}',
           [1,0,0], ['Back-infill-8'], 12) for i in (1,2) for j in (3,4)],
        ('feed-right-side', 'Right-infill-8', [0,-1,0], ['Beam-body-side-966','Post-966-470'], 435),
        *[(f'feed-floor-rear-{side}', f'Floor-{side}-Rear-8', [0,-1,0],
           [f'Beam-body-side-{post}', 'Beam-body-center','Beam-body-rear', f'Post-{post}-470'], 435)
          for side,post in [('Left',4),('Right',966)]],
        *[(f'close-mid-{side}',f'Beam-body-mid-{side}',[0,-1,0],[f'Floor-{side}-Rear-8'],12)
          for side in ('Left','Right')],
        *[(f'feed-floor-front-{side}', f'Floor-{side}-Front-8', [0,-1,0],
           [f'Beam-body-side-{post}', 'Beam-body-center', f'Beam-body-mid-{side}'], 245)
          for side,post in [('Left',4),('Right',966)]],
        ('close-floor-front', 'Beam-body-front', [0,-1,0],
         ['Floor-Left-Front-8','Floor-Right-Front-8'], 12),
        ('close-right-front', 'Post-966-23', [0,-1,0], ['Right-infill-8'], 12),
        ('lower-rear-beam', 'Beam-top-rear', [0,0,1], ['Back-infill-8'], 12),
        ('lower-right-beam', 'Beam-top-side-966', [0,0,1], ['Right-infill-8'], 12),
    ]
    result = {}
    for label, mover, direction, targets, run in paths:
        span = sorted(set([0,2.5,5,7.5,10,12,run/2,run]))
        peak = max(overlap_volume(
            meshes[mover].copy().apply_translation(np.asarray(direction)*distance),
            meshes[target]) for distance in span for target in targets)
        result[label] = round(peak,5)
    return result


def right_parts(progress):
    leaf=leaf_parts()
    return [dict(pose(p,z,progress), name=f"{p['name']}-{i}")
            for i,(_,z) in enumerate(SECTIONS,1) for p in leaf]


def detail_sets(parts):
    by_name = {p['name']:p for p in parts}

    def clip(name,low,high):
        part=by_name[name]
        mesh=tm.boolean.intersection([part['mesh'],cube(low,high)],engine='manifold')
        return dict(part,mesh=mesh)

    rear=[
        clip('Post-966-470',[960,465,1068],[1001,501,1158]),
        clip('Angle-Outer-Right-1',[930,421,1080],[970,498,1131]),
        clip('Shelf-Right-1',[900,421,1126],[968,461,1140]),
        clip('Back-infill-8',[911,480,1070],[976,490,1160]),
    ]
    rear += [by_name[f'{name}-Right-1-{i}'] for i in (3,4) for name in ('M5x10','RSI-5048')]
    divider=[
        clip('Center-18',[490,248,1080],[510,337,1152]),
        clip('Angle-Inner-Right-1',[508,248,1084],[540,337,1131]),
        clip('Shelf-Right-1',[508,248,1126],[557,337,1140]),
        by_name['M5x12-Right-1-2'],
        by_name['Insert-M5-Right-1-2'],
    ]
    floor=[p for p in parts if p['name'].startswith(('Beam-body-','Floor-'))]
    return {'shelf-at-rear-post':rear, 'shelf-at-divider':divider, 'floor-in-slots':floor}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    fixed,new,left,rows=cabinet()
    complete=fixed+new
    model_closed=complete+left+right_parts(0)
    model_open=swing_left(complete+right_parts(2),left,AXIS_LEFT,96)
    results={}
    for name,parts in [('closed',model_closed),('open',model_open),('right-raised',complete+left+right_parts(1))]:
        collisions=collision_pairs(named(parts))
        results[name]=collisions
        print(name,collisions,flush=True)
        if name!='right-raised':
            export(OUT/f'cabinet-{name}.glb',parts)
    left_sweep=swept_clearance(complete,left,np.asarray(AXIS_LEFT))
    right_sweep=[audit_leaf(leaf_parts(),shelf_sweep_obstacles(complete),z) for _,z in SECTIONS]
    installation=assembly_paths(complete)
    print('installation paths',installation,flush=True)
    for item in right_sweep:
        print(item,flush=True)
    print(left_sweep,flush=True)
    with (OUT/'panels-and-shelves.csv').open('w',newline='') as f:
        writer=csv.writer(f,lineterminator="\n")
        writer.writerow(['part','width_or_depth_mm','height_or_depth_mm','stock_mm','count'])
        writer.writerows(rows)
    assert not any(results.values()),results
    assert min(left_sweep[2], *(item[1] for item in right_sweep)) > 0
    assert not any(installation.values()),installation
    for name,detail in detail_sets(complete).items():
        export(OUT/f'{name}.glb',detail)
    (OUT/'checks.json').write_text(json.dumps(dict(section=SOURCE['profile_step_sha256'],
        panel_stock_thickness_mm=THICKNESS, panel_insertion_each_edge_mm=ENGAGE, endpoint_overlaps=results,left_sweep=left_sweep,
        right_sweep=right_sweep, assembly_sample_overlaps_mm3=installation,
        lower_beams_clearance_mm=LOWER_CLEARANCE, fabrication_release=False),indent=2)+'\n')


if __name__=='__main__':
    main()
