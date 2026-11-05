"""v30: contained shelves, blind pegboard, contextual details and adjustable door.

Old outputs and the no-spacer Blum candidate remain reproducible.
"""
import argparse
import base64
import csv
import gzip
import json
import math
from pathlib import Path

import numpy as np
import trimesh as tm
from shapely import affinity

import blum_inset as blum
from build_aluminum_corner import add, cube, cut, footprint, overlap_volume
from build_concealed_cabinet import audit_contacts, reviewed_structure_with_previous_door
from build_frame_joinery import PEGBOARD_PATTERN, bore
from build_panel_mount_viewer import payload as previous_payload, details as previous_details
from build_pegboard_cabinet import drill_x, drill_z, right_parts, right_leaf, slot_end
from build_right_lift import ROOT, SECTIONS, audit_leaf, export
from review_panel_fasteners import candidate
from audit_assembly import load_parts

OUT=ROOT/'outputs/cambusa-v30-review-fixes'
CUP_SPACER=1.5
SHELF_FRONT=54.0


def blind_side(fixed):
    holes=[bore([10,y,z],[1,0,0],-.1,10,6) for y,z in PEGBOARD_PATTERN]
    holes += [drill_x(28,y,z,-10.3,.1,3.03)
              for z in (1138,1458) for y in (150,400)]
    for z,edge,sign in ((820,800,1),(1749,1769,-1)):
        for y in (97,426):
            holes += [drill_x(28,y,z,-14.6,.1,5.05),
                      drill_z(19,y,edge-sign*.1,z+sign*5,3.3)]
    board=next(p for p in fixed if p['name']=='Left-pegboard-18')
    board['mesh']=cut(cube([10,53.5,800],[28,469.5,1769]),holes)


def assembly():
    fixed,_,mount_dimensions=candidate()
    fixed=[p for p in fixed if not p['name'].startswith(('Left-hinge-','Left-profile-'))]
    blind_side(fixed)
    for index,z in enumerate((1127,1448),1):
        shelf=next(p for p in fixed if p['name']==f'Shelf-Right-{index}')
        tools=[drill_x(509,y,z,-.1,11.35,3.1) for y in (100,405)]
        tools += [drill_x(972,y,z,-11,.1,3.1) for y in (100,405)]
        shelf['mesh']=cut(cube([510,SHELF_FRONT,z],[971.5,458,z+12]),tools)
    left,machining=blum.build(fixed,cup_spacer_mm=CUP_SPACER)
    _,_,rows,joints,seats=reviewed_structure_with_previous_door()
    rows=[r for r in rows if not r[0].startswith('Shelf-Right-')]
    rows += [[f'Shelf-Right-{i}',461.5,404,12,1] for i in (1,2)]
    return fixed,left,rows,joints,seats,mount_dimensions,machining


def clip(part,low,high):
    mesh=tm.boolean.intersection([part['mesh'],cube(low,high)],engine='manifold')
    assert mesh.is_volume,part['name']
    return dict(part,mesh=mesh)


