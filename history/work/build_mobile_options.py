from pathlib import Path
import sys, json, math, csv, zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work/vendor'))
import numpy as np
import trimesh as tm
from shapely.geometry import Polygon, box, Point
from shapely.ops import unary_union
from build_assembly_v1 import cube, cylinder, diff, collision_volume
from render_assembly_v1 import render, COLORS, font
from PIL import Image, ImageDraw

OUT=ROOT/'outputs/mobile-cabinet-options-v04'
OUT.mkdir(parents=True,exist_ok=True)
COLORS.update(wood=[91,64,46,255],back=[65,47,37,255],metal=[118,124,125,255],
              frame=[42,45,44,255],rubber=[33,35,34,255],key=[128,91,56,255],
              book=[120,123,111,255],book2=[144,125,100,255],paper=[184,176,155,255])

def rounded(x0,y0,x1,y1,r=5):
    return box(x0+r,y0+r,x1-r,y1-r).buffer(r,resolution=4)

def panel(poly,axis,lo,t):
    m=tm.creation.extrude_polygon(poly,t,engine='earcut')
    if axis==0:m.vertices=m.vertices[:,[2,0,1]]
    elif axis==1:m.vertices=m.vertices[:,[0,2,1]];m.invert()
    tr=np.zeros(3);tr[axis]=lo;m.apply_translation(tr)
    return m

def add(ps,name,m,mat='wood',group='body',**kw):
    ps.append(dict(name=name,mesh=m,material=mat,group=group,**kw))

def wheels(ps):
    # Generic 65 mm wheel / 104 mm assembly envelope, not a purchased SKU.
    for i,(x,y) in enumerate([(65,62),(935,62),(65,288),(935,288)]):
        prefix=f'caster-{i}'
        tire=diff(cylinder(0,[x,y,32.5],32.5,25,32),[cylinder(0,[x,y,32.5],20,30,32)])
        add(ps,prefix+'-tire',tire,'rubber','wheel')
        add(ps,prefix+'-hub',cylinder(0,[x,y,32.5],19.8,24,24),'frame','wheel')
        add(ps,prefix+'-axle',cylinder(0,[x,y,32.5],4,43,16),'metal','wheel')
        for side in [-1,1]:
            add(ps,prefix+f'-fork{side}',cube([x+side*19-2,y-10,30],[x+side*19+2,y+10,82]),'frame','wheel')
        add(ps,prefix+'-crown',cube([x-22,y-14,82],[x+22,y+14,88]),'frame','wheel')
        add(ps,prefix+'-swivel',cylinder(2,[x,y,93],18,10,24),'metal','wheel')
        add(ps,prefix+'-plate',cube([x-27,y-25,98],[x+27,y+25,104]),'frame','wheel')
        # A brake pedal is deliberately shown on all four conceptual casters.
        add(ps,prefix+'-brake',cube([x-10,y-31,67],[x+10,y-12,72]),'metal','wheel')

def door(ps,name,x0,x1,z0,z1,front=0,hinge='left'):
    poly=rounded(x0,z0,x1,z1,5)
    hx=x1-32 if hinge=='left' else x0+32
    pull=box(hx-4,z1-50,hx+4,z1-30).buffer(5,resolution=5)
    m=panel(poly.difference(pull),1,front,18)
    pivot=[x0-2 if hinge=='left' else x1+2,front-2,0]
    add(ps,name,m,'wood','door',pivot=pivot,sign=-1 if hinge=='left' else 1)

def books(ps,x0,y,z,n=6):
    for i in range(n):
        w=[27,32,23,35,24,30][i%6];h=[225,242,214,231,238,222][i%6]
        add(ps,f'prop-book-{len(ps)}',cube([x0,y,z],[x0+w,y+160,z+h]),'book' if i%2 else 'book2','prop')
        x0+=w+4

def ply(ps,name,lo,hi,mat='wood',group='body'):
    add(ps,name,cube(lo,hi),mat,group)

