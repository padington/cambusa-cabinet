"""Cambusa v27. Supplier quick connectors, centered pegboard and door-tray joinery."""
import csv
import json
from collections import Counter

import numpy as np
import trimesh as tm

from build_aluminum_corner import add, collision_pairs, cube, cut, overlap_volume, swept_clearance
from build_aluminum_corner import pose as swing_left
from build_pegboard_cabinet import (
    cabinet as v26_cabinet, install_tests,
    right_leaf, right_parts, slot_end,
)
from build_right_lift import AXIS_LEFT, ROOT, SECTIONS, audit_leaf, export, named

OUT = ROOT / 'outputs/cambusa-v27-frame-joinery'
PEGBOARD_PATTERN = [(86.5+50*i,834.5+50*j) for i in range(8) for j in range(19)]
ACCESS_OFFSET = 16.0
CROSS_BORE = 11.3
AXIAL_BORE = 7.1
CAD_SOURCE = json.loads((ROOT/'inputs/rsi-quick-connectors.json').read_text())


def revolve_at(origin, direction, section):
    mesh=tm.creation.revolve(np.asarray(section),sections=32)
    mesh.apply_transform(tm.geometry.align_vectors([0,0,1],direction))
    return mesh.apply_translation(origin)


def bore(origin,direction,start,end,radius):
    return revolve_at(origin,direction,[(0,start),(radius,start),(radius,end),(0,end)])


def screw(origin, direction, radius, length, bore_length=None):
    # In the assembly check the screw threads and the pilot are represented
    # by the same cylindrical envelope. Pilot sizes come from the chosen screw.
    head=2*radius
    depth=head-radius
    if bore_length is None:
        outline=[(0,0),(head,0),(radius,depth),(radius,length),(0,length)]
    else:
        outline=[(0,-.05),(head+.1,-.05),(radius+.04,depth),(radius+.04,bore_length),(0,bore_length)]
    return revolve_at(origin,direction,outline)


def cad_parts():
    path=ROOT/'inputs/rsi-quick-connectors.npz'
    with np.load(path) as data:
        return {sku:[tm.Trimesh(vertices=data[f'{sku}_{i}_vertices'],faces=data[f'{sku}_{i}_faces'],
                                process=False)
                     for i in range(info['parts'])] for sku,info in CAD_SOURCE.items()}


def frame_joints(fixed):
    joints=[]
    for p in fixed:
        name=p['name']
        if not name.startswith('Beam-'):
            continue
        low,high=p['mesh'].bounds
        axis=int(np.argmax(high-low))
        for side in (0,1):
            end='A' if side==0 else 'B'
            point=(low+high)/2
            point[axis]=[low,high][side][axis]
            along=np.eye(3)[axis]*(1-2*side)
            if name=='Beam-body-center':
                target=['Beam-body-front','Beam-body-rear'][side]
                sku,access='5211',[0,0,-1]
            elif name.startswith('Beam-right-shelf-'):
                target=f'Post-966-{[23,470][side]}'
                sku,access='5211',[1,0,0]
            elif axis==0:
                x=[4,966][side]
                target=f'Post-{x}-{int(low[1])}'
                sku,access='5212',[0,0,1 if name.startswith('Beam-top-') else -1]
            else:
                x=int(low[0])
                target=f'Post-{x}-{[23,470][side]}'
                sku,access='5212',[0,0,1 if name.startswith('Beam-top-') else -1]
            joints.append(dict(id=f'{name}-{end}',beam=name,target=target,sku=sku,point=point,
                               along=along,access=np.asarray(access)))
    assert Counter(j['sku'] for j in joints)=={'5211':6,'5212':22}
    return joints


def frame_joinery(fixed):
    cad=cad_parts()
    joints=frame_joints(fixed)
    by_name={p['name']:p for p in fixed}
    cuts={}
    for j in joints:
        point,along,access=j['point'],j['along'],j['access']
        axis=point+along*ACCESS_OFFSET
        cuts.setdefault(j['beam'],[]).extend([
            bore(point,along,-.02,28,AXIAL_BORE/2),
            bore(axis,access,-6.35,15.1,CROSS_BORE/2),
        ])
        matrix=np.eye(4)
        matrix[:3,:3]=np.column_stack((np.cross(access,along),access,along))
        matrix[:3,3]=point
        for n,mesh in enumerate(cad[j['sku']],1):
            placed=mesh.copy().apply_transform(matrix)
            if j['sku']=='5212' and n==1:
                # The lock pulls the head toward the lip. Use its seated
                # position in the OB-3030 cross-section.
                placed.apply_translation(-.25*along)
            add(fixed,f"RSI-{j['sku']}::{j['id']}::{n}",placed,'fastener')
    for name,mortises in cuts.items():
        by_name[name]['mesh']=cut(by_name[name]['mesh'],mortises)
    return joints


