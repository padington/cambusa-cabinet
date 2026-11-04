from pathlib import Path
import sys,math,json,csv,zipfile,copy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work/vendor'));sys.path.insert(0,str(ROOT/'work'))
import numpy as np
import trimesh as tm
from shapely.geometry import box,Point,Polygon
from shapely.ops import unary_union
from build_mobile_options import add,ply,panel,rounded,scene,COLORS,pack_rects,books
from build_assembly_v1 import cube,cylinder,diff,collision_volume
from render_assembly_v1 import render,font
from PIL import Image,ImageDraw

OUT=ROOT/'outputs/order-preparation-v06';OUT.mkdir(parents=True,exist_ok=True)
COLORS['inner']=[115,84,57,255]
profiles=[];blanks=[];ps=[];shapes={}
def wood(name,poly,axis,at,t,mat='wood',group='body',**meta):
    m=panel(poly,axis,at,t);add(ps,name,m,mat,group,**meta)
    x0,y0,x1,y1=poly.bounds
    blanks.append(dict(id=name,thickness_mm=t,blank_w_mm=round(x1-x0,2),blank_h_mm=round(y1-y0,2),quantity=1,group=group))
    shapes[name]=(poly,axis,at,t)

def profile(name,lo,hi):
    e=np.array(hi)-np.array(lo);axis=int(np.argmax(e))
    assert sorted(e.tolist())[:2]==[30,30]
    profiles.append(dict(id=name,section_mm='30x30',slot='8 mm, exact system pending',length_mm=int(e[axis]),quantity=1))
    ply(ps,name,lo,hi,'frame','profile')

def casters():
    # Envelope matches a 75 mm / 100 mm-high candidate. This is not the
    # vendor's exact product mesh. Its 60x60 plate stays a nominal envelope.
    for i,(x,y) in enumerate([(70,75),(930,75),(70,425),(930,425)]):
        yy=y+29
        tire=diff(cylinder(0,[x,yy,37.5],37.5,25,32),[cylinder(0,[x,yy,37.5],22,30,32)])
        add(ps,f'caster-{i}-tire',tire,'rubber','wheel')
        add(ps,f'caster-{i}-hub',cylinder(0,[x,yy,37.5],21.8,24,24),'frame','wheel')
        fork=Polygon([(y+20,35),(y+38,35),(y+11,85),(y-11,85)])
        for sign in [-1,1]:add(ps,f'caster-{i}-fork-{sign}',panel(fork,0,x+sign*19-2,4),'frame','wheel')
        add(ps,f'caster-{i}-crown',cube([x-22,y-14,84],[x+22,y+14,89]),'frame','wheel')
        add(ps,f'caster-{i}-swivel',cylinder(2,[x,y,92],19,6,24),'metal','wheel')
        add(ps,f'caster-{i}-plate',cube([x-30,y-30,95],[x+30,y+30,100]),'frame','wheel')
        add(ps,f'caster-{i}-brake',cube([x-10,y-32,76],[x+10,y-13,81]),'metal','wheel')

def face(name,x0,x1,z0,z1,side=None,y=10,t=18,group='door',**meta):
    if side:
        meta.update(pivot=[x0-2 if side=='left' else x1+2,y-2,0],sign=-1 if side=='left' else 1,owner=name)
    wood(name,rounded(x0,z0,x1,z1,4),1,y,t,group=group,**meta)
    hx=x1-22 if side=='left' else x0+22;zc=(z0+z1)/2
    add(ps,name+'-handle',panel(rounded(hx-4,zc-38,hx+4,zc+38,3),1,y-7,7),'frame',group,**meta)
    return meta