def build(key):
    ps=[];wheels(ps)
    if key=='clean':
        # Lower front remains vertical for ordinary inset hinges. The upper
        # contour recedes 65 mm, echoing the user's sloping desk references.
        outer=Polygon([(0,104),(350,104),(350,1200),(65,1200),(0,760)])
        outer=outer.buffer(-5).buffer(5,resolution=4)
        for x,n in [(0,'left'),(982,'right')]:add(ps,'frame-'+n,panel(outer,0,x,18))
        for i,(z,y) in enumerate([(104,20),(452,20),(800,20),(1182,68)]):
            add(ps,f'shelf-{i}',panel(rounded(18,y,982,338,4),2,z,18))
        for i,(z0,z1) in enumerate([(122,452),(470,800),(818,1182)]):
            ply(ps,f'partition-{i}',[491,68 if i==2 else 22,z0],[509,330,z1])
        ply(ps,'back-panel',[18,338,122],[982,344,1182],'back','back')
        door(ps,'door-tall-left',22,487,126,792,0,'left')
        door(ps,'door-low-right',513,978,126,444,0,'right')
        books(ps,545,70,470,7);books(ps,65,115,818,6)
        title='Скошенный корпус';detail='Скрытые готовые защёлки; корпус собирается руками. Печать не нужна.'
    elif key=='aluminium':
        # 30 mm solid envelopes of extrusion, not the manufacturer's section CAD.
        for x in [0,970]:
            for y in [0,320]:ply(ps,f'profile-post-{x}-{y}',[x,y,104],[x+30,y+30,1200],'frame','profile')
        for j,z in enumerate([104,440,788,1170]):
            for y in [0,320]:ply(ps,f'profile-rail-{j}-{y}',[30,y,z],[970,y+30,z+30],'frame','profile')
            for x in [0,970]:ply(ps,f'profile-depth-{j}-{x}',[x,30,z],[x+30,320,z+30],'frame','profile')
        for i,z in enumerate([134,470,818,1152]):ply(ps,f'shelf-{i}',[30,30,z],[970,314,z+18])
        for i,(z0,z1) in enumerate([(152,470),(488,818),(836,1152)]):
            ply(ps,f'partition-{i}',[491,32,z0],[509,314,z1])
        # Flush infill side sheets only behind the lower closed storage.
        for i,(z0,z1) in enumerate([(152,440),(488,788)]):
            ply(ps,f'side-infill-left-{i}',[12,30,z0],[30,314,z1])
            ply(ps,f'side-infill-right-{i}',[970,30,z0],[988,314,z1])
        ply(ps,'back-panel',[30,314,152],[970,320,1152],'back','back')
        door(ps,'door-low-left',34,487,156,432,0,'left')
        door(ps,'door-mid-right',513,966,492,780,0,'right')
        books(ps,78,75,488,7);books(ps,545,90,836,6)
        title='Тонкий алюминий';detail='Профиль 30 × 30 мм. Каркас заранее собирает мастер; винты скрыты в профиле.'
    else:
        # A stepped frame-and-shelf concept. Flat wedges illustrate a joint
        # direction only: exact tabs, access and hand forces need a prototype.
        for x,n,H in [(28,'left',866),(954,'right',1200)]:
            outer=Polygon([(0,104),(350,104),(350,H),(65,H),(0,160)])
            for za,zb in [(146,414),(488,758),(834,H-34)]:
                if zb>za:
                    yf=25+(za-104)*.06
                    outer=outer.difference(rounded(yf+30,za,315,zb,9))
            for z in [104,452,800,1182]:
                if z<H:outer=outer.difference(box(-10,z-.4,360,z+18.4))
            # The continuous rear strip bridges the narrow tab slots below.
            outer=Polygon([(0,104),(350,104),(350,H),(65,H),(0,160)])
            for za,zb in [(146,414),(488,758),(834,H-34)]:
                if zb>za:outer=outer.difference(rounded(60+(za-104)*.025,za,312,zb,9))
            for z in [104,452,800,1182]:
                if z<H:
                    for ya,yb in ([(0,350)] if z==104 else [(0,125),(272,328)]):outer=outer.difference(box(ya,z-.4,yb,z+18.4))
            add(ps,'frame-'+n,panel(outer,0,x,18))
        for i,z in enumerate([104,452,800,1182]):
            x0=491 if i==3 else 46; xf=500 if i==3 else 18
            body=rounded(x0,65,954,338,4)
            for xa,xb in ([(xf,46)] if i<3 else [])+[(954,982)]:
                for ya,yb in [(65,120),(276,324)]:body=body.union(box(xa,ya,xb,yb))
            if i==0:body=rounded(0,0,1000,350,4)
            add(ps,f'shelf-{i}',panel(body,2,z,18))
            for sx,H in [(18,866),(978,1200)]:
                if i>0 and z<H and (i<3 or sx>500):
                    for yy in [87,296]:
                        ztop=min(1200,z+48)
                        wedge=Polygon([(sx-3,z-8),(sx+3,z-8),(sx+8,ztop),(sx-8,ztop)])
                        add(ps,f'flat-key-{i}-{sx}-{yy}',panel(wedge,1,yy,8),'key','key')
        for i,(z0,z1) in enumerate([(122,452),(470,800),(818,1182)]):
            ply(ps,f'partition-{i}',[491,68,z0],[509,330,z1])
        ply(ps,'back-low',[46,338,122],[954,344,800],'back','back')
        ply(ps,'back-high',[509,338,800],[954,344,1182],'back','back')
        door(ps,'door-low-left',50,487,126,444,42,'left')
        door(ps,'door-low-right',513,950,126,444,42,'right')
        books(ps,70,110,470,8);books(ps,545,110,818,6)
        title='Рамы и плоские клинья';detail='Ступенчатый силуэт; съёмные плоские ключи вместо шаров. Узел требует образца.'
    return dict(id=key,title=title,detail=detail,parts=ps)

