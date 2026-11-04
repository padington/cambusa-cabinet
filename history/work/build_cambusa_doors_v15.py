"""Framed storage doors and stepped mortises for HES3D-120, in mm."""
from pathlib import Path
import json, math, sys, itertools, hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'work/vendor'),str(ROOT/'work')]
import numpy as np
import trimesh as tm
from shapely.geometry import box, Polygon, Point
from shapely.ops import unary_union
from PIL import Image, ImageDraw, ImageFont, ImageChops
from build_mobile_options import panel, add, cube, scene
from render_assembly_v1 import render, COLORS

OUT=ROOT/'outputs/cambusa-doors-v15'; OUT.mkdir(exist_ok=True)
MANUAL='https://www.sugatsune.com/content/site-assets/Instructions/0522-7_hes3d120e.pdf'
CATALOG='https://www.sugatsune.com/content/site-assets/201B_PDF/182.pdf'
PRODUCT='https://www.sugatsune.com/3-way-adjustable-concealed-hinge-black-hes3d-120bl/'
L,R=39.5,497.; HINGE_END=L+40; MEET_START=R-38; DEEP_END=R-20
Y0,Y1,Z0,Z1=2.,87.,821.,1779.
RACK_FRONT=19.8; LIP_FRONT=78.; POST_X,POST_Y=36.,38.
HINGES=(960.,1640.); SHELVES=(934.,1234.,1534.)
PALETTE={'wood':[108,77,53,255],'back':[80,54,37,255],'frame':[45,48,48,255],
         'door-panel':[130,96,66,255],'door-stile':[101,69,44,255],
         'door-shelf':[139,101,69,255],'lip':[116,80,52,255],
         'metal':[120,123,126,255],'rubber':[35,37,38,255]}
COLORS.update(PALETTE)
wood=[]; cuts=[]; reference=[]; door_parts=[]
def insert(lst,name,m,mat,group,**meta):add(lst,name,m,mat,group,**meta)
def rod(m):return tm.Trimesh(vertices=m.vertices.copy(),faces=m.faces.copy(),process=False)
def cut(m,*ts):
    q=tm.boolean.difference([m,*ts],engine='manifold');assert q.is_volume;return q
def vol(m):
    v=np.asarray(m.triangles);return abs(float(np.einsum('ij,ij->i',v[:,0],np.cross(v[:,1],v[:,2])).sum()/6)) if len(v) else 0.
def overlap(a,b):
    if np.any(np.minimum(a.bounds[1],b.bounds[1])-np.maximum(a.bounds[0],b.bounds[0])<1e-5):return 0.
    return vol(tm.boolean.intersection([a,b],engine='manifold'))
def rr(a,b,c,d,r):return box(a+r,b+r,c-r,d-r).buffer(r,quad_segs=12)
def mirrored(m):
    m=rod(m);T=np.diag([-1.,1,1,1]);T[0,3]=1000;m.apply_transform(T);return m
def chamfered(a,b,c,d,left):
    # C1 at the opposing edges nearest the opening side, per hinge manual.
    return Polygon([(a+1,b),(c,b),(c,d),(a,d),(a,b+1)]) if left else Polygon([(a,b),(c-1,b),(c,b+1),(c,d),(a,d)])

# Retain the v08 cabinet and stand, except front edges that are rebuilt for
# the new jambs. The old drawers and any slide/door placeholders are omitted.
old=json.loads((ROOT/'work/cambusa-proportions-v08-data.json').read_text())
for p in old['parts']:
    n=p['name']
    if p['group'] not in ('body','profile','foot','back','pegboard'):continue
    if n in ('B00-bottom','B01-top','B02-left-side','B03-right-pegboard'):continue
    insert(wood,n,tm.Trimesh(vertices=p['v'],faces=p['f'],process=True),p['material'],p['group'])
for name,z in [('B00-bottom',800),('B01-top',1782)]:insert(wood,name,cube([0,0,z],[1000,500,z+18]),'wood','body')
insert(wood,'B02-left-side',cube([0,38,818],[18,500,1782]),'wood','body')
peg=[(y,z) for y in range(50,451,50) for z in range(840,1741,50)]
insert(wood,'B03-right-pegboard',panel(box(38,818,500,1782).difference(unary_union([Point(y,z).buffer(6,quad_segs=8) for y,z in peg])),0,982,18),'wood','pegboard')

