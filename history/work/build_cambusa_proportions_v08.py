from pathlib import Path
import sys, math, json, csv, zipfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'work/vendor'))
sys.path.insert(0, str(ROOT/'work'))
import numpy as np
import trimesh as tm
from shapely.geometry import box, Point
from shapely.ops import unary_union
from build_mobile_options import add, panel, rounded, scene, books, COLORS
from build_assembly_v1 import cube, cylinder, collision_volume
from render_assembly_v1 import render

OUT = ROOT/'outputs/cambusa-proportions-v08'
OUT.mkdir(parents=True, exist_ok=True)
VIS = Path('./previews/cambusa-proportions-v08.html')
ps, blanks, profiles, plates = [], [], [], []
COLORS.update(wood=[91,64,46,255], inner=[116,83,55,255], back=[71,49,35,255])

def wood(name, poly, axis, at, thick, mat='wood', group='body', **meta):
    add(ps, name, panel(poly, axis, at, thick), mat, group, **meta)
    x0,y0,x1,y1 = poly.bounds
    blanks.append(dict(id=name, thickness_mm=thick, blank_w_mm=round(x1-x0,2), blank_h_mm=round(y1-y0,2), quantity=1, group=group, status='CONCEPT_ONLY_NO_ATTACHMENT_MACHINING'))

def block(name, lo, hi, mat='wood', group='body', **meta):
    e = np.array(hi)-np.array(lo)
    ax = int(np.argmin(e)); ids=[i for i in range(3) if i != ax]
    wood(name, box(lo[ids[0]],lo[ids[1]],hi[ids[0]],hi[ids[1]]),ax,lo[ax],e[ax],mat,group,**meta)

def profile(name,lo,hi):
    add(ps,name,cube(lo,hi),'frame','profile')
    profiles.append(dict(id=name, section_mm='30x30', length_mm=max(np.array(hi)-np.array(lo)), quantity=1, status='CONCEPT_ONLY_END_MACHINING_PENDING'))

def build():
    # Four individual posts, a top ring, two lower side rails and one rear rail.
    # The front is intentionally open. All profiles remain separate parts.
    for ix,x in enumerate([40,930]):
        for iy,y in enumerate([60,440]):
            profile(f'A0-post-{ix}-{iy}',[x,y,4],[x+30,y+30,770])
            add(ps,f'foot-{ix}-{iy}',cylinder(2,[x+15,y+15,2],12,4,24),'frame','foot')
    for iy,y in enumerate([60,440]):profile(f'A1-width-{iy}',[70,y,770],[930,y+30,800])
    for ix,x in enumerate([40,930]):
        profile(f'A1-depth-{ix}',[x,60,770],[x+30,470,800])
        profile(f'A2-low-depth-{ix}',[x,90,4],[x+30,440,34])
    profile('A2-low-rear',[70,440,4],[930,470,34])
    block('B00-bottom',[0,20,800],[1000,500,818])
    block('B01-top',[0,20,1782],[1000,500,1800])
    block('B02-left-side',[0,20,818],[18,500,1782])
    # Pegboard is the actual right side, with no solid backing hiding the holes.
    # Hole rows avoid shelf faces. Lower drawer/hinge zones need later accessory exclusions.
    zs=list(range(840,1741,50))
    holes=[(y,z) for y in range(50,451,50) for z in zs]
    poly=box(20,818,500,1782).difference(unary_union([Point(y,z).buffer(6,resolution=4) for y,z in holes]))
    wood('B03-right-pegboard',poly,0,982,18,group='pegboard')
    block('B04-back',[18,488,818],[982,500,1782],'back','back')
    block('B05-divider',[491,104,818],[509,488,1782])
    for i,z in enumerate([1140,1460]):block(f'B1{i}-left-shelf',[18,104,z],[491,488,z+18])
    for i,z in enumerate([1160,1460]):block(f'B2{i}-right-shelf',[509,104,z],[982,488,z+18])
    for side,(x0,x1,sgn,piv) in enumerate([(2,498,-1,[0,0,0]),(502,998,1,[1000,0,0])]):
        owner=f'B3{side}-door'
        meta=dict(owner=owner,door_id=side,pivot=piv,sign=sgn)
        # Conceptual recessed pull; exact commercial part and route unselected.
        hx=x1-21 if side==0 else x0+21
        pull=rounded(hx-5,1230,hx+5,1360,4)
        wood(owner,rounded(x0,804,x1,1796,3).difference(pull),1,0,18,group='door',**meta)
        add(ps,owner+'-recess',panel(pull,1,12,4),'frame','door',**meta)
        # Six removable shallow trays, arranged inside both doors.
        xa,xb=(48,452) if side==0 else (548,952)
        for i,z in enumerate([940,1260,1580]):
            prefix=f'T{side}{i}'
            block(prefix+'-bottom',[xa,18,z],[xb,83,z+9],'inner','door',**meta)
            block(prefix+'-lip',[xa,74,z+9],[xb,83,z+49],'inner','door',**meta)
            block(prefix+'-left',[xa,18,z+9],[xa+9,74,z+49],'inner','door',**meta)
            block(prefix+'-right',[xb-9,18,z+9],[xb,74,z+49],'inner','door',**meta)
    # 473 mm bay: Tandem-family preliminary width = 473 - 42 + 2*12 = 455.
    # Tray storage consumes depth, therefore 350 nominal runner / 340 box,
    # rather than silently retaining the prior 400 runner.
    for i,z in enumerate([828,982]):
        meta=dict(drawer_id=i)
        block(f'D{i}-left',[518,134,z+19],[530,474,z+129],'inner','drawer',**meta)
        block(f'D{i}-right',[961,134,z+19],[973,474,z+129],'inner','drawer',**meta)
        block(f'D{i}-front',[530,134,z+19],[961,146,z+129],'inner','drawer',**meta)
        block(f'D{i}-rear',[530,462,z+19],[961,474,z+129],'inner','drawer',**meta)
        block(f'D{i}-bottom',[518,134,z+10],[973,474,z+19],'inner','drawer',**meta)
        block(f'D{i}-face',[513,122,z],[978,134,z+142],'inner','drawer',**meta)
        add(ps,f'D{i}-pull',cube([724,118,z+122],[768,122,z+128]),'frame','drawer',**meta)
        for k,x in enumerate([511,972]):add(ps,f'runner-{i}-{k}',cube([x,126,z+1],[x+5,476,z+10]),'metal','runner')
    books(ps,60,210,1158,6)
    books(ps,555,210,1178,7)
    books(ps,60,210,1478,6)
    return holes

