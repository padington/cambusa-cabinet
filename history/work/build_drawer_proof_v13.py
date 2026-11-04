from pathlib import Path
import sys,json,math,hashlib,collections,itertools
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work/vendor'));sys.path.insert(0,str(ROOT/'work'))
import numpy as np
import trimesh as tm
from shapely.geometry import box
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3,landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor

OUT=ROOT/'outputs/drawer-proof-v13';OUT.mkdir(exist_ok=True)
SOURCE=ROOT/'outputs/cabinet-project/outputs/joinery-review-v12/operations.json'
data=json.loads(SOURCE.read_text());parts={p['id']:p for p in data['parts']}
for p in parts.values():
    for a in p['operations']:
        a['corner_radius_mm']=3 if a['kind']=='pocket' and (p['id'] in ['left','right'] or a['joint']=='finger-pull') else 0
data['operations']=[a for p in parts.values() for a in p['operations']]
assert len({a['id'] for a in data['operations']})==len(data['operations'])
EPS=.001

def basis(p):return np.column_stack([p['u'],p['v'],p['n']])
def world(p,q):return np.array(p['origin'])+basis(p)@np.array(q)
def trans(p):
    T=np.eye(4);T[:3,:3]=basis(p);T[:3,3]=p['origin'];return T
def stock(p):
    m=tm.creation.box([p['width'],p['height'],p['thickness']]);m.apply_translation([p['width']/2,p['height']/2,p['thickness']/2]);m.apply_transform(trans(p));return m
def cyl(start,direction,r,length):
    direction=np.array(direction,dtype=float);T=tm.geometry.align_vectors([0,0,1],direction)
    T[:3,3]=np.array(start)+direction*length/2
    return tm.creation.cylinder(radius=r,height=length,sections=64,transform=T)
def frustum(start,direction,r0,r1,length):
    n=64;angles=np.arange(n)*2*np.pi/n
    vertices=np.vstack([np.c_[r0*np.cos(angles),r0*np.sin(angles),np.zeros(n)],np.c_[r1*np.cos(angles),r1*np.sin(angles),np.full(n,length)],[[0,0,0],[0,0,length]]])
    faces=[]
    for i in range(n):
        j=(i+1)%n;faces.extend([[i,j,n+j],[i,n+j,n+i],[2*n,j,i],[2*n+1,n+i,n+j]])
    m=tm.Trimesh(vertices=vertices,faces=faces,process=True)
    if m.volume<0:m.invert()
    T=tm.geometry.align_vectors([0,0,1],direction);T[:3,3]=start;m.apply_transform(T);return m
def geometry(p,a):
    u,v=a['u'],a['v'];depth=a['depth'];t=p['thickness'];face=a['face']
    if face in ['A','B']:
        start=[u,v,0 if face=='A' else t];direction=[0,0,1 if face=='A' else -1]
    else:start=[u,v,t/2];direction=[1 if face=='U0' else -1,0,0]
    if a['kind']=='countersink':
        # A real 90-degree frustum, not the cylindrical envelope used in v12.
        return frustum(world(p,start),basis(p)@np.array(direction),a['diameter']/2,2,depth)
    if a['diameter'] is not None:
        return cyl(world(p,start),basis(p)@np.array(direction),a['diameter']/2,depth)
    sx,sy=a['size'];radius=3 if a['joint']=='bottom-groove' and p['id'] in ['left','right'] else 0
    poly=box(u,v,u+sx,v+sy)
    if radius:poly=box(u+radius,v+radius,u+sx-radius,v+sy-radius).buffer(radius,quad_segs=16)
    if a['joint']=='finger-pull':poly=box(u+3,v+3,u+sx-3,v+sy+3).buffer(3,quad_segs=16)
    m=tm.creation.extrude_polygon(poly,depth,engine='earcut')
    m.apply_translation([0,0,0 if face=='A' else t-depth]);m.apply_transform(trans(p));return m
def volume(m):return abs(float(m.volume)) if len(m.faces) else 0
def intersection(a,b):return tm.boolean.intersection([a,b],engine='manifold')
def clone(m):return tm.Trimesh(vertices=m.vertices.copy(),faces=m.faces.copy(),process=False)

