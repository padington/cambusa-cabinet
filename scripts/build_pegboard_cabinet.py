"""Cambusa v26. Perforated side, discreet shelf supports and full-height lower facades."""
import csv
import json

import numpy as np
import trimesh as tm
from shapely.geometry import Point, box
from shapely.ops import unary_union

from build_aluminum_corner import add, collision_pairs, cube, cut, cylinder, overlap_volume, panel, swept_clearance
from build_aluminum_corner import pose as swing_left
from build_right_lift import AXIS_LEFT, ROOT, SECTIONS, SLOT_END, audit_leaf, export, leaf_parts, named, pose
from build_slotted_panels import ENGAGE, LOWER_CLEARANCE, cabinet as v25_cabinet, countersunk_screw, cross_hole, nut_at, panel_blank, profile_mesh

OUT = ROOT / 'outputs/cambusa-v26-pegboard'
LOWER_SECTION_TOP = SECTIONS[0][1]
EXTENSION = 18
PEGBOARD_HOLES = [(y,z) for y in range(75,426,50) for z in range(840,1741,50)]


def drill_z(x,y,a,b,radius):
    mesh=tm.creation.cylinder(radius=radius,height=abs(a-b),sections=32)
    return mesh.apply_translation([x,y,(a+b)/2])


def drill_x(x,y,z,start,end,radius):
    return cylinder(0,min(x+start,x+end),max(x+start,x+end),y,z,radius)


def pegboard(shelf_mounts, pattern=PEGBOARD_HOLES):
    outline=box(53.5,800,469.5,1769).difference(unary_union([
        Point(y,z).buffer(6,quad_segs=5) for y,z in pattern
    ]))
    wood=panel(outline,0,10,18)
    holes=list(shelf_mounts)
    hardware=[]
    beam_mortises={'Beam-body-side-4':[],'Beam-top-side-4':[]}
    for end,z,shank_base,seat,free_edge,entry in [
        ('Bottom',820,777.4,779,800,770),('Top',1749,1792.6,1791,1769,1800)
    ]:
        bottom=end=='Bottom'
        sign=1 if bottom else -1
        beam='Beam-body-side-4' if bottom else 'Beam-top-side-4'
        for y in (97,426):
            bore=drill_z(19,y,seat-sign*.05,free_edge+sign*.1,3.3)
            sink=drill_z(19,y,entry-sign*.1,seat,8.5)
            beam_mortises[beam] += [bore,sink]
            barrel=drill_x(28,y,z,-15.5,-2.5,5)
            holes.extend([drill_x(28,y,z,-15.6,.1,5.05),
                          drill_z(19,y,free_edge-sign*.1,z+sign*5,3.3)])
            add(hardware,f'Pegboard-cross-dowel-{end}-{y}',
                cut(barrel,[drill_z(19,y,z-5.1,z+5.1,3.02)]),'fastener')
            head=drill_z(19,y,shank_base-sign*6,shank_base,5)
            shank=drill_z(19,y,shank_base,shank_base+sign*45,3)
            screw=tm.boolean.union([head,shank],engine='manifold')
            add(hardware,f'Pegboard-M6x45-{end}-{y}',screw,'fastener')
            washer=cut(drill_z(19,y,shank_base,seat,8),[drill_z(19,y,shank_base-sign*.1,seat+sign*.1,3.2)])
            add(hardware,f'Pegboard-washer-{end}-{y}',washer,'fastener')
            if not bottom:
                shim=cut(cube([10,y-10,1769],[28,y+10,1770]),[drill_z(19,y,1768.9,1770.1,3.3)])
                add(hardware,f'Pegboard-top-shim-{y}',shim,'frame')
    return cut(wood,holes),hardware,beam_mortises


def slot_end(top):
    return SLOT_END+EXTENSION if top==LOWER_SECTION_TOP else SLOT_END