def details(fixed,left):
    # Keep the unchanged cube and foot detail geometry from the v29 helper.
    result=previous_details(fixed,[])
    by_name={p['name']:p for p in fixed}
    names=['Right-wall-18','Beam-body-side-966',
           'Right-wall-M6x45-Bottom-97','Right-wall-washer-Bottom-97',
           'Right-wall-cross-dowel-Bottom-97']
    mounts=[clip(by_name[name],[965,75,769],[997,123,854]) if i<2 else by_name[name]
            for i,name in enumerate(names)]
    section=[clip(p,[965,97,769],[997,123,854]) for p in mounts]
    deltas=([0,0,32],[0,0,0],[0,0,-24],[0,0,-12],[-23,0,32])
    result['mount']=[dict(p,delta=d) for p,d in zip(mounts,deltas)]
    result['section']=[dict(p,delta=d) for p,d in zip(section,deltas)]
    right=[]
    beams={'Beam-body-side-966','Beam-top-side-966','Beam-body-front','Beam-body-rear',
           'Beam-top-front','Beam-top-rear','Beam-body-center'}
    relevant_joints=set()
    for p in fixed:
        name=p['name']
        if name in ('Right-wall-18','Center-18') or name.startswith(('Shelf-Right-',
            'Shelf-pin-Right-','Right-wall-M6','Right-wall-washer','Right-wall-cross',
            'Right-wall-top-shim')):
            right.append(p)
        elif name in beams or name in ('Post-966-23','Post-966-470'):
            right.append(clip(p,[491,22,760],[997,501,1801]))
        elif name.startswith(('Cube-2069-966-','Cube-bolt-M8x25-966-','Cube-cap-966-')):
            right.append(p)
        elif name.startswith('RSI-') and '::' in name:
            joint_id=name.split('::')[1]
            beam=joint_id.rsplit('-',1)[0]
            if beam in beams and p['mesh'].bounds[0,0]>480:
                relevant_joints.add(joint_id);right.append(p)
    result['right']=right
    result['hinge']=[]
    for p in fixed+left:
        name=p['name']
        if name in ('Post-4-23','Left-pegboard-18','Left-door-face-18'):
            result['hinge'].append(clip(p,[3,14,848],[106,116,938]))
        elif name.startswith('Blum-1-'):
            result['hinge'].append(p)
    board=clip(by_name['Left-pegboard-18'],[9,114,907],[29,159,956])
    # Explanatory example pin, not a load-rated product or a procurement item.
    pin=dict(name='Example-peg-11.8',mesh=bore([10,136.5,934.5],[1,0,0],-40.5,9.5,5.9),
             material='handle',group='example')
    result['pegmount']=[dict(clip(board,[9,136.5,907],[29,159,956]),delta=[0,0,0]),
                        dict(clip(pin,[-31,136.5,907],[30,159,956]),delta=[-25,0,0])]
    return result


def door_sweep(fixed,left):
    """Planar door clearance with an analytic between-sample speed bound."""
    face=next(p for p in left if p['name']=='Left-door-face-18')['mesh']
    z0,z1=face.bounds[:,2]
    obstacles=[(p['name'],footprint(p['mesh'])) for p in fixed+right_parts(0)
               if not p['name'].startswith('Blum-') and
               min(z1,p['mesh'].bounds[1,2])-max(z0,p['mesh'].bounds[0,2])>.001]
    shape=footprint(face);step=.125;closest=(math.inf,None,None)
    for degrees in np.arange(0,110+step/2,step):
        t=blum.transform_for('cup',degrees,CUP_SPACER)
        transformed=affinity.affine_transform(shape,[t[0,0],t[0,1],t[1,0],t[1,1],t[0,3],t[1,3]])
        for name,obstacle in obstacles:
            distance=transformed.distance(obstacle)
            if distance<closest[0]:closest=(float(distance),float(degrees),name)
    # B' is tangent to (B-P). Its magnitude <= |A-B| / min(sin(phi)),
    # with phi between the two pin links. Obtain the global extremal link
    # angle analytically from |P-Q + R(theta)(A-B)|², a sine/cosine function.
    d=blum.A-blum.B;w=blum.P-blum.Q
    ac=float(w@d);bc=float(w@np.array([-d[1],d[0]]))
    angles=[0,math.radians(110)]
    base=math.atan2(bc,ac)
    angles += [base+k*math.pi for k in range(-2,3) if 0<=base+k*math.pi<=angles[1]]
    r1=np.linalg.norm(blum.B-blum.P);r2=np.linalg.norm(blum.A-blum.Q)
    distances=[float(w@w+d@d+2*(ac*math.cos(a)+bc*math.sin(a))) for a in angles]
    cosines=[(r1*r1+r2*r2-v)/(2*r1*r2) for v in distances]
    sine=math.sqrt(1-max(abs(c) for c in cosines)**2)
    max_b_speed=np.linalg.norm(d)/sine
    reach=max(np.linalg.norm(v[:2]-blum.world_xy(blum.B,CUP_SPACER)) for v in face.vertices)
    allowance=float((reach+max_b_speed)*math.radians(step/2))
    return dict(closest_sample=closest,step_degrees=step,
                analytic_speed_bound_mm_per_radian=float(reach+max_b_speed),
                between_sample_allowance_mm=allowance,lower_bound_mm=closest[0]-allowance,
                scope='Door vs cabinet, excluding its commercial hinge internals')