# Both mounting faces of each hinge share world Y=16.5 in closed pose.
# Door pocket: 23 wide, 3 from exterior face. Frame: 25 wide, 4 from face.
# The cut-outs are 120 x 6.5 and 90 x 21, not 35 mm cups.
def mortises(kind,side):
    assert side in ('L','R')
    is_door=kind=='door'; entry=L if is_door else POST_X
    width=23 if is_door else 25; y=5 if is_door else 4
    models=[]
    for index,zc in enumerate(HINGES,1):
        for label,height,depth in [('face',120.,6.5),('body',90.,21.)]:
            depth_start=entry-.01 if is_door else entry-depth
            m=panel(rr(y,zc-height/2,y+width,zc+height/2,6),0,depth_start,depth+.01)
            if side=='R':m=mirrored(m)
            models.append(m)
            cuts.append(dict(id=f'{side}-{kind}-H{index}-{label}',part=f'{side}-'+('hinge-stile' if is_door else 'jamb'),
                edge_face_x_mm=entry if side=='L' else 1000-entry,
                from_front_edge_mm=3 if is_door else 4,from_lower_edge_mm=zc-height/2-(Z0 if is_door else 818),
                width_mm=width,height_mm=height,depth_mm=depth,radius_mm=6,source=MANUAL))
    return models
for s in ('L','R'):
    m=panel(chamfered(0,0,POST_X,POST_Y,False),2,818,964)
    if s=='R':m=mirrored(m)
    holes=mortises('jamb',s);q=cut(m,*holes)
    assert all(overlap(q,h)<.001 for h in holes)
    insert(wood,f'{s}-jamb',q,'door-stile','body')

# Stable wooden components. The far stile is one stepped section, leaving
# clearance around the middle seam. Shelves are held on three sides by grooves
# and the retaining lip; their actual retention hardware is a later release.
for s in ('L','R'):
    def hand(m):return m if s=='L' else mirrored(m)
    def dp(name,m,mat='door-stile'):
        insert(door_parts,f'{s}-{name}',hand(m),mat,'door',side=s)
    skin_groove=6.8,19.2; zskin=(835.0,1765.0)
    lx0,lx1=HINGE_END,MEET_START
    hc=[cube([lx0-4,skin_groove[0],zskin[0]],[lx0+.01,skin_groove[1],zskin[1]])]
    mc=[cube([lx1-.01,skin_groove[0],zskin[0]],[lx1+4,skin_groove[1],zskin[1]])]
    for z in SHELVES:
        hc.extend([cube([lx0-4,RACK_FRONT-.2,z-.2],[lx0+.01,Y1+.01,z+12.2]),cube([lx0-4,LIP_FRONT-.2,z+11.8],[lx0+.01,Y1+.01,z+50.2])])
        mc.extend([cube([lx1-.01,RACK_FRONT-.2,z-.2],[lx1+4,Y1+.01,z+12.2]),cube([lx1-.01,LIP_FRONT-.2,z+11.8],[lx1+4,Y1+.01,z+50.2])])
    hinge_stock=panel(chamfered(L,Y0,HINGE_END,Y1,True),2,Z0,Z1-Z0)
    # Record mirrored machining separately but cut in the common left datum.
    holes=mortises('door',s);local_holes=holes if s=='L' else [mirrored(h) for h in holes]
    h=cut(hinge_stock,*local_holes,*hc)
    assert all(overlap(h,k)<.001 for k in local_holes)
    dp('hinge-stile',h)
    grip=panel(rr(R-29,1240,R-6,1360,5),1,Y0-.01,15.01)
    stile=panel(unary_union([box(MEET_START,Y0,R,30),box(MEET_START,30,DEEP_END,Y1)]),2,Z0,Z1-Z0)
    dp('meeting-stile',cut(stile,grip,*mc))
    for label,lo,hi,g0,g1 in [('bottom-rail',Z0,839,835,839.01),('top-rail',1761,Z1,1760.99,1765)]:
        m=cut(cube([lx0,Y0,lo],[lx1,Y1,hi]),cube([lx0-.01,6.8,g0],[lx1+.01,19.2,g1]))
        dp(label,m)
    dp('front-panel',cube([lx0-3.8,7,835.2],[lx1+3.8,19,1764.8]),'door-panel')
    for i,z in enumerate(SHELVES,1):
        dp(f'shelf-{i}',cube([lx0-3.8,RACK_FRONT,z],[lx1+3.8,LIP_FRONT,z+12]),'door-shelf')
        dp(f'lip-{i}',cube([lx0-3.8,LIP_FRONT,z+12],[lx1+3.8,Y1,z+50]),'lip')

def opened(m,s):
    # Static 180-degree pose derived from the published fully-open section:
    # the mounting edge planes align; 14 - 4 - 3 = 7 between front faces.
    if s=='R':return mirrored(opened(mirrored(m),'L'))
    m=rod(m);T=np.diag([-1.,-1.,1.,1.]);T[:3,3]=[POST_X+L,Y0-7,0];m.apply_transform(T);return m