def transformed(angle=0, travel=0, drawer=1, exploded=False):
    out=[]
    for p in ps:
        q=p.copy();q['mesh']=p['mesh'].copy();off=[0,0,0]
        if p['group']=='door':q['mesh'].apply_transform(tm.transformations.rotation_matrix(p['sign']*math.radians(angle),[0,0,1],point=p['pivot']))
        if p['group']=='drawer' and p['drawer_id']==drawer:off[1]-=travel
        if exploded:
            if p['group']=='door':off[1]-=270
            elif p['group']=='drawer':off[1]-=420
            elif p['group']=='pegboard':off[0]+=160
            elif p['group']=='back':off[1]+=170
            elif p['name']=='B01-top':off[2]+=120
            elif p['name']=='B02-left-side':off[0]-=120
        q['mesh'].apply_translation(off);out.append(q)
    return out

def intersections(a,b):
    hits=[]
    for p in a:
        for q in b:
            if p['name']==q['name']:continue
            v=collision_volume(p['mesh'],q['mesh'])
            if v>.2:hits.append([p['name'],q['name'],round(v,2)])
    return hits

def main():
    holes=build()
    for file,rows in [('plywood-concept-blanks.csv',blanks),('base-profile-concept-blanks.csv',profiles)]:
        with (OUT/file).open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    for name,angle,travel,exploded in [('closed',0,0,False),('open',145,180,False),('exploded',0,0,True)]:
        parts=transformed(angle,travel,1,exploded)
        (OUT/(name+'.glb')).write_bytes(scene(parts).export(file_type='glb'))
        render(parts,1400,1150,yaw=24 if name=='open' else 34,pitch=15).save(OUT/(name+'.png'))
    invalid=[p['name'] for p in ps if not p['mesh'].is_volume]
    fixed=[p for p in ps if p['group'] in ['body','back','pegboard','profile']]
    hits=[]
    for i,p in enumerate(fixed):hits+=intersections([p],fixed[i+1:])
    door_hits=[]
    for a in [0,5,10,20,30,45,60,90,120,135,145,155]:
        parts=transformed(a)
        doors=[p for p in parts if p['group']=='door']
        obstacles=fixed+[p for p in parts if p['group']=='drawer']
        door_hits += [dict(angle=a,parts=h) for h in intersections(doors,obstacles)]
    drawer_hits=[]
    for drawer in [0,1]:
        for travel in [0,60,120,180,240,280]:
            parts=transformed(145,travel,drawer)
            moving=[p for p in parts if p['group']=='drawer' and p['drawer_id']==drawer]
            obstacles=[p for p in parts if p['group'] in ['body','back','pegboard','door'] or (p['group']=='drawer' and p['drawer_id']!=drawer)]
            drawer_hits += [dict(drawer=drawer,travel_mm=travel,parts=h) for h in intersections(moving,obstacles)]
    report=dict(status='CONCEPT ONLY — NOT FOR CUTTING OR PURCHASE',dimensions_mm=[1000,1800,500],parts=len(ps),plywood_blanks=len(blanks),base_profile_blanks=len(profiles),body_height_mm=1000,base_height_mm=800,casters=0,profile_metres=float(sum(r['length_mm'] for r in profiles)/1000),pegboard_holes=len(holes),invalid_meshes=invalid,static_major_intersections=hits,sampled_door_intersections=door_hits,sampled_drawer_intersections=drawer_hits,scope='Ideal fixed-axis rotations and straight drawer motion only. Actual hinges, attachments, assembly access, strength and stability are not validated.')
    (OUT/'geometry-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    payload=[]
    for p in ps:
        m=p['mesh'];n=m.face_normals
        payload.append({**{k:v for k,v in p.items() if k!='mesh'},'v':np.round(m.vertices,2).tolist(),'f':m.faces.tolist(),'edge':[]})
    data=dict(parts=payload,colors=COLORS)
    (ROOT/'work/cambusa-proportions-v08-data.json').write_text(json.dumps(data,separators=(',',':')))
    VIS.write_text((ROOT/'work/cambusa-proportions-v08-template.html').read_text().replace('__MODEL_DATA__',json.dumps(data,separators=(',',':'))))
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