def right_leaf(top):
    return leaf_parts(300+EXTENSION,slot_end(top)) if top==LOWER_SECTION_TOP else leaf_parts()


def right_beam_fasteners(parts,index,z):
    """Flat plates fit the outside-facing slots of beam and posts."""
    for label,y0,y1,post_y,beam_y in [('Front',23,83,38,68),('Rear',440,500,485,455)]:
        suffix=f'{index}-{label}'
        plate=cube([996,y0,z-12],[999,y1,z+12])
        seats=[]
        for y in (post_y,beam_y):
            seats.extend([cross_hole(995.9,999.1,y,z,2.7),cross_hole(999.02,996.67,y,z,5.02,2.7)])
            add(parts,f'Right-plate-M5x10-{suffix}-{y}',countersunk_screw(999,1,y,z,10),'fastener')
            nut=nut_at(996,1,y,z)
            if y==beam_y:
                rotation=tm.transformations.rotation_matrix(np.pi/2,[1,0,0],[996,y,z])
                nut.apply_transform(rotation)
            add(parts,f'Right-plate-5048-{suffix}-{y}',nut,'fastener')
        add(parts,f'Right-flat-plate-{suffix}',cut(plate,seats),'frame')


def cabinet(pegboard_pattern=PEGBOARD_HOLES):
    fixed,old,left,rows=v25_cabinet()
    parts = [p for p in fixed+old if p['name'] not in ('Center-18','Back-infill-8','Right-infill-8') and
        not p['name'].startswith(('Left-glass-','Glazing-','Glass-pad-','Front-sill-','Shelf-',
                                  'Angle-','M5x10-','M5x12-','RSI-5048-','Insert-M5-'))]
    rows=[r for r in rows if not r[0].startswith(('Right-infill-','Front-sill-','Shelf-'))]
    for part in left:
        if part['name']=='Door-face-18':
            mesh=part['mesh']
            bottom=mesh.bounds[0,2]
            mesh.vertices[mesh.vertices[:,2]<bottom+.001,2]-=EXTENSION
    divider=next(p['mesh'] for p in fixed if p['name']=='Center-18')
    # Restore the stock divider before making the new blind pin holes.
    divider=cube(*divider.bounds)
    pins,pegboard_holes,divider_holes=[],[],[]
    for side,levels in [('Left',(1138,1458)),('Right',(1127,1448))]:
        is_left=side=='Left'
        for index,z in enumerate(levels,1):
            start_x,end_x,start_y,stock=(29,490,103,18) if is_left else (510,975.5,23,12)
            body=cube([start_x,start_y,z],[end_x,458,z+stock])
            receivers=[('divider',491,-1,(150,400))] if is_left else [('divider',509,1,(100,405))]
            if is_left:
                receivers.append(('pegboard',28,1,(150,400)))
            seats=[] if is_left else [cube([965.5,22,z-.1],[976,53.5,z+stock+.1])]
            for receiver,edge,side_sign,locations in receivers:
                for y in locations:
                    pins.append((f'Shelf-pin-{side}-{index}-{receiver}-{y}',
                                 drill_x(edge,y,z,-10*side_sign,10*side_sign,3)))
                    holes=pegboard_holes if receiver=='pegboard' else divider_holes
                    if receiver=='pegboard':
                        assert all((y-py)**2+(z-pz)**2>(6+3.03)**2 for py,pz in pegboard_pattern)
                    holes.append(drill_x(edge,y,z,-10.3*side_sign,.1*side_sign,3.03))
                    seats.append(drill_x(edge,y,z,-.1*side_sign,10.35*side_sign,3.1))
            add(parts,f'Shelf-{side}-{index}',cut(body,seats),'wood')
            rows.append([f'Shelf-{side}-{index}',end_x-start_x,458-start_y,stock,1])
    add(parts,'Center-18',cut(divider,divider_holes),'wood')
    for name,mesh in pins:
        add(parts,name,mesh,'fastener')

    wood,hardware,beam_mortises=pegboard(pegboard_holes, pegboard_pattern)
    for p in parts:
        if p['name'] in beam_mortises:
            p['mesh']=cut(p['mesh'],beam_mortises[p['name']])
    add(parts,'Left-pegboard-18',wood,'wood')
    parts += hardware
    rows.append(['Left-pegboard-18',416,969,18,1])

    add(parts,'Back-infill-8',panel_blank(box(34-ENGAGE,800-ENGAGE,966+ENGAGE,1770+ENGAGE),1,485),'panel8')
    for index,z in enumerate((1127,1448),1):
        blank=cube([966,53,z-30],[996,470,z])
        add(parts,f'Beam-right-shelf-{index}',profile_mesh(*blank.bounds),'frame')
        right_beam_fasteners(parts,index,z-15)
    for index,(a,b) in enumerate(((800,1097),(1127,1418),(1448,1770)),1):
        outline=box(53-ENGAGE,a-ENGAGE,470+ENGAGE,b+ENGAGE)
        add(parts,f'Right-infill-8-{index}',panel_blank(outline,0,981),'panel8')
        rows.append([f'Right-infill-8-{index}',432,b-a+2*ENGAGE,8,1])
    return parts,left,rows


