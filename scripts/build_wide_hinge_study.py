"""170° candidate: real 71T6650 six-bar kinematics, 24 mm left board.

This does not release a manufacturing kit. Two source solids are converted;
the remaining hinge bodies are visibly marked kinematic/dimensional proxies.
Door/furniture sweep and cup drilling are checked independently of proxies.
"""
import base64
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import trimesh as tm
from shapely import affinity
from shapely.geometry import LineString

from blum_wide_kinematics import SixBar
from build_aluminum_corner import add, cube, cut, footprint, overlap_volume, panel
from build_direct_axes_v31 import direct_assembly, posed_right
from build_frame_joinery import PEGBOARD_PATTERN, bore
from build_right_lift import export
from audit_assembly import load_parts
from build_concealed_cabinet import audit_contacts
from study_pegboard_thickness import candidate
import blum_inset as old
import build_reviewed_cabinet as reviewed

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/wide-hinge-study'
LINK=SixBar(json.loads((OUT/'linkage.json').read_text())['points'])
CENTERS=old.CENTERS


def world(mesh,z):
    t=np.diag([-1.,1.,-1.,1.]);t[:3,3]=[43,79.5,z]
    return mesh.copy().apply_transform(t)


def posed(left,degrees):
    result=[]
    for p in left:
        if 'wide_body' not in p:result.append(p);continue
        t=LINK.transform(p['wide_body'],degrees)
        result.append(dict(p,mesh=p['mesh'].copy().apply_transform(t),
            thread_targets={name:m.copy().apply_transform(t) for name,m in p.get('thread_targets',{}).items()}))
    return result


def assembly():
    base,_,_,joints,*_=direct_assembly()
    fixed,case=candidate(24,base,with_hinge_pilots=False)
    fixed=[p for p in fixed if not p['name'].startswith('Blum-')]
    board=next(p for p in fixed if p['name']=='Left-pegboard-18')
    door_tools=[];board_tools=[];left=[];machining=[]
    native=np.load(OUT/'factory-meshes.npz')
    # Numeric source keys are kept in the conversion report for provenance.
    print('factory arrays',native.files,flush=True)
    actual={i:tm.Trimesh(native[f'blum-71t6650-{i}-v'],native[f'blum-71t6650-{i}-f'],process=False)
            for i in (1,6)}
    for index,z in enumerate(CENTERS,1):
        for i,m in actual.items():
            target=left if i==1 else fixed
            add(target,f'Blum-wide-{index}-factory-body-{i}',world(m,z),'handle',
                wide_body=i,hinge=index,geometry='factory')
        # These links only expose the real pivot graph; they are not CAD solids.
        for i,names in ((0,'PQ'),(2,'BCD'),(3,'QCE'),(4,'EF')):
            path=LineString([LINK.points[n] for n in names])
            m=panel(path.buffer(1.2,quad_segs=8),2,-1.0,2.0)
            add(left if i else fixed,f'Blum-wide-{index}-schematic-body-{i}',world(m,z),'guide',
                wide_body=i,hinge=index,geometry='kinematic schematic')
        # Cup: nominal drill fit, not the unconverted factory cup B-rep.
        cup=bore([59,41,z],[0,1,0],-10.5,0,17.45)
        flange=cube([46.5,41,z-28.5],[77.5,43.2,z+28.5])
        cup=tm.boolean.union([cup,flange],engine='manifold')
        cup=cut(cup,[bore([59,41,z],[0,1,0],-8.5,2.3,15.4)])
        cup=cut(cup,[bore([68.5,41,zz],[0,1,0],-.1,2.4,1.9) for zz in (z-22.5,z+22.5)])
        add(left,f'Blum-wide-{index}-cup-envelope',cup,'handle',wide_body=5,
            motion='wide5',hinge=index,geometry='dimensional proxy')
        # Purchased 9 mm plate: the wood contact plane and 32 mm drilling
        # pitch are exact source datums, the metal outline is a proxy.
        plate=tm.boolean.union([cube([6.8,-8,-22],[9,8,22]),
                               cube([-8.5,-15,-4.5],[6.8,17.7,4.5])],engine='manifold')
        plate=cut(plate,[bore([9,0,zz],[-1,0,0],-.1,2.4,1.9) for zz in (-16,16)])
        add(fixed,f'Blum-wide-{index}-175H7190-envelope',world(plate,z),'handle',hinge=index,
            geometry='dimensional proxy')
        for zz in (z-16,z+16):
            board_tools.append(bore([34,79.5,zz],[-1,0,0],-.1,13,1.25))
            screw=old.wood_screw([36.2,79.5,zz],[-1,0,0],15)
            add(fixed,f'Blum-wide-{index}-plate-screw-{zz}',screw,'fastener',hinge=index,
                thread_targets={'Left-pegboard-18':bore([34,79.5,zz],[-1,0,0],-.01,12.81,1.8)})
            machining.append(['Left-pegboard-24','inner face',26,zz-800,2.5,13,'pilot; screw final choice pending'])
        door_tools.append(bore([59,41,z],[0,-1,0],-.1,11,17.5))
        machining.append(['Left-door-face-18','back',23,z-803,35,11,'cup; flat bottom'])
        for zz in (z-22.5,z+22.5):
            door_tools.append(bore([68.5,41,zz],[0,-1,0],-.1,13,1.25))
            screw=old.wood_screw([68.5,43.2,zz],[0,-1,0],15)
            add(left,f'Blum-wide-{index}-cup-screw-{zz}',screw,'fastener',wide_body=5,
                motion='wide5',hinge=index,
                thread_targets={'Left-door-face-18':bore([68.5,41,zz],[0,-1,0],-.01,12.81,1.8)})
            machining.append(['Left-door-face-18','back',32.5,zz-803,2.5,13,'pilot; screw final choice pending'])
    grip=panel(LineString([(470,1250),(470,1322)]).buffer(9,quad_segs=16),1,22.9,12.1)
    add(left,'Left-door-face-18',cut(cube([36,23,803],[488,41,1767]),door_tools+[grip]),
        'door',wide_body=5,motion='wide5')
    board['mesh']=cut(board['mesh'],board_tools)
    # All mobile bodies, including the two real source solids, get the same
    # body ID in the exported animation. Nothing uses the old four-bar motion.
    for p in left:
        if 'wide_body' in p:p['motion']=f"wide{p['wide_body']}"
    return fixed,left,joints,case,machining