meshes={};cutters={};feature_checks=[];overlaps=[]
for key,p in parts.items():
    blank=stock(p);cs=[geometry(p,a) for a in p['operations']]
    for a,m in zip(p['operations'],cs):cutters[a['id']]=m
    result=tm.boolean.difference([blank,*cs],engine='manifold') if cs else blank
    assert result.is_watertight and result.volume>0,key
    meshes[key]=result
    for a,cut in zip(p['operations'],cs):
        taken=volume(intersection(blank,cut));residue=volume(intersection(result,cut))
        assert taken>.01,(a['id'],'does not cut stock');assert residue<.01,(a['id'],'material remains in cut',residue)
        if a['face'] in ['A','B']:
            minimum_wall=0 if a['depth']>=p['thickness'] else p['thickness']-a['depth']
        else:minimum_wall=p['thickness']/2-a['diameter']/2
        feature_checks.append(dict(id=a['id'],part=key,stock_cut_mm3=round(taken,3),wood_remaining_in_feature_mm3=round(residue,6),nominal_back_or_radial_wall_mm=minimum_wall))
    for a,b in itertools.combinations(p['operations'],2):
        amount=volume(intersection(cutters[a['id']],cutters[b['id']]))
        if amount>.01:
            intended=a['joint']==b['joint'] and bool(a['joint'])
            overlaps.append(dict(a=a['id'],b=b['id'],volume_mm3=round(amount,3),expected=intended))
            assert intended,('unexpected intersecting features',a['id'],b['id'])

axes=[]
for side in ['left','right']:
    for end in ['front','rear']:
        for suffix in ['55','90','dowel']:
            joint=f'{side}-{end}-{suffix}'
            a=next(a for a in parts[side]['operations'] if a['joint']==joint)
            b=next(a for a in parts[end]['operations'] if a['joint']==joint and a['kind']=='edge_bore')
            pa=world(parts[side],[a['u'],a['v'],12 if side=='left' else 0]);pb=world(parts[end],[b['u'],b['v'],6])
            mismatch=float(np.linalg.norm(pa-pb));assert mismatch<1e-6,joint
            axes.append(dict(joint=joint,parts=[side,end],position_mm=pa.tolist(),misalignment_mm=mismatch))
face_axes=[]
for a in parts['front']['operations']:
    if a['kind']=='bore' and a['reason'].startswith('Сквозной'):
        b=next(b for b in parts['face']['operations'] if b['joint']==a['joint'])
        pa=world(parts['front'],[a['u'],a['v'],0]);pb=world(parts['face'],[b['u'],b['v'],12])
        mismatch=float(np.linalg.norm(pa-pb));assert mismatch<1e-6
        face_axes.append(dict(joint=a['joint'],misalignment_mm=mismatch))
wood_collisions=[]
for a,b in itertools.combinations(meshes,2):
    amount=volume(intersection(meshes[a],meshes[b]))
    if amount>.01:wood_collisions.append([a,b,amount])
assert not wood_collisions,wood_collisions

# Assembly sequence is sampled for the wood geometry. It deliberately does not
# claim that absent cams, studs, locks or runners have passed an assembly test.
sequence=[('front',[500,0,0]),('rear',[500,0,0]),('bottom',[500,0,0]),('right',[500,0,0]),('face',[0,-100,0])]
fixed=['left'];assembly=[]
for key,shift in sequence:
    collisions=[]
    for t in np.linspace(1,0,101):
        m=clone(meshes[key]);m.apply_translation(np.array(shift)*t)
        for other in fixed:
            if np.any(m.bounds[1]<meshes[other].bounds[0]-EPS) or np.any(meshes[other].bounds[1]<m.bounds[0]-EPS):continue
            amount=volume(intersection(m,meshes[other]))
            if amount>.01:collisions.append(dict(t=float(t),with_part=other,mm3=amount))
    assert not collisions,(key,collisions[:3])
    assembly.append(dict(step=len(assembly)+1,moving_part=key,initial_offset_mm=shift,samples=101,wood_collisions=collisions));fixed.append(key)