def install_tests(fixed):
    meshes=named(fixed)
    checks=[
        ('pegboard-insert', 'Left-pegboard-18', [1,0,0], ['Beam-body-side-4','Beam-top-side-4','Post-4-23','Post-4-470'], 33),
        ('close-front-with-floors','Beam-body-front',[0,-1,0],['Floor-Left-8','Floor-Right-8'],12),
        ('back-feed','Back-infill-8',[1,0,0],['Beam-body-rear','Post-4-470'],950)
    ]
    levels=('Beam-body-side-966','Beam-right-shelf-1','Beam-right-shelf-2','Beam-top-side-966')
    for index in range(1,4):
        checks.append((f'right-feed-{index}',f'Right-infill-8-{index}',[0,-1,0],
                       [*levels[index-1:index+1],'Post-966-470'],435))
    result={}
    for label,mover,direction,targets,run in checks:
        span=sorted(set([0,1,2.5,5,7.5,10,12,run/2,run]))
        result[label]=round(max(overlap_volume(meshes[mover].copy().apply_translation(np.asarray(direction)*d),
                                              meshes[t]) for t in targets for d in span),5)
    # The right front post is fitted after the shelves enter from the front.
    # During feed, each shelf is raised 3.2 mm above its locating pins.
    for index in (1,2):
        shelf=meshes[f'Shelf-Right-{index}']
        supports=[meshes[f'Shelf-pin-Right-{index}-divider-{y}'] for y in (100,405)]
        frame=[meshes[key] for key in ('Center-18','Post-966-470',f'Beam-right-shelf-{index}',
                                      f'Right-infill-8-{index}',f'Right-infill-8-{index+1}')]
        steps=[(0,-d,3.2) for d in (0,10,40,100,200,320,440)]+[(0,0,d) for d in (0,1,2,3.2)]
        result[f'right-shelf-feed-{index}']=round(max(overlap_volume(
            shelf.copy().apply_translation(offset), obstacle) for offset in steps for obstacle in frame+supports),5)
    # Fit left shelves through the front before the left front post is added.
    for index in (1,2):
        shelf=meshes[f'Shelf-Left-{index}']
        frame=[meshes[key] for key in ('Center-18','Left-pegboard-18','Post-4-470')]
        supports=[meshes[f'Shelf-pin-Left-{index}-{owner}-{y}']
                  for owner in ('divider','pegboard') for y in (150,400)]
        steps=[(0,-d,3.2) for d in (0,10,40,100,200,320,460)]+[(0,0,d) for d in (0,1,2,3.2)]
        result[f'left-shelf-feed-{index}']=round(max(overlap_volume(
            shelf.copy().apply_translation(offset), obstacle) for offset in steps for obstacle in frame+supports),5)
    return result