def door_joinery(left):
    parts={p['name']:p for p in left}
    hinge='Door-inner-hinge-18'
    meeting='Door-inner-meeting-18'
    face='Door-face-18'
    machining={name:[] for name in (hinge,meeting,face)}
    for rib,x in ((hinge,83),(meeting,458)):
        for z in (870,1060,1370,1720):
            point=[x,75.5,z]
            direction=[0,-1,0]
            tool=screw(point,direction,2.5,80,80.4)
            machining[rib].append(tool)
            machining[face].append(tool)
            add(left,f'Left-door-rib-screw-{x}-{z}',screw(point,direction,2.5,80),'fastener')
    for i,z in enumerate((934,1234,1534),1):
        tray_name=f'Door-tray-{i}-12'
        lip_name=f'Door-lip-{i}-12'
        tray=cube([87,8.7,z],[454,75.3,z+12])
        lip=cube([92,63.5,z+12],[449,75.3,z+50])
        tray_cuts,lip_cuts=[],[]
        machining[hinge].append(cube([86.8,8.45,z-.15],[92.05,75.6,z+12.15]))
        machining[meeting].append(cube([448.95,8.45,z-.15],[454.2,75.6,z+12.15]))
        for x,direction,rib in ((74,[1,0,0],hinge),(467,[-1,0,0],meeting)):
            point=[x,45,z+6]
            tool=screw(point,direction,2,30,30.4)
            machining[rib].append(tool)
            tray_cuts.append(tool)
            add(left,f'Left-door-tray-lock-{i}-{x}',screw(point,direction,2,30),'fastener')
        for x in (130,270,410):
            point=[x,69.5,z]
            direction=[0,0,1]
            tool=screw(point,direction,2,25,25.4)
            tray_cuts.append(tool)
            lip_cuts.append(tool)
            add(left,f'Left-door-lip-screw-{i}-{x}',screw(point,direction,2,25),'fastener')
        parts[tray_name]['mesh']=cut(tray,tray_cuts)
        parts[lip_name]['mesh']=cut(lip,lip_cuts)
    for name,tools in machining.items():
        parts[name]['mesh']=cut(parts[name]['mesh'],tools)


def cabinet():
    fixed,left,rows=v26_cabinet(PEGBOARD_PATTERN)
    fixed=[p for p in fixed if not p['name'].startswith(('Right-flat-plate-','Right-plate-'))]
    joints=frame_joinery(fixed)
    door_joinery(left)
    return fixed,left,rows,joints


def is_same_connector(pair):
    a,b=pair['parts']
    return a.startswith('RSI-') and b.startswith('RSI-') and a.split('::')[1]==b.split('::')[1]


def profile_access(fixed,joints):
    # The accessible straight approach begins at the aluminum surface.
    obstacles=[p for p in fixed if not p['name'].startswith('RSI-')]
    results={}
    for j in joints:
        axis=j['point']+j['along']*ACCESS_OFFSET
        tool=bore(axis,j['access'],15.05,85,3.3)
        hits=[p['name'] for p in obstacles if
              np.all(np.minimum(tool.bounds[1],p['mesh'].bounds[1]) >
                     np.maximum(tool.bounds[0],p['mesh'].bounds[0])+.01) and
              overlap_volume(tool,p['mesh'])>.08]
        results[j['id']]=hits
    return results


def head_entry_checks(fixed,joints):
    parts=named(fixed)
    types=('Beam-body-front-A','Beam-right-shelf-1-A','Beam-body-center-A')
    results={}
    for j in joints:
        if j['id'] not in types:
            continue
        point,axis=j['point'],j['along']
        head=parts[f"RSI-{j['sku']}::{j['id']}::1"]
        receiver=parts[j['target']]
        def rotated(degrees):
            transform=tm.transformations.rotation_matrix(np.radians(degrees),axis,point)
            return head.copy().apply_transform(transform)
        turn=max(overlap_volume(rotated(degrees),receiver) for degrees in range(0,91,5))
        entry=max(overlap_volume(rotated(90).apply_translation(axis*d),receiver)
                  for d in (0,1,2,3,4,5,6,8))
        results[j['id']]={'quarter_turn_mm3':round(turn,5),'entry_mm3':round(entry,5)}
    return results