gaps=dict(bottom_side_capture_mm=2.8,bottom_front_capture_mm=2.8,bottom_vertical_gap_below_mm=.1,bottom_vertical_gap_above_mm=.1,bottom_rear_gap_mm=.2)
checks=dict(version='drawer-proof-v13',status='Контрольная 3D-геометрия одного ящика; не выпуск в изготовление',
    input_source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),features=feature_checks,feature_overlaps=overlaps,
    mating_axes=axes,face_screw_axes=face_axes,wood_part_collisions=wood_collisions,assembly_wood_only=assembly,nominal_gaps=gaps,
    true_countersink_cones=True,true_side_groove_radius_mm=3,
    not_verified=['Геометрия и установка реальных эксцентриков и штоков','Замки, направляющие и их незаданные пилоты','Допуски фактической фанеры и отделки','Прочность, нагрузка и устойчивость','Присадка остальных деталей шкафа и новых дверей'])
(OUT/'ПРОВЕРКИ-3D.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
data['version']='drawer-proof-v13';data['checks']=checks
(OUT/'МОДЕЛЬ-И-ОПЕРАЦИИ.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

shifts={'left':[-45,0,0],'right':[45,0,0],'front':[0,-55,0],'rear':[0,55,0],'bottom':[0,0,-50],'face':[0,-110,0]}
T=np.array([[.001,0,0,0],[0,0,.001,0],[0,-.001,0,0],[0,0,0,1]])
for exploded in [False,True]:
    scene=tm.Scene()
    for k,m in meshes.items():
        q=clone(m)
        if exploded:q.apply_translation(shifts[k])
        q.apply_transform(T);q.visual.vertex_colors=np.tile([171,137,96,255],(len(q.vertices),1));scene.add_geometry(q,node_name=k)
    (OUT/('exploded.glb' if exploded else 'assembled.glb')).write_bytes(scene.export(file_type='glb'))
checks['geometry_sha256']={name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ['assembled.glb','exploded.glb']}
(OUT/'ПРОВЕРКИ-3D.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
(OUT/'МОДЕЛЬ-И-ОПЕРАЦИИ.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

# Engineering previews rasterize the actual cut meshes, including true cones
# and R3 groove ends. No decorative replacement shapes are used.
from render_assembly_v1 import render,COLORS
COLORS['proof']=[191,158,116,255]
for exploded in [False,True]:
    ps=[]
    for k,m in meshes.items():
        q=clone(m)
        if exploded:q.apply_translation(shifts[k])
        ps.append(dict(name=k,mesh=q,material='proof'))
    render(ps,1400,850,yaw=28,pitch=38).save(OUT/('exploded.png' if exploded else 'assembled.png'))

payload=[]
for k,m in meshes.items():
    p=parts[k];payload.append(dict(id=k,name=p['name'],codes=p['codes'],origin=p['origin'],u=p['u'],v=p['v'],n=p['n'],width=p['width'],height=p['height'],thickness=p['thickness'],shift=shifts[k],vertices=np.round(m.triangles.reshape(-1,3),5).tolist(),normals=np.round(np.repeat(m.face_normals,3,axis=0),5).tolist()))
features=[]
for a in data['operations']:
    m=cutters[a['id']];p=parts[a['part']];u,v=a['u'],a['v']
    anchor='центр' if a['diameter'] else 'нижний левый угол паза'
    features.append(dict(**a,anchor=anchor,offsets_mm=dict(from_U0=u,from_U1=p['width']-u,from_V0=v,from_V1=p['height']-v),vertices=np.round(m.triangles.reshape(-1,3),5).tolist(),normals=np.round(np.repeat(m.face_normals,3,axis=0),5).tolist()))
viewer_data=dict(parts=payload,features=features,checks=checks)
(ROOT/'work/drawer-v13-data.json').write_text(json.dumps(viewer_data,ensure_ascii=False,separators=(',',':')))

pdfmetrics.registerFont(TTFont('Arial','/System/Library/Fonts/Supplemental/Arial.ttf'))
pdfmetrics.registerFont(TTFont('ArialB','/System/Library/Fonts/Supplemental/Arial Bold.ttf'))
c=canvas.Canvas(str(OUT/'Размерные-привязки-v13.pdf'),pagesize=landscape(A3));W,H=landscape(A3)
c.setTitle('Контрольный ящик v13: размерные привязки из 3D-операций')
def txt(x,y,s,size=11,bold=False,color='#26382d'):
    c.setFont('ArialB' if bold else 'Arial',size);c.setFillColor(HexColor(color));c.drawString(x,y,str(s))
def title(s,sub):
    c.setFillColor(HexColor('#fafbf8'));c.rect(0,0,W,H,fill=1,stroke=0);txt(35,H-38,s,20,True);txt(35,H-62,sub,11)
    c.setStrokeColor(HexColor('#bbc9bd'));c.line(35,H-78,W-35,H-78)
    txt(35,22,'v13 | 04.11.2026 | мм | GLB SHA256 '+checks['geometry_sha256']['assembled.glb'][:12]+' | НЕ ДЛЯ ИЗГОТОВЛЕНИЯ',9)
    txt(W-85,22,f'Лист {c.getPageNumber()}',9)
def dim(x1,y1,x2,y2,label,size=10):
    c.setStrokeColor(HexColor('#445e4a'));c.setFillColor(HexColor('#26382d'));c.setLineWidth(.6);c.line(x1,y1,x2,y2)
    if abs(y2-y1)<.01:
        for x in [x1,x2]:c.line(x,y1-3,x,y1+3)
        c.setFont('Arial',size);c.drawCentredString((x1+x2)/2,y1+4,str(label))
    else:
        for y in [y1,y2]:c.line(x1-3,y,x1+3,y)
        c.saveState();c.translate(x1-4,(y1+y2)/2);c.rotate(90);c.setFont('Arial',size);c.drawCentredString(0,0,str(label));c.restoreState()
def line(x1,y1,x2,y2):
    c.setStrokeColor(HexColor('#9baca0'));c.setLineWidth(.4);c.line(x1,y1,x2,y2)

title('3D-модель задаёт обработку и размерные привязки','Это исправление способа проверки v12; общая модель шкафа v08 не заменяется.')
c.drawImage(str(OUT/'exploded.png'),35,H-440,width=650,height=330,preserveAspectRatio=True,anchor='c')
notes=['6 деревянных деталей с вычтенной обработкой.',f"{len(feature_checks)} операций: проверены вырезы в материале.",f'{len(axes)} пар осей стяжек и шкантов совпадают.',f'{len(face_axes)} оси шурупов фасада совпадают.',
       'Пазы боковин имеют реальные концы R3.','Зенковки построены конусами 90 градусов.','Проверены 101 положение на каждом из 5 шагов.','Проверка сборки относится только к дереву.',
       'Реальная фурнитура пока не смоделирована.','Пилоты замков и направляющих ещё не заданы.']
for i,s in enumerate(notes):txt(730,H-128-i*28,s,12,bold=i in [0,7])
txt(42,325,'Правила чтения',14,True)
for i,s in enumerate(['Операции имеют те же номера, что в просмотре 3D и JSON. Каждый лист показывает отдельную группу обработки.',
    'Отступы показаны размерными линиями от баз U0 и V0. У отверстия привязан центр; у паза - нижний левый угол.',
    'U0/V0 - физические кромки с общей системой координат детали. На обратном виде U0 может находиться справа.',
    'Виды выполнены с учётом стороны обработки; положение базы подписано. Глубина всегда отсчитывается от указанной пласти.',
    'Размеры номинальные. Допуски и фактическая толщина фанеры должны быть назначены до технологического выпуска.',
    'Врезные петли новых дверей пользователем выбраны как направление; точный артикул и их присадка пока отсутствуют.']):txt(42,294-i*27,s,12)
c.showPage()

groups=[]
for key,p in parts.items():
    grouped=collections.defaultdict(list)
    for a in p['operations']:
        kind='screw-fix' if p['id']=='front' and a['joint'] and a['joint'].startswith('face-') else a['kind']
        face='U0/U1' if a['face'].startswith('U') else a['face']
        discriminator='' if kind=='screw-fix' else str((a['diameter'],a['depth']))
        grouped[(face,kind,discriminator)].append(a)
    if not grouped:groups.append((p,('A','outline',''),[]))
    for g,aa in grouped.items():groups.append((p,g,aa))

for p,g,aa in groups:
    face,kind,_=g;primary='B' if p['id'] in ['left','front','face'] else 'A'
    view=primary if face=='U0/U1' else face
    outward=np.array(p['n'])*(1 if view=='B' else -1)
    flip=np.dot(np.cross(p['u'],p['v']),outward)<0
    ids=', '.join(a['id'] for a in aa)
    title(', '.join(p['codes'])+' | '+p['name'],f'{p["width"]:g} × {p["height"]:g} × {p["thickness"]:g} | обработка: {face} | '+('контур без отверстий' if not aa else ids))
    scale=min(1.65,740/p['width'],215/p['height']);dw=p['width']*scale;dh=p['height']*scale
    x=230;y=H-175-dh
    X=lambda u:x+(p['width']-u if flip else u)*scale
    Y=lambda v:y+v*scale
    txt(x,y+dh+25,f'Вид на пласть {view}; U0 '+('справа' if flip else 'слева')+', V0 снизу',12,True)
    c.setFillColor(HexColor('#eadcc7'));c.setStrokeColor(HexColor('#536b58'));c.rect(x,y,dw,dh,fill=1)
    for a in aa:
        c.setStrokeColor(HexColor('#245f86'));c.setLineWidth(1.1)
        xx,yy=X(a['u']),Y(a['v'])
        if a['size']:
            sx,sy=a['size'];lo=min(X(a['u']),X(a['u']+sx));r=3 if p['id'] in ['left','right'] else 0
            if a['joint']=='finger-pull':
                rr=3*scale;xx1=lo+sx*scale;path=c.beginPath();path.moveTo(lo,yy+sy*scale);path.lineTo(lo,yy+rr)
                path.curveTo(lo,yy+rr*.448,lo+rr*.448,yy,lo+rr,yy);path.lineTo(xx1-rr,yy)
                path.curveTo(xx1-rr*.448,yy,xx1,yy+rr*.448,xx1,yy+rr);path.lineTo(xx1,yy+sy*scale);c.drawPath(path,fill=0,stroke=1)
            else:c.roundRect(lo,yy,sx*scale,sy*scale,r*scale,fill=0,stroke=1)
        elif a['face'].startswith('U'):
            end=X(a['u']+(a['depth'] if a['face']=='U0' else -a['depth']))
            c.setDash(3,2);c.rect(min(xx,end),yy-a['diameter']*scale/2,abs(end-xx),a['diameter']*scale,fill=0,stroke=1);c.setDash()
        else:c.circle(xx,yy,a['diameter']/2*scale,fill=0,stroke=1)
        if a['kind']!='countersink':txt(xx+5,yy+10,a['id'].split('-')[-1],9,color='#245f86')
    txt(X(0)+(-20 if flip else 2),y+5,'U0',9,True);txt(x-24,y+2,'V0',9,True)
    # Baseline dimensions, rather than a coordinate-only table.
    us=sorted(set(a['u'] for a in aa if 0<a['u']<p['width']))
    if aa and aa[0]['size']:
        us=sorted(set([aa[0]['u'],aa[0]['u']+aa[0]['size'][0]])-{0,p['width']})
    for i,u in enumerate(us):
        dy=y-28-23*i;line(X(0),y,X(0),dy-4);line(X(u),y,X(u),dy-4);dim(X(0),dy,X(u),dy,f'{u:g}')
    full_y=y-28-23*len(us);dim(x,full_y,x+dw,full_y,f'{p["width"]:g}')
    vs=sorted(set(a['v'] for a in aa if a['v']>0))
    if aa and aa[0]['size']:vs=sorted(set([aa[0]['v'],aa[0]['v']+aa[0]['size'][1]]))
    for i,v in enumerate(vs):
        dx=x-32-24*i;line(x,y,dx-4,y);line(x,Y(v),dx-4,Y(v));dim(dx,y,dx,Y(v),f'{v:g}')
    dim(x+dw+35,y,x+dw+35,y+dh,f'{p["height"]:g}')
    details_y=min(275,full_y-45)
    if aa:
        a=aa[0];txt(42,details_y,'Сечение / глубина',13,True)
        sx=70;sy=details_y-86;ss=4
        c.setFillColor(HexColor('#eadcc7'));c.setStrokeColor(HexColor('#536b58'));c.rect(sx,sy,p['thickness']*ss,62,fill=1)
        if face=='U0/U1':
            c.setFillColor(HexColor('#fafbf8'));c.rect(sx-2,sy-2,p['thickness']*ss+4,66,fill=1,stroke=0)
            c.setFillColor(HexColor('#eadcc7'));c.setStrokeColor(HexColor('#536b58'));c.rect(sx,sy,30*ss,p['thickness']*ss,fill=1)
            c.setFillColor(HexColor('#bfd6e3'));c.setStrokeColor(HexColor('#245f86'));c.rect(sx,sy+(p['thickness']/2-a['diameter']/2)*ss,a['depth']*ss,a['diameter']*ss,fill=1)
            dim(sx-16,sy,sx-16,sy+p['thickness']/2*ss,f'ось {p["thickness"]/2:g}')
            dim(sx,sy-17,sx+a['depth']*ss,sy-17,f'гл. {a["depth"]:g}')
            dim(sx+30*ss+15,sy,sx+30*ss+15,sy+p['thickness']*ss,f'{p["thickness"]:g}')
            txt(sx+180,sy+32,f'Торцевое отверстие Ø{a["diameter"]:g}, глубина {a["depth"]:g}',12)
            txt(sx+180,sy+8,'Сечение от торца внутрь детали; ось посередине толщины.',11)
        else:
            # Face-normal section; A is at w0 and B is at w=t.
            start=sx if face=='A' else sx+p['thickness']*ss
            direction=1 if face=='A' else -1
            dep=max(q['depth'] for q in aa);r=a['diameter']/2 if a['diameter'] else a['size'][1]/2
            c.setFillColor(HexColor('#bfd6e3'));c.setStrokeColor(HexColor('#245f86'))
            hole_h=(4 if kind=='screw-fix' else a['diameter'] if a['diameter'] else a['size'][1])*ss
            c.rect(min(start,start+direction*dep*ss),sy+31-hole_h/2,dep*ss,hole_h,fill=1)
            if kind=='screw-fix':
                c.setFillColor(HexColor('#245f86'));path=c.beginPath();path.moveTo(start,sy+31-3.5*ss);path.lineTo(start+direction*1.5*ss,sy+31-2*ss);path.lineTo(start+direction*1.5*ss,sy+31+2*ss);path.lineTo(start,sy+31+3.5*ss);path.close();c.drawPath(path,fill=1,stroke=0)
            dim(start,sy-17,start+direction*dep*ss,sy-17,f'гл. {dep:g}');dim(sx,sy-48,sx+p['thickness']*ss,sy-48,f'толщ. {p["thickness"]:g}')
            label=('Сквозное Ø4 и зенковка Ø7 × 1,5; угол 90°' if kind=='screw-fix' else f'Ø{a["diameter"]:g}' if a['diameter'] else f'Паз {a["size"][0]:g} × {a["size"][1]:g}')
            txt(sx+120,sy+35,label,12);txt(sx+120,sy+12,f'Глубина от пласти {face}; A = w0, B = w{p["thickness"]:g}.',11)
        reasons=list(dict.fromkeys(a['reason'] for a in aa))
        for i,s in enumerate(reasons):txt(42,60+18*i,s,10)
    else:txt(42,120,'Дно без сверлений; окончательный размер задаёт посадку в трёх пазах.',12)
    c.showPage()
c.save()
print(json.dumps(dict(parts=6,features=len(feature_checks),axes=len(axes),face_axes=len(face_axes),assembly_steps=len(assembly),pdf_pages=1+len(groups),output=str(OUT)),ensure_ascii=False))