def scene(ps):
    s=tm.Scene()
    for p in ps:
        if p['group']=='prop':continue
        m=p['mesh'].copy();m.visual=tm.visual.ColorVisuals(m,vertex_colors=COLORS[p['material']])
        m.apply_transform(tm.transformations.rotation_matrix(-math.pi/2,[1,0,0]));m.apply_scale(.001)
        s.add_geometry(m,geom_name=p['name'],node_name=p['name'])
    return s

def pack_rects(items,W,H):
    # Conservative rectangular blanks with fixed grain orientation. Six mm
    # spacing between blanks; ten mm trim allowance around the sheet.
    sheets=[]
    for item in sorted(items,key=lambda x:x['w']*x['h'],reverse=True):
        w,h=item['w']+6,item['h']+6;best=None
        for si,s in enumerate(sheets):
            for ri,(x,y,rw,rh) in enumerate(s['free']):
                if w<=rw and h<=rh:
                    rank=min(rw-w,rh-h)*100000+rw*rh-w*h
                    if best is None or rank<best[0]:best=(rank,si,ri,x,y)
        if best is None:
            if w>W-20 or h>H-20:raise ValueError(item)
            sheets.append(dict(free=[(10,10,W-20,H-20)],placed=[]));si=len(sheets)-1;ri=0;x=y=10
        else:_,si,ri,x,y=best
        s=sheets[si];s['placed'].append(dict(**item,x=x,y=y))
        new=[]
        for fx,fy,fw,fh in s['free']:
            if x>=fx+fw or x+w<=fx or y>=fy+fh or y+h<=fy:new.append((fx,fy,fw,fh));continue
            if x>fx:new.append((fx,fy,x-fx,fh))
            if x+w<fx+fw:new.append((x+w,fy,fx+fw-x-w,fh))
            if y>fy:new.append((fx,fy,fw,y-fy))
            if y+h<fy+fh:new.append((fx,y+h,fw,fy+fh-y-h))
        s['free']=[r for i,r in enumerate(new) if not any(i!=j and r[0]>=q[0] and r[1]>=q[1] and r[0]+r[2]<=q[0]+q[2] and r[1]+r[3]<=q[1]+q[3] for j,q in enumerate(new))]
    return sheets

def clean_blanks(b):
    items=[]
    for p in b['parts']:
        if p['material']!='wood':continue
        e=p['mesh'].extents;n=p['name']
        if n.startswith('frame'):w,h=e[2],e[1]
        elif n.startswith('shelf'):w,h=e[0],e[1]
        elif n.startswith('partition'):w,h=e[2],e[1]
        else:w,h=e[2],e[0]
        items.append(dict(name=n,w=round(float(w),2),h=round(float(h),2)))
    return items