def right_parts(progress):
    return [dict(pose(p,top,progress,slot_end(top)),name=f'{p["name"]}-{index}')
            for index,(_,top) in enumerate(SECTIONS,1) for p in right_leaf(top)]


def detail_sets(fixed):
    parts={p['name']:p for p in fixed}

    def clip(name,low,high):
        p=parts[name]
        mesh=tm.boolean.intersection([p['mesh'],cube(low,high)],engine='manifold')
        return dict(p,mesh=mesh)

    shelf=[
        clip('Left-pegboard-18',[9,99,1105],[29,166,1160]),
        clip('Shelf-Left-1',[28,99,1137],[86,166,1157]),
        parts['Shelf-pin-Left-1-pegboard-150']
    ]
    mount=[
        clip('Left-pegboard-18',[9,76,799],[29,121,847]),
        clip('Beam-body-side-4',[3,76,769],[35,121,801]),
        *[parts[f'Pegboard-{part}-Bottom-97'] for part in ('M6x45','washer','cross-dowel')]
    ]
    right=[
        clip('Shelf-Right-1',[949,22,1126],[976,96,1140]),
        clip('Beam-right-shelf-1',[965,53,1096],[997,96,1128]),
        clip('Post-966-23',[965,22,1088],[997,54,1152]),
        parts['Right-flat-plate-1-Front'],
        *[parts[f'Right-plate-{part}-1-Front-{y}'] for y in (38,68) for part in ('M5x10','5048')],
    ]
    return {'shelf-pin-detail':shelf,'pegboard-mount-detail':mount,'right-shelf-frame-detail':right}


def main():
    OUT.mkdir(exist_ok=True)
    fixed,left,rows=cabinet()
    results={}
    for label,parts in [('closed',fixed+left+right_parts(0)),('right-raised',fixed+left+right_parts(1)),
                        ('open',swing_left(fixed+right_parts(2),left,AXIS_LEFT,96)),
                        ('left-270',swing_left(fixed+right_parts(0),left,AXIS_LEFT,270))]:
        results[label]=collision_pairs(named(parts))
        print(label,results[label],flush=True)
        if label in ('closed','open'):
            export(OUT/f'cabinet-{label}.glb',parts)
    left_result=swept_clearance(fixed,left,np.asarray(AXIS_LEFT))
    right_results=[audit_leaf(right_leaf(z),fixed,z,slot_end(z)) for _,z in SECTIONS]
    install=install_tests(fixed)
    print('left',left_result,'right',right_results,'install',install,flush=True)
    assert not any(results.values()),results
    assert not any(install.values()),install
    assert min(left_result[2],*(r[1] for r in right_results))>0
    for name,parts in detail_sets(fixed).items():
        export(OUT/f'{name}.glb',parts)
    with (OUT/'panels-and-shelves.csv').open('w',newline='') as f:
        writer=csv.writer(f,lineterminator='\n')
        writer.writerow(['part','width_or_depth_mm','height_or_depth_mm','stock_mm','count'])
        writer.writerows(rows)
    lower_closed=right_parts(0)
    left_lower=min(p['mesh'].bounds[0,2] for p in left if p['name']=='Door-face-18')
    right_lower=min(p['mesh'].bounds[0,2] for p in lower_closed if p['name'].endswith('-1'))
    (OUT/'checks.json').write_text(json.dumps(dict(endpoint_overlaps=results,left_sweep=left_result,
        right_sweep=right_results,installation_sample_overlaps_mm3=install,pegboard_holes=len(PEGBOARD_HOLES),
        lowest_right_facade_height_mm=300+EXTENSION,lower_beam_clearance_mm=LOWER_CLEARANCE,
        closed_facade_gap_to_front_beam_mm=[round(left_lower-800,3),round(right_lower-800,3)],
        fabrication_release=False),indent=2)+'\n')


if __name__=='__main__':
    main()