def detail_sets(fixed,left):
    parts=named(fixed+left)
    by_name={p['name']:p for p in fixed+left}

    def clip(name,low,high):
        return dict(by_name[name],mesh=tm.boolean.intersection(
            [parts[name],cube(low,high)],engine='manifold'))

    corner=[
        clip('Post-4-470',[3,469,726],[35,501,840]),
        clip('Beam-body-side-4',[3,410,767],[35,470,801]),
        clip('Beam-body-rear',[34,469,767],[99,501,801]),
        *[p for p in fixed if p['name'].startswith(
            ('RSI-5212::Beam-body-side-4-B::','RSI-5212::Beam-body-rear-A::'))],
    ]
    right=[
        clip('Post-966-23',[965,22,1069],[997,54,1161]),
        clip('Beam-right-shelf-1',[965,53,1096],[997,110,1128]),
        *[p for p in fixed if p['name'].startswith('RSI-5211::Beam-right-shelf-1-A::')],
    ]
    tray=[
        clip('Door-face-18',[64,-10,912],[155,9,1003]),
        clip('Door-inner-hinge-18',[73,8,912],[93,76,1003]),
        clip('Door-tray-1-12',[86,8,933],[155,76,947]),
        clip('Door-lip-1-12',[91,63,945],[155,76,985]),
        by_name['Left-door-tray-lock-1-74'],by_name['Left-door-lip-screw-1-130'],
    ]
    return {'frame-corner-5212':corner,'frame-side-joint-5211':right,'left-door-tray-joint':tray}


def tray_installation(left):
    meshes=named(left)
    rib_names=('Door-inner-hinge-18','Door-inner-meeting-18','Door-face-18')
    return {f'tray-{i}':round(max(overlap_volume(
        meshes[moving].copy().apply_translation([0,d,0]),meshes[target])
        for moving in (f'Door-tray-{i}-12',f'Door-lip-{i}-12') for target in rib_names
        for d in (0,1,4,12,25,50,70)),5) for i in (1,2,3)}


def main():
    OUT.mkdir(exist_ok=True)
    fixed,left,rows,joints=cabinet()
    results={}
    for label,parts in [('closed',fixed+left+right_parts(0)),('right-raised',fixed+left+right_parts(1)),
                        ('open',swing_left(fixed+right_parts(2),left,AXIS_LEFT,96)),
                        ('left-270',swing_left(fixed+right_parts(0),left,AXIS_LEFT,270))]:
        results[label]=[p for p in collision_pairs(named(parts)) if not is_same_connector(p)]
        print(label,results[label],flush=True)
        if label in ('closed','open'):
            export(OUT/f'cabinet-{label}.glb',parts)
    access=profile_access(fixed,joints)
    print('blocked access', {k:v for k,v in access.items() if v},flush=True)
    left_clearance=swept_clearance(fixed,left,np.asarray(AXIS_LEFT))
    right_clearance=[audit_leaf(right_leaf(z),fixed,z,slot_end(z)) for _,z in SECTIONS]
    print('sweeps',left_clearance,right_clearance,flush=True)
    installation=install_tests([p for p in fixed if not p['name'].startswith('RSI-')])
    print('panel/shelf placement, anchors released',installation,flush=True)
    tray_feed=tray_installation(left)
    head_entry=head_entry_checks(fixed,joints)
    print('tray installation',tray_feed,flush=True)
    assert not any(results.values()),results
    assert not any(access.values()),access
    assert not any(v for check in head_entry.values() for v in check.values()),head_entry
    assert min(left_clearance[2],*(r[1] for r in right_clearance))>0
    assert not any(installation.values()) and not any(tray_feed.values())
    for label,detail in detail_sets(fixed,left).items():
        export(OUT/f'{label}.glb',detail)
    with (OUT/'frame-joints.csv').open('w',newline='') as f:
        writer=csv.writer(f,lineterminator='\n')
        writer.writerow(['joint','beam','receiver','rsi_sku','X','Y','Z','access','bore_from_end_mm','cross_bore_mm','axial_bore_mm'])
        writer.writerows([j['id'],j['beam'],j['target'],j['sku'],*j['point'],
            'up' if j['access'][2]>0 else 'down' if j['access'][2]<0 else 'right',
            ACCESS_OFFSET,CROSS_BORE,AXIAL_BORE] for j in joints)
    counts=Counter(j['sku'] for j in joints)
    with (OUT/'frame-hardware.csv').open('w',newline='') as f:
        writer=csv.writer(f,lineterminator='\n')
        writer.writerow(['supplier','sku','quantity','product_page'])
        writer.writerows([['RSI','5212',counts['5212'],'https://www.rsi-llc.ru/catalog/87/274/'],
                          ['RSI','5211',counts['5211'],'https://www.rsi-llc.ru/catalog/87/272/']])
    with (OUT/'panels-and-shelves.csv').open('w',newline='') as f:
        writer=csv.writer(f,lineterminator='\n')
        writer.writerow(['part','width_or_depth_mm','height_or_depth_mm','stock_mm','count'])
        writer.writerows(rows)
    (OUT/'checks.json').write_text(json.dumps(dict(endpoint_overlaps=results,tool_access=access,
        left_sweep=left_clearance,right_sweep=right_clearance,installation=installation,tray_insertion_overlaps_mm3=tray_feed,
        counts=counts,head_entry_samples=head_entry,pegboard={'diameter_mm':12,'pitch_mm':50,
        'margins_to_centers_mm':[33,34.5]},fabrication_release=False),indent=2)+'\n')


if __name__=='__main__':
    main()