def state(is_open):
    return wood+[dict(p,mesh=opened(p['mesh'],p['side'])) for p in door_parts] if is_open else wood+door_parts

def collisions(ps):
    out=[]
    for a,b in itertools.combinations(ps,2):
        if not (a['group']=='door' or b['group']=='door'):continue
        v=overlap(a['mesh'],b['mesh'])
        if v>.02:out.append([a['name'],b['name'],round(v,3)])
    return out

zero=state(False);full=state(True);hit0=collisions(zero);hit180=collisions(full)
assert not hit0 and not hit180,(hit0,hit180)
assert all(p['mesh'].is_volume for p in zero)
closed_bounds=np.array([np.min([p['mesh'].bounds[0] for p in zero],axis=0),np.max([p['mesh'].bounds[1] for p in zero],axis=0)])
assert np.allclose(np.diff(closed_bounds,axis=0),[1000,500,1800])
open_w=max(p['mesh'].bounds[1,0] for p in full)-min(p['mesh'].bounds[0,0] for p in full)
# Guaranteed bound for the _assumed_ fixed edge test, irrespective of Y:
# every XY point stays inside its circle about the closed outer front edge.
max_rad=max(math.hypot(v[0]-L,v[1]-Y0) for p in door_parts if p['side']=='L' for v in p['mesh'].vertices)
unrelieved_rad=math.hypot(R-L,Y1-Y0)
gap_one=(1000-R)-(L+max_rad);gap_both=1000-2*(L+max_rad)
unrelieved_gap=(1000-R)-(L+unrelieved_rad)
assert gap_both>0 and unrelieved_gap<0

# For these rectangular boards and straight insertion directions the swept
# volume is exactly another box. Check the whole volume, not sampled poses.
left_door={p['name'][2:]:p['mesh'] for p in door_parts if p['side']=='L'}
assembly=[]
def prove_slide(key,axis,travel,already):
    lo,hi=left_door[key].bounds.copy()
    if travel>0:hi[axis]+=travel
    else:lo[axis]+=travel
    swept=cube(lo,hi)
    hit=[(n,round(overlap(swept,left_door[n]),3)) for n in already if overlap(swept,left_door[n])>.02]
    assert not hit,(key,hit)
    assembly.append(dict(part=key,direction='XYZ'[axis],travel_mm=travel,intersection_mm3=0.0))
prove_slide('front-panel',0,-420,['top-rail','bottom-rail','meeting-stile'])
installed=['front-panel','top-rail','bottom-rail','meeting-stile']
stile=left_door['hinge-stile'];sampled_hits=[]
for t in np.linspace(-45,0,91):
    q=rod(stile);q.apply_translation([t,0,0])
    for n in installed:
        v=overlap(q,left_door[n])
        if v>.02:sampled_hits.append([float(t),n,v])
assert not sampled_hits,sampled_hits
installed.append('hinge-stile')
for i in range(1,4):
    prove_slide(f'shelf-{i}',1,75,installed);installed.append(f'shelf-{i}')
    prove_slide(f'lip-{i}',1,15,installed);installed.append(f'lip-{i}')

mass_kg=sum(p['mesh'].volume for p in door_parts if p['side']=='L')*1e-9*720+2*.38
min_depth_gap=min(p['mesh'].bounds[0,1] for p in wood if p['name'] in ('B05-divider','B10-left-shelf','B11-left-shelf','B20-right-shelf','B21-right-shelf'))-Y1
assert math.isclose(min_depth_gap,17)
clear_opening=491-POST_X
record=dict(version='cambusa-v15',status='Geometry review only; not for machining order',
    cabinet_dimensions_mm=[1000,1800,500],door_dimensions_mm=[R-L,Z1-Z0,Y1-Y0],door_shelf_usable_mm=[MEET_START-HINGE_END,LIP_FRONT-RACK_FRONT],
    door_count=2,trays_per_door=3,drawers='deferred, excluded from new model',sources=[PRODUCT,MANUAL,CATALOG],
    hinge_candidate='Sugatsune HES3D-120BL',hinges_per_door=2,source_max_kg_per_pair=30,estimated_empty_door_kg=round(mass_kg,2),density_assumed_kg_m3=720,
    screw_axis_note='Height from hinge centre ±53 mm; Y=16.5 mm. Pilot diameters and depths not released.',
    test_results=dict(closed_door_related_volume_intersections=hit0,open_180_door_related_volume_intersections=hit180,
       open_180_pose_model='Inferred from published endpoint section, no CAD linkage',open_width_mm=open_w,closed_rear_clearance_to_internal_shelves_mm=min_depth_gap,
       fixed_edge_seam_test=dict(one_door_static_other_min_projection_gap_mm=round(gap_one,3),two_door_min_projection_gap_mm=round(gap_both,3),
            one_door_unrelieved_projection_gap_mm=round(unrelieved_gap,3),not_actual_hinge_kinematics=True),
       pegboard_holes=len(peg),pegboard_min_front_ligament_mm=50-6-38,jamb_residual_after_deep_pocket_mm=POST_X-21,leaf_residual_after_deep_pocket_mm=40-21,
       future_drawer_front_passage_mm=clear_opening,v13_drawer_face_width_mm=465,v13_drawer_body_width_mm=455,
       wood_insertion_sweeps=assembly,hinge_stile_sampled_assembly_positions=91),
    mortises=cuts,remaining=['Связка механизма и путь между положениями: CAD траектории или образец.',
        'Подтверждение удержания полок, крепления стоек, допустимой нагрузки и устойчивости.',
        'Перед сверлением назначить пилоты по комплектным шурупам и подтвердить монтажный образец.',
        'Ящики v14 отложены; новая рамка задаёт проём 455 мм.'])