def hinge_samples(fixed,left):
    """Check moving hinge bodies vs furniture/door, with explicit thread regions."""
    failures=[]
    for degrees in range(111):
        moving=blum.posed(left,degrees,CUP_SPACER)
        face=next(p for p in moving if p['name']=='Left-door-face-18')
        hardware=[p for p in moving if p.get('hinge')]
        obstacles=fixed+[face]
        for p in hardware:
            for q in obstacles:
                if p.get('hinge')==q.get('hinge'):continue
                a,b=p['mesh'],q['mesh']
                if np.min(np.minimum(a.bounds[1],b.bounds[1])-np.maximum(a.bounds[0],b.bounds[0]))<=.002:continue
                common=tm.boolean.intersection([a,b],engine='manifold')
                if not len(common.faces):continue
                if q['name'] in p.get('thread_targets',{}):
                    common=tm.boolean.difference([common,p['thread_targets'][q['name']]],engine='manifold')
                volume=abs(float(common.volume)) if len(common.faces) else 0
                if volume>.08:failures.append([degrees,p['name'],q['name'],round(volume,4)])
    return failures


def make_payload(fixed,left,joints,detail):
    # Encode new view meshes through the same single geometry cache. The
    # helper accepts all view keys and preserves per-part four-bar motion.
    data=previous_payload(fixed,left,detail,joints)
    data['linkage']={**blum.SPEC,'world_offset_xy':[34,81]}
    data['detailLabels']={key:[dict(text=str(i+1),point=point,delta=p.get('delta',[0,0,0]))
        for i,(p,point) in enumerate(zip(detail[key],[
            [983,116,846],[984,116,782],[981,97,803],[981,97,778.2],[980.25,97,820]]))]
        for key in ('mount','section')}
    # Delta-pack triangle indices when it compresses better. This changes
    # storage only; assert exact reconstruction before sending the mesh.
    for geometry in data['geo'].values():
        indices=np.frombuffer(base64.b64decode(geometry['f']),dtype='<u2')
        delta=np.diff(indices.astype(np.int64),prepend=0).astype('<u2')
        packed=base64.b64encode(delta.tobytes()).decode()
        if len(gzip.compress(packed.encode()))+15<len(gzip.compress(geometry['f'].encode())):
            assert np.array_equal(np.cumsum(delta.astype(np.int64)).astype('<u2'),indices)
            geometry['f']=packed;geometry['fd']=True
    return data


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);parser.add_argument('--viewer-only',action='store_true');args=parser.parse_args()
    OUT.mkdir(exist_ok=True)
    fixed,left,rows,joints,seats,mounts,machining=assembly();detail=details(fixed,left)
    if not args.viewer_only:
        checks=dict(version='cambusa-v30-review-fixes',fabrication_release=False,
            pegboard=dict(hole_diameter_mm=12,grid_mm=50,count=152,blind_depth_mm=10,
                          remaining_inner_skin_mm=8,universal_hook_compatibility=False),
            right_shelves=dict(blank_mm=[461.5,404,12],front_y_mm=54,wall_front_y_mm=53.5,
                               front_recess_mm=.5),hinge=dict(sku='71B3750',plate='175H3100',
                               cup_spacer_sku='70T3507.21',cup_spacer_mm=1.5,count=3,
                               maximum_degrees=110,height_adjustment_mm=[-2,2],
                               side_adjustment_mm=[-2,2],depth_adjustment_mm=[-2,3],
                               geometry_scope=blum.SPEC['geometry_scope']),poses={})
        for angle in (0,55,90,110):
            posed=fixed+right_parts(0)+blum.posed(left,angle,CUP_SPACER)
            bad,threads=audit_contacts(posed);checks['poses'][angle]=dict(unexpected=bad,thread_contacts=len(threads))
            print('pose',angle,bad,flush=True);assert not bad,bad
            if angle in (0,110):export(OUT/f'cabinet-{angle}.glb',posed)
        checks['door_sweep']=door_sweep(fixed,left);print('door sweep',checks['door_sweep'],flush=True)
        assert checks['door_sweep']['lower_bound_mm']>0
        checks['hinge_sample_step_degrees']=1
        checks['hinge_sample_collisions']=hinge_samples(fixed,left)
        print('hinge collisions',checks['hinge_sample_collisions'][:8],flush=True)
        assert not checks['hinge_sample_collisions']
        checks['right_sweeps']=[audit_leaf(right_leaf(z),fixed+left,z,slot_end(z)) for _,z in SECTIONS]
        assert min(r[1] for r in checks['right_sweeps'])>0
        by_name={p['name']:p for p in fixed}
        checks['view_dependencies']={}
        right_names={p['name'] for p in detail['right']}
        for end,beam in [('Top','Beam-top-side-966'),('Bottom','Beam-body-side-966')]:
            for y in (97,426):
                key=f'Right-wall-M6x45-{end}-{y}'
                assert key in right_names and beam in right_names
                checks['view_dependencies'][key]=beam
        for shelf in [p for p in fixed if p['name'].startswith('Shelf-Right-')]:
            assert shelf['mesh'].bounds[0,1]>=by_name['Right-wall-18']['mesh'].bounds[0,1]+.49
        # The full-height interior skin blocks every peg hole independently of
        # whether the outside hole has a peg installed.
        # Check each peg footprint against the entire remaining back skin.
        probes=[bore([20,y,z],[1,0,0],.01,7.99,5.99) for y,z in PEGBOARD_PATTERN]
        board=by_name['Left-pegboard-18']['mesh']
        checks['closed_peg_hole_backs']=int(sum(abs(overlap_volume(board,p)-p.volume)<.01 for p in probes))
        assert checks['closed_peg_hole_backs']==152
        (OUT/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    for key,parts in detail.items():export(OUT/f'{key}-detail.glb',parts)
    with (OUT/'panels-and-shelves.csv').open('w',newline='') as f:
        writer=csv.writer(f,lineterminator='\n');writer.writerow(['part','a_mm','b_mm','stock_mm','count']);writer.writerows(rows)
    with (OUT/'hinge-machining.csv').open('w',newline='') as f:
        writer=csv.writer(f,lineterminator='\n');writer.writerow(['part','operation','u_mm','v_mm','diameter_mm','depth_mm']);writer.writerows(machining)
    with (OUT/'pegboard-machining.csv').open('w',newline='') as f:
        writer=csv.writer(f,lineterminator='\n')
        writer.writerow(['hole','u_from_front_mm','v_from_bottom_mm','diameter_mm','flat_depth_from_outer_face_mm','remaining_skin_mm'])
        writer.writerows([i,y-53.5,z-800,12,10,8] for i,(y,z) in enumerate(PEGBOARD_PATTERN,1))
    data=make_payload(fixed,left,joints,detail)
    report=json.loads((OUT/'checks.json').read_text())
    report['export_readback']={}
    for angle in (0,110):
        source=fixed+right_parts(0)+blum.posed(left,angle,CUP_SPACER)
        expected={p['name']:p['mesh'] for p in source if p['group']!='prop'}
        actual=load_parts(OUT/f'cabinet-{angle}.glb')
        assert set(actual)==set(expected)
        error=max(float(np.abs(actual[name].bounds-expected[name].bounds).max()) for name in actual)
        assert error<.002,error
        report['export_readback'][angle]=dict(part_count=len(actual),maximum_bounds_error_mm=error)
    vertex_error=0.0
    for p,encoded_part in zip(fixed+left,data['full']):
        local=np.frombuffer(base64.b64decode(data['geo'][encoded_part['geo']]['v']),dtype='<i2').reshape(-1,3)/16
        placed=local@np.array(encoded_part['axes']).reshape(3,3).T+encoded_part['origin']
        error=float(np.abs(placed-p['mesh'].vertices).max());assert error<.055,(p['name'],error)
        vertex_error=max(vertex_error,error)
    report['viewer_maximum_coordinate_error_mm']=vertex_error
    report['physical_verification']='Not performed; fabrication_release remains false'
    report['adjustment_scope']='Cabinet motion checked at neutral adjustment; manufacturer adjustment ranges are recorded, their extreme combinations are not qualified.'
    (OUT/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    encoded=base64.b64encode(gzip.compress(json.dumps(data,separators=(',',':')).encode())).decode()
    result=(ROOT/'work/viewer-v30-template.html').read_text().replace('__MODEL_DATA__',encoded)
    assert len(result.encode())<1_000_000,len(result.encode())
    (OUT/'viewer.html').write_text(result)
    if args.output:args.output.write_text(result)
    print('viewer bytes',len(result.encode()),flush=True)


if __name__=='__main__':main()