def build():
    casters()
    wood('B00-base',box(0,0,1000,500),2,100,18)
    for ix,x in enumerate([0,477,952]):
        for iy,y in enumerate([0,464]):profile(f'A-post-{ix}-{iy}',[x,y,118],[x+30,y+30,1182])
    for j,z in enumerate([118,448,798,1152]):
        for iy,y in enumerate([0,464]):
            if not (j==1 and iy==0):profile(f'A-cross-left-{j}-{iy}',[30,y,z],[477,y+30,z+30])
            profile(f'A-cross-right-{j}-{iy}',[507,y,z],[952,y+30,z+30])
        for ix,x in enumerate([0,477,952]):profile(f'A-depth-{j}-{ix}',[x,30,z],[x+30,464,z+30])
    for i,z in enumerate([148,478,828]):
        poly=box(30,30,952,464)
        if i==1:poly=poly.difference(box(29,29,477,104))
        # 0.3 mm relief around the continuous rear central post is not needed:
        # all posts end outside the shelf depth, at y<=30 or y>=470.
        wood(f'B0{i+1}-shelf',poly,2,z,18)
    wood('B04-top',box(0,0,1000,500),2,1182,18)
    for i,(z0,z1) in enumerate([(166,448),(496,798),(846,1152)]):
        wood(f'B1{i}-partition',box(30,z0,464,z1),0,489,18)
    for i,(z0,z1) in enumerate([(166,478),(496,828),(846,1182)]):
        wood(f'B2{i}-left-side',box(30,z0,464,z1),0,30,18)
        wood(f'B3{i}-right-side',box(30,z0,464,z1),0,934,18)
    wood('B40-back',box(0,118,982,1182),1,494,6,'back','back')
    centres=[(y,z) for y in range(50,451,50) for z in range(190,1141,50)]
    peg=rounded(0,118,500,1182,7).difference(unary_union([Point(y,z).buffer(6,resolution=4) for y,z in centres]))
    wood('B50-pegboard',peg,0,982,18,group='pegboard')
    left=face('B60-left-door',34,473,170,790,'left')
    face('B61-right-door',511,948,170,440,'right')
    for i,z in enumerate([230,580]):
        for n,lo,hi in [('bottom',[80,28,z],[440,98,z+9]),('lip',[80,89,z+9],[440,98,z+43]),('left',[80,28,z+9],[89,89,z+43]),('right',[431,28,z+9],[440,89,z+43])]:
            axis=2 if n=='bottom' else 1 if n=='lip' else 0
            p2=box(lo[0],lo[1],hi[0],hi[1]) if axis==2 else box(lo[0],lo[2],hi[0],hi[2]) if axis==1 else box(lo[1],lo[2],hi[1],hi[2])
            wood(f'B7{i}-{n}',p2,axis,lo[axis],hi[axis]-lo[axis],'inner','door',**left)
    for i,z in enumerate([170,304]):
        meta=dict(drawer_id=i)
        def wall(n,lo,hi,axis,t):
            po=box(lo[1],lo[2],hi[1],hi[2]) if axis==0 else box(lo[0],lo[2],hi[0],hi[2]) if axis==1 else box(lo[0],lo[1],hi[0],hi[1])
            wood(f'D{i}-{n}',po,axis,lo[axis],t,'inner','drawer',**meta)
        # 427 mm opening, 409 mm outer box, 385 mm inner width.
        wall('left',[516,46,z+22],[528,436,z+122],0,12)
        wall('right',[913,46,z+22],[925,436,z+122],0,12)
        wall('front',[528,46,z+22],[913,58,z+122],1,12)
        wall('rear',[528,424,z+22],[913,436,z+122],1,12)
        wall('bottom',[516,46,z+13],[925,436,z+22],2,9)
        face(f'D{i}-face',515,926,z,z+130,None,y=34,t=12,group='drawer',**meta)
        for k,x in enumerate([510,925]):
            add(ps,f'runner-{i}-{k}',cube([x,51,z+1],[x+6,441,z+12]),'metal','runner')
    books(ps,75,140,846,6);books(ps,545,110,496,7)
    return centres