def main():
    models=[build(k) for k in ['clean','aluminium','wedge']]
    data=[];checks=[]
    for b in models:
        ps=b['parts'];print('Export',b['id'],len(ps),flush=True)
        (OUT/(b['id']+'.glb')).write_bytes(scene(ps).export(file_type='glb'))
        parts=[]
        for p in ps:
            m=p['mesh'];q={k:v for k,v in p.items() if k not in ['mesh']}
            q.update(v=np.round(m.vertices,2).tolist(),f=m.faces.tolist())
            # Main face and exposed plywood edge have different colors.
            n=m.face_normals
            axis=0 if p['name'].startswith(('frame','partition','side-infill')) else 2 if p['name'].startswith('shelf') else 1
            q['edge']=(np.abs(n[:,axis])<.6).astype(int).tolist() if p['material']=='wood' else []
            parts.append(q)
        data.append(dict(id=b['id'],title=b['title'],detail=b['detail'],parts=parts))
        invalid=[p['name'] for p in ps if not p['mesh'].is_volume]
        # For the two cabinetry concepts, static major-panel overlaps are
        # checked. The wedge joints are intentionally schematic and excluded.
        collisions=[]
        if b['id']!='wedge':
            structural=[p for p in ps if p['group'] in ['body','profile','back','door']]
            for i,p in enumerate(structural):
                for q in structural[i+1:]:
                    vol=collision_volume(p['mesh'],q['mesh'])
                    if vol>.1:collisions.append([p['name'],q['name'],round(vol,2)])
        bounds=np.array([p['mesh'].bounds for p in ps if p['group']!='prop'])
        ext=bounds[:,1].max(axis=0)-bounds[:,0].min(axis=0)
        assert np.all(ext<=[1000.01,350.01,1200.01]),ext
        checks.append(dict(id=b['id'],parts=len(ps),extents_mm=ext.tolist(),invalid_meshes=invalid,major_panel_intersections=collisions if b['id']!='wedge' else None,
                           status='Schematic appearance model; hardware, assembly path and strength are not validated.'))
        im=render(ps,width=740,height=860,yaw=27,pitch=14);im.save(OUT/(b['id']+'.png'))
    payload=dict(models=data,colors=COLORS)
    (ROOT/'work/mobile-options-data.json').write_text(json.dumps(payload,separators=(',',':')),encoding='utf8')
    canvas=Image.new('RGB',(1800,880),'#f6f5f1');dr=ImageDraw.Draw(canvas)
    for i,b in enumerate(models):
        im=Image.open(OUT/(b['id']+'.png'));im.thumbnail((600,730));canvas.paste(im,(i*600,95))
        dr.text((i*600+25,25),f'{i+1}  '+b['title'],font=font(27),fill='#2c302c')
        dr.text((i*600+25,64),'1000 × 1200 × 350 мм, с колёсами',font=font(20),fill='#62675f')
    dr.text((25,835),'Варианты внешнего вида. Скрытая фурнитура и крепления колёс ещё не разработаны.',font=font(24),fill='#62675f')
    canvas.save(OUT/'comparison.png')
    blanks=clean_blanks(models[0]);square=pack_rects(blanks,1525,1525);large=pack_rects(blanks,2440,1220)
    for sheets,W,H,name in [(square,1525,1525,'square'),(large,2440,1220,'large')]:
        for s in sheets:
            for i,p in enumerate(s['placed']):
                assert p['x']>=10 and p['y']>=10 and p['x']+p['w']<=W-10 and p['y']+p['h']<=H-10
                for q in s['placed'][i+1:]:
                    assert p['x']+p['w']+5.99<=q['x'] or q['x']+q['w']+5.99<=p['x'] or p['y']+p['h']+5.99<=q['y'] or q['y']+q['h']+5.99<=p['y']
        report=dict(sheet_mm=[W,H],thickness_mm=18,margin_mm=10,gap_mm=6,rotation_allowed=False,sheets=[s['placed'] for s in sheets])
        (OUT/(f'cut-plan-{name}.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2))
    with (OUT/'clean-panel-blanks.csv').open('w') as f:
        cw=csv.DictWriter(f,fieldnames=['name','w','h']);cw.writeheader();cw.writerows(blanks)
    (OUT/'geometry-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
    print(json.dumps(dict(checks=checks,square_sheets=len(square),large_sheets=len(large),payload_bytes=(ROOT/'work/mobile-options-data.json').stat().st_size),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