def velocity_bound(face,end):
    """Conservative planar point speed per radian of input crank phi.

    First triangle extrema are analytic. The second triangle's side-length
    range is bounded using the first triangle's global velocity bounds. This
    bounds gaps between door-clearance samples without numerical derivatives.
    """
    p=LINK.points;l=lambda a,b:float(np.linalg.norm(p[a]-p[b]))
    w=p['P']-p['Q'];v=p['B']-p['P']
    ac=float(w@v);bc=float(w@np.array([-v[1],v[0]]))
    critical=[0,end];base=math.atan2(bc,ac)
    critical += [base+k*math.pi for k in range(-2,3) if 0<=base+k*math.pi<=end]
    ds=[float(w@w+v@v+2*(ac*math.cos(a)+bc*math.sin(a))) for a in critical]
    cosines=[(l('B','C')**2+l('Q','C')**2-d)/(2*l('B','C')*l('Q','C')) for d in ds]
    s1=math.sqrt(1-max(abs(c) for c in cosines)**2)
    d_speed=l('P','B')+(l('P','B')/s1+l('P','B'))/l('B','C')*l('B','D')
    e_speed=l('P','B')/(l('Q','C')*s1)*l('Q','E')
    phis=np.linspace(0,end,10001)
    distances=[]
    for phi in phis:
        q=LINK.state(float(phi))['points'];distances.append(float(np.linalg.norm(q['D']-q['E'])))
    allowance=(d_speed+e_speed)*float(phis[1]-phis[0])/2
    dmin=max(0,min(distances)-allowance);dmax=max(distances)+allowance
    cosines=[(l('D','F')**2+l('E','F')**2-d*d)/(2*l('D','F')*l('E','F')) for d in (dmin,dmax)]
    s2=math.sqrt(1-max(abs(c) for c in cosines)**2)
    cup_speed=(d_speed+e_speed)/(l('D','F')*s2)
    anchor=np.array([43,79.5])+p['D']*[-1,1]
    reach=float(max(np.linalg.norm(q[:2]-anchor) for q in face.vertices))
    return dict(first_triangle_sine_lower_bound=s1,second_triangle_sine_lower_bound=s2,
        d_speed_mm_per_rad=d_speed,e_speed_mm_per_rad=e_speed,
        de_distance_mm=[dmin,dmax],de_sampling_allowance_mm=allowance,
        cup_angular_speed_rad_per_rad=cup_speed,door_reach_mm=reach,
        door_point_speed_mm_per_rad=d_speed+cup_speed*reach)