def ascii_dxf(path,poly):
    # Quote drawings only: outline plus hole contours. Exact attachment
    # machining is intentionally absent until fittings and tools are settled.
    lines=['0','SECTION','2','HEADER','9','$ACADVER','1','AC1015','9','$INSUNITS','70','4','0','ENDSEC','0','SECTION','2','ENTITIES']
    def ring(coords,layer):
        pts=list(coords)[:-1]
        lines.extend(['0','LWPOLYLINE','100','AcDbEntity','8',layer,'100','AcDbPolyline','90',str(len(pts)),'70','1'])
        for x,y in pts:lines.extend(['10',f'{x:.4f}','20',f'{y:.4f}'])
    ring(poly.exterior.coords,'OUTLINE_QUOTE_ONLY')
    for r in poly.interiors:ring(r.coords,'HOLES_QUOTE_ONLY')
    lines.extend(['0','ENDSEC','0','EOF']);path.write_text('\n'.join(lines)+'\n')

def views(mode):
    out=[]
    for p in ps:
        q=p.copy();q['mesh']=p['mesh'].copy();offset=[0,0,0]
        if mode=='open':
            if p['group']=='door':q['mesh'].apply_transform(tm.transformations.rotation_matrix(p['sign']*math.radians(100),[0,0,1],point=p['pivot']))
            elif p['group']=='drawer' and p['drawer_id']==1:offset[1]=-180
        elif mode=='exploded':
            if p['group']=='door':offset[1]=-250
            elif p['group']=='drawer':offset[1]=-420
            elif p['group']=='pegboard':offset[0]=190
            elif p['group']=='back':offset[1]=200
            elif p['group']=='wheel':offset[2]=-110
            elif p['name']=='B04-top':offset[2]=180
            elif p['name'].endswith('left-side'):offset[0]=-100
            elif p['name'].endswith('right-side'):offset[0]=100
        q['mesh'].apply_translation(offset);out.append(q)
    return out

def main():
    centres=build();print('Parts',len(ps),'profiles',len(profiles),'plywood',len(blanks),flush=True)
    for name,rows in [('profile-blanks.csv',profiles),('plywood-blanks.csv',blanks)]:
        with (OUT/name).open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    drawing=OUT/'quote-outlines';drawing.mkdir(exist_ok=True)
    for name,(poly,axis,at,t) in shapes.items():
        x0,y0,x1,y1=poly.bounds
        from shapely.affinity import translate
        p=translate(poly,-x0,-y0)
        ascii_dxf(drawing/(name+'.dxf'),p)
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{x1-x0}mm" height="{y1-y0}mm" viewBox="0 0 {x1-x0} {y1-y0}"><g fill="none" stroke="black" stroke-width="0.3">'
        for coords in [p.exterior.coords,*[r.coords for r in p.interiors]]:
            svg+='<path d="M '+' L '.join(f'{x:.3f},{y:.3f}' for x,y in coords)+' Z"/>'
        (drawing/(name+'.svg')).write_text(svg+'</g></svg>')
    for mode in ['assembled','open','exploded']:
        parts=views(mode)
        (OUT/(mode+'.glb')).write_bytes(scene(parts).export(file_type='glb'))
        render(parts,1100,1100,yaw=34,pitch=17).save(OUT/(mode+'.png'))
    invalid=[p['name'] for p in ps if not p['mesh'].is_volume]
    structural=[p for p in ps if p['group'] in ['body','profile','back','pegboard','door']]
    hits=[]
    for i,p in enumerate(structural):
        for q in structural[i+1:]:
            if p.get('owner') and p.get('owner')==q.get('owner'):continue
            v=collision_volume(p['mesh'],q['mesh'])
            if v>.2:hits.append([p['name'],q['name'],round(v,2)])
    assert not invalid,invalid
    report=dict(parts=len(ps),plywood_parts=len(blanks),profile_parts=len(profiles),profile_metres=sum(p['length_mm'] for p in profiles)/1000,pegboard_holes=len(centres),invalid_meshes=invalid,closed_major_intersections=hits,
                status='QUOTE / DESIGN REVIEW ONLY; attachment machining and exact fittings are unresolved; not released for cutting or full purchase')
    (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (OUT/'hardware-candidates.json').write_text((ROOT/'work/order_hardware_candidates.json').read_text())
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