for name,ps in [('closed',zero),('open',full)]:
    f=OUT/f'{name}.glb';f.write_bytes(scene(ps).export(file_type='glb'))
    loaded=tm.load(f,force='scene');assert len(loaded.geometry)==len(ps)
    record.setdefault('sha256',{})[f.name]=hashlib.sha256(f.read_bytes()).hexdigest()
    render(ps,1450,1100,yaw=20 if name=='open' else 29,pitch=12).save(OUT/f'{name}.png')
close=Image.open(OUT/'closed.png');op=Image.open(OUT/'open.png')
canvas=Image.new('RGB',(1800,1170),'#f6f5f1');d=ImageDraw.Draw(canvas)
FONT='/System/Library/Fonts/Supplemental/Arial.ttf';BOLD='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
def label(x,y,text,s=27,b=False):d.text((x,y),text,font=ImageFont.truetype(BOLD if b else FONT,s),fill='#25352b')
label(45,27,'Cambusa v15: объёмные двери с полками',40,True)
label(45,85,'Шкаф 1000 × 1800 × 500 мм · высокий каркас · 3 полки в каждой двери',26)
for im,x,w in [(close,30,550),(op,620,1135)]:
    bounds=ImageChops.difference(im,Image.new('RGB',im.size,(246,245,241))).getbbox()
    im=im.crop(bounds);im.thumbnail((w-30,870));canvas.paste(im,(x+(w-im.width)//2,148+(870-im.height)//2))
label(55,1045,'Закрыто',28,True);label(690,1045,'Открыто на 180°: проверочное положение',28,True)
label(45,1110,'Промежуточный ход петли и нагрузка требуют отдельной проверки. Ящики отложены.',23)
canvas.save(OUT/'ДВЕРИ-v15.png')

# Near-hinge view cropped from the same manufactured wooden model, showing
# the two recesses at 180 degrees. No fake hinge body is drawn.
sample=[]
for p in full:
    if p['name'] not in ('L-hinge-stile','L-jamb'):continue
    crop=cube([-500,-120,884],[100,70,1036]);m=tm.boolean.intersection([p['mesh'],crop],engine='manifold')
    assert m.is_volume;sample.append(dict(p,mesh=m))
detail=Image.new('RGB',(1260,810),'#f6f5f1');dd=ImageDraw.Draw(detail)
def dlabel(x,y,text,s=23,b=False):dd.text((x,y),text,font=ImageFont.truetype(BOLD if b else FONT,s),fill='#25352b')
dlabel(35,26,'Два кармана под одну врезную петлю',32,True)
dlabel(35,70,'Сечение по нижней петле, центр 960 мм от пола',22)
detail.paste(render(sample,690,680,yaw=66,pitch=13),(10,115))
dlabel(720,187,'Ширина карманов',26,True)
dlabel(720,232,'23 мм в двери')
dlabel(720,268,'25 мм в стойке корпуса')
dlabel(720,339,'Две ступени',26,True)
dlabel(720,385,'120 мм по высоте × 6,5 мм вглубь')
dlabel(720,421,'90 мм по высоте × 21 мм вглубь')
dlabel(720,491,'Скругления R6 по чертежу')
dlabel(720,557,'Корпус петли и рычаги',22,True)
dlabel(720,591,'на этом виде не смоделированы.',22)
detail.save(OUT/'КАРМАНЫ-ПЕТЛИ.png')
(OUT/'ПРОВЕРКА.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ('door_dimensions_mm','door_shelf_usable_mm','estimated_empty_door_kg','test_results')},ensure_ascii=False))