def sweep(fixed,left,right):
    face=next(p['mesh'] for p in left if p['name']=='Left-door-face-18')
    shape=footprint(face);z0,z1=face.bounds[:,2]
    obstacles=[(p['name'],footprint(p['mesh'])) for p in fixed+right
        if not p['name'].startswith('Blum-') and
        min(z1,p['mesh'].bounds[1,2])-max(z0,p['mesh'].bounds[0,2])>.001]
    closest=(math.inf,None,None);collisions=[]
    end=float(LINK.opening(170)['angles'][1]);count=math.ceil(end/math.radians(.01))
    phis=np.linspace(0,end,count+1)
    bound=velocity_bound(face,end)
    for phi in phis:
        state=LINK.state(float(phi));deg=math.degrees(state['angles'][5])
        t=LINK.transform_state(5,state);a=t[:2,:2];v=t[:2,3]
        moving=affinity.affine_transform(shape,[a[0,0],a[0,1],a[1,0],a[1,1],*v])
        for name,obstacle in obstacles:
            d=float(moving.distance(obstacle))
            if d<closest[0]:closest=(d,float(deg),name)
            area=moving.intersection(obstacle).area
            if area>.001:collisions.append([float(deg),name,float(area)])
    allowance=bound['door_point_speed_mm_per_rad']*float(phis[1]-phis[0])/2
    return dict(degrees=[0,170],input_crank_step_degrees=math.degrees(float(phis[1]-phis[0])),sample_count=len(phis),
                closest_sample_mm=closest,sampled_intersections=collisions,
                velocity_bound=bound,between_sample_allowance_mm=allowance,
                nominal_clearance_lower_bound_mm=closest[0]-allowance-.01,
                scope='door vs furniture and frame; excludes hinge internals',
                continuous_nominal_bound=True,manufacturing_tolerances_qualified=False)


def export_readback(name,parts):
    parts=[dict(p,name='Left-pegboard-24') if p['name']=='Left-pegboard-18' else p for p in parts]
    export(OUT/name,parts)
    actual=load_parts(OUT/name);expected={p['name']:p['mesh'] for p in parts if p['group']!='prop'}
    assert set(actual)==set(expected)
    error=max(float(np.abs(actual[n].bounds-m.bounds).max()) for n,m in expected.items())
    assert error<.002
    return dict(parts=len(actual),maximum_bounds_error_mm=error)


def actual_body_samples(fixed,left,right):
    """Only successfully converted factory solids; no proxy-based assurance."""
    failures=[]
    for d in range(171):
        moving=posed(left,d)
        furniture=[p for p in fixed+right+moving if not p['name'].startswith('Blum-')]
        for p in [p for p in fixed+moving if p.get('geometry')=='factory']:
            for q in furniture:
                a,b=p['mesh'],q['mesh']
                if np.min(np.minimum(a.bounds[1],b.bounds[1])-np.maximum(a.bounds[0],b.bounds[0]))<=.002:continue
                volume=overlap_volume(a,b)
                if volume>.08:failures.append([d,p['name'],q['name'],volume])
    return dict(sample_step_degrees=1,bodies=[1,6],collisions=failures,
                complete_hinge_test=False)


