"""v32 external hinge-node fit: complete supplier CAD + machined rear reliefs.

Converted supplier solids overlap internally; the origin is not independently
confirmed. This is not a release of the hinge or a physical cabinet load test.
"""
import base64,csv,gzip,hashlib,json
from pathlib import Path
import numpy as np
import trimesh as tm
from shapely.geometry import LineString,box as box2

from build_aluminum_corner import add,cube,cut,panel
from build_direct_axes_v31 import direct_assembly,posed_right,axis_detail
from build_frame_joinery import bore
from build_right_lift import export
from study_pegboard_thickness import candidate
from build_wide_hinge_study import LINK,CENTERS,world,posed,export_readback
import build_reviewed_cabinet as reviewed

ROOT=Path(__file__).resolve().parents[1];CAD=ROOT/'outputs/wide-hinge-verification'
OUT=ROOT/'outputs/cambusa-v32-hinge-node'


def build():
    base,_,_,joints,*_=direct_assembly();fixed,case=candidate(24,base,with_hinge_pilots=False)
    fixed=[p for p in fixed if not p['name'].startswith('Blum-')];left=[]
    data=np.load(CAD/'factory-visual-meshes.npz');screws=np.load(CAD/'screw-meshes.npz')
    source={i:tm.Trimesh(data[f'blum-71t6650-{i}-v'],data[f'blum-71t6650-{i}-f'],process=True) for i in range(7)}
    plate=tm.Trimesh(data['blum-175h7190-0-v'],data['blum-175h7190-0-f'],process=True)
    leaf_tools=[];side_tools=[];machining=[]
    for j,z in enumerate(CENTERS,1):
        for i,m in source.items():
            add(fixed if i in (0,6) else left,f'Blum-{j}-71T6650-body-{i}',world(m,z),'handle',
                hinge=j,wide_body=i,geometry='supplier external CAD',
                **({'motion':f'wide{i}'} if i not in (0,6) else {}))
        add(fixed,f'Blum-{j}-175H7190',world(plate,z),'handle',hinge=j,geometry='supplier external CAD')
        leaf_tools.append(bore([59,41,z],[0,-1,0],-.1,11.2,17.6))
        relief=box2(33,z-12.5,45.5,z+12.5).buffer(-3).buffer(3,quad_segs=16)
        leaf_tools.append(panel(relief,1,37.8,3.3))
        machining += [['Left-door-face-18','back','cup',23,z-803,35.2,11.2,'flat bottom'],
                      ['Left-door-face-18','back','relief',0,z-803,9.5,3.2,'height 25; internal R3; open to hinge edge']]
        for zz in (z-22.5,z+22.5):
            leaf_tools.append(bore([68.5,41,zz],[0,-1,0],-.1,8,1.35))
            machining.append(['Left-door-face-18','back','pilot',32.5,zz-803,2.7,8,'609.1500'])
        for zz in (z-16,z+16):
            side_tools.append(bore([34,79.5,zz],[-1,0,0],-.1,8,1.35))
            machining.append(['Left-pegboard-24','inner','pilot',26,zz-800,2.7,8,'609.1500'])
        for kind,prototypes,targets,shifts in (
            ('plate',fixed,'Left-pegboard-18',(0,-32)),('cup',left,'Left-door-face-18',(0,-45))):
            native=tm.Trimesh(screws[f'{kind}-v'],screws[f'{kind}-f'],process=True)
            for k,delta in enumerate(shifts,1):
                mesh=world(native.copy().apply_translation([0,0,delta]),z)
                zz=z-(16 if kind=='plate' else 22.5)-delta
                region=(bore([34,79.5,zz],[-1,0,0],-.01,12.6,1.8) if kind=='plate' else
                        bore([68.5,41,zz],[0,-1,0],-.01,12.55,1.8))
                add(prototypes,f'Blum-{j}-609.1500-{kind}-{k}',mesh,'fastener',hinge=j,
                    geometry='nominal purchased screw envelope',thread_targets={targets:region},
                    **({'motion':'wide5','wide_body':5} if kind=='cup' else {}))
    grip=panel(LineString([(470,1250),(470,1322)]).buffer(9,quad_segs=16),1,22.9,12.1)
    add(left,'Left-door-face-18',cut(cube([36,23,803],[488,41,1767]),leaf_tools+[grip]),
        'door',wide_body=5,motion='wide5')
    board=next(p for p in fixed if p['name']=='Left-pegboard-18');board['mesh']=cut(board['mesh'],side_tools)
    return fixed,left,joints,machining


def main():
    OUT.mkdir(exist_ok=True);fixed,left,joints,machining=build()
    right=posed_right(0);report=dict(version='cambusa-v32-hinge-node',geometry_source='all 7 hinge bodies + real mounting plate',
        actual_factory_body_count=24,cup_spacers=0,side_backers=0,
        supplier_internal_collision_qualification=False,physical_load_test=False,complete_cabinet_release=False)
    from audit_assembly import load_parts
    report['exports']={}
    for d in (0,110,170):
        parts=fixed+right+posed(left,d)
        parts=[dict(p,name='Left-pegboard-24') if p['name']=='Left-pegboard-18' else p for p in parts]
        path=OUT/f'cabinet-{d}.glb';export(path,parts)
        read=load_parts(path);expected={p['name']:p['mesh'] for p in parts if p['group']!='prop'}
        assert set(read)==set(expected)
        error=max(float(np.abs(read[n].bounds-m.bounds).max()) for n,m in expected.items());assert error<.002
        report['exports'][d]=dict(parts=len(read),bounds_error_mm=error,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    detail=[]
    for p in fixed+left:
        if p['name'].startswith('Blum-1-'):detail.append(p)
        elif p['name'] in ('Post-4-23','Left-pegboard-18','Left-door-face-18'):
            detail.append(dict(p,mesh=tm.boolean.intersection([p['mesh'],cube([3,14,848],[130,120,938])],engine='manifold')))
    for d in (0,170):export(OUT/f'hinge-{d}.glb',posed(detail,d))
    # Wood-only model exposes the actual receiving recesses for inspection.
    export(OUT/'left-door-machined.glb',[p for p in left if p['name']=='Left-door-face-18'])
    # This viewer focuses on the hinge node. The older version retains the
    # independent axle, mounting and foot inspection views.
    details={k:[] for k in ('mount','section','right','corner','foot','hinge','pegmount','axis-l','axis-r')}
    details['hinge']=detail
    leaf=next(p for p in left if p['name']=='Left-door-face-18')
    details['doorwood']=[{k:leaf[k] for k in ('name','mesh','material','group')}]
    data=reviewed.make_payload(fixed,left,joints,details);data['pivotY']=70
    data['widePoints']={k:v.tolist() for k,v in LINK.points.items()};data['wideOffset']=[43,79.5]
    packed=base64.b64encode(gzip.compress(json.dumps(data,separators=(',',':')).encode())).decode()
    html=(ROOT/'work/viewer-full-blum-template.html').read_text().replace('__MODEL_DATA__',packed)
    print('viewer bytes',len(html.encode()),flush=True)
    if len(html.encode())>=1_000_000:raise ValueError('Inline viewer exceeds 1 MB')
    (OUT/'viewer.html').write_text(html)
    with (OUT/'hinge-machining.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['part','face','operation','u_mm','v_mm','diameter_or_width_mm','depth_mm','note']);w.writerows(machining)
    (OUT/'model-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