def main():
    sources=json.loads((ROOT/'inputs/blum-wide-hinge-sources.json').read_text())
    for row in sources['sources']:
        assert hashlib.sha256((ROOT/row['file']).read_bytes()).hexdigest()==row['sha256']
    fixed,left,joints,case,machining=assembly()
    case['hinge_screw_wood_penetration_mm']=12.8
    right=posed_right(0)
    report=dict(status='170 degree candidate; not a fabrication release',fabrication_release=False,
                hinge='71T6650',plate='175H7190',plate_spacing_mm=9,
                cup_spacer_mm=0,board_backer_mm=0,board=case,
                geometry_limit='Only factory bodies 1 and 6 converted. Other bodies are labelled proxies/schematic links. Full hinge/wood collision qualification remains open.')
    report['link_length_residual_mm']=max(LINK.residual(float(d)) for d in np.linspace(0,170,1361))
    assert report['link_length_residual_mm']<1e-8
    report['door_sweep']=sweep(fixed,left,right)
    print('door sweep',report['door_sweep'],flush=True)
    assert not report['door_sweep']['sampled_intersections']
    assert report['door_sweep']['nominal_clearance_lower_bound_mm']>0
    report['converted_hinge_bodies']=actual_body_samples(fixed,left,right)
    print('converted bodies',report['converted_hinge_bodies'],flush=True)
    assert not report['converted_hinge_bodies']['collisions']
    # Full furniture and screw audit at selected positions; skip the visibly
    # schematic/unconverted hinge bodies, not their furniture counterparts.
    report['selected_pose_audit']={}
    for d in (0,90,110,170):
        actual=[p for p in fixed+right+posed(left,d) if p.get('geometry') not in ('dimensional proxy','kinematic schematic')]
        bad,threads=audit_contacts(actual)
        report['selected_pose_audit'][d]=dict(unexpected=bad,thread_contacts=len(threads))
        assert not bad,(d,bad)
    face=next(p['mesh'] for p in left if p['name']=='Left-door-face-18')
    report['cup_drilling']=[]
    for z in CENTERS:
        empty=bore([59,41,z],[0,-1,0],.01,10.99,17.49)
        skin=bore([59,30,z],[0,-1,0],.01,6.99,17.49)
        assert overlap_volume(face,empty)<.01
        assert abs(overlap_volume(face,skin)-skin.volume)<.01
        report['cup_drilling'].append(dict(z_mm=z,x_from_left_mm=23,y_back_mm=41,
            diameter_mm=35,depth_mm=11,remaining_skin_mm=7,
            cup_edge_to_door_edge_mm=5.5,fixing_pitch_mm=45,fixing_offset_mm=9.5))
    report['export_readback']={}
    for d in (0,110,170):
        report['export_readback'][d]=export_readback(f'cabinet-{d}.glb',fixed+right+posed(left,d))
    detail=[]
    for p in fixed+left:
        if p['name'] in ('Post-4-23','Left-pegboard-18','Left-door-face-18'):
            m=tm.boolean.intersection([p['mesh'],cube([3,14,848],[115,117,938])],engine='manifold')
            detail.append(dict(p,mesh=m))
        elif p['name'].startswith('Blum-wide-1-'):detail.append(p)
    for d in (0,170):
        export_readback(f'hinge-{d}.glb',posed(detail,d))
    with (OUT/'hinge-machining.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['part','face','u_mm','v_mm','diameter_mm','depth_mm','note']);w.writerows(machining)
    # Reuse all existing views but replace the actual left-door mechanism.
    details=reviewed.details(fixed,left);details['hinge']=detail
    board=next(p['mesh'] for p in fixed if p['name']=='Left-pegboard-18')
    details['pegmount']=[dict(name='Pegboard-24-section',
        mesh=tm.boolean.intersection([board,cube([9,136.5,907],[35,159,956])],engine='manifold'),material='wood',group='body',delta=[0,0,0]),
        dict(name='Example-peg-11.8',mesh=tm.boolean.intersection([
            bore([10,136.5,934.5],[1,0,0],-40.5,15.5,5.9),cube([-31,136.5,907],[35,159,956])],engine='manifold'),
            material='handle',group='example',delta=[-25,0,0])]
    from build_direct_axes_v31 import axis_detail
    details.update({'axis-l':axis_detail(fixed,'L',True),'axis-r':axis_detail(fixed,'R',True)})
    data=reviewed.make_payload(fixed,left,joints,details);data['pivotY']=70
    data['widePoints']={k:v.tolist() for k,v in LINK.points.items()}
    data['wideOffset']=[43,79.5]
    packed=base64.b64encode(gzip.compress(json.dumps(data,separators=(',',':')).encode())).decode()
    html=(ROOT/'work/viewer-wide-hinge-template.html').read_text().replace('__MODEL_DATA__',packed)
    assert len(html.encode())<1_000_000
    (OUT/'viewer.html').write_text(html)
    reference={str(d):{f'wide{i}':dict(matrix=LINK.transform(i,d)[:3,:3].T.flatten().tolist(),
        shift=LINK.transform(i,d)[:3,3].tolist()) for i in range(7)} for d in (0,30,90,110,155,170)}
    (OUT/'kinematics-reference.json').write_text(json.dumps(reference,indent=2)+'\n')
    report['model_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('*.glb')}
    report['viewer_sha256']=hashlib.sha256((OUT/'viewer.html').read_bytes()).hexdigest()
    (OUT/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('viewer bytes',len(html.encode()),flush=True)


if __name__=='__main__':main()
