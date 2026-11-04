"""Read actual Blum rail DXF geometry and place it against the v13 drawer.

Only straight and elliptical ACIS edges are drawn. Spline edges and solid
interference are deliberately not represented as verified.
"""
from pathlib import Path
from collections import Counter
import hashlib, json, math, sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'work/hardware-v14/vendor'),str(ROOT/'work/vendor')]
import ezdxf
from ezdxf.acis import api, sat
import numpy as np
import trimesh as tm
from PIL import Image, ImageDraw, ImageFont

OUT=ROOT/'outputs/tandem-review-v14';OUT.mkdir(exist_ok=True)
SRC=ROOT/'work/hardware-v14'
V13=ROOT/'outputs/cabinet-project/outputs/drawer-proof-v13'
SOURCES={
 'planning':'https://publications.blum.com/2024/catalogue/en/435/',
 'ru_manual':'https://d2.blum.com/services/BEC003/me16460573_ep_dok_bau_%24sru_%24aof_%24v4.pdf',
 'rail_listing':'https://swshardware.com/products/tandem-full-extension-runner-plus-blumot?variantId=12052',
 'rail-L.dxf':'https://swshardware.com/cdn/cad-files/cad46278782_runner_1_cad_bau_%24sall_%24acaddxf_%24v1.dxf',
 'rail-R.dxf':'https://swshardware.com/cdn/cad-files/cad47021868_runner_1_cad_bau_%24sall_%24acaddxf_%24v1.dxf',
 'lock-L.dwg':'https://www.demos-trade.eu/product-file/download/33797',
 'lock-R.dwg':'https://www.demos-trade.eu/product-file/download/33798',
}

def num(x):return np.array(list(map(float,x)))
def pv(v):return num(v.data[-1].data[-3:])
def bb(v):return np.array([v.min(axis=0),v.max(axis=0)])
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def read_rail(path):
    d=ezdxf.readfile(path);assert d.units==4
    entities=list(d.modelspace().query('3DSOLID'));assert len(entities)==3
    sections=[];circles=[];points=[];stats=Counter()
    for j,s in enumerate(entities):
        builder=sat.parse_sat(s.sat);body,=api.load_dxf(s)
        mat=body.transform.matrix
        V=np.array([tuple(v) for v in api.vertices_from_body(body)])
        points.append(np.unique(np.round(V,7),axis=0));lines=[]
        for e in builder.entities:
            if e.name=='ellipse-curve' and j==0:
                a=num(e.data[1:11]);c=np.array(mat.transform(a[:3]));n=np.array(mat.transform_direction(a[3:6]));r=np.linalg.norm(a[6:9]);
                if .25<abs(c[0])<.35 and abs(n[0])>.99 and abs(c[2])<1e-5 and abs(r-3.15)<1e-5:circles.append(c)
            if e.name!='edge':continue
            _,v0,t0,v1,t1,_,curve,*_=e.data
            p,q=pv(v0),pv(v1)
            if curve.name=='straight-curve':
                poly=np.array([p,q])
            elif curve.name=='ellipse-curve':
                v=num(curve.data[1:11]);center=v[:3];normal=v[3:6];major=v[6:9];minor=np.cross(normal,major)*v[9]
                t=np.linspace(float(t0),float(t1),max(3,math.ceil(abs(float(t1)-float(t0))/(math.pi/24))+1))
                candidates=[center+np.cos(t)[:,None]*major+sign*np.sin(t)[:,None]*minor for sign in [1,-1]]
                variants=[a for seq in candidates for a in (seq,seq[::-1])]
                def error(a):return max(np.linalg.norm(a[0]-p),np.linalg.norm(a[-1]-q))
                poly=min(variants,key=error)
                if error(poly)>.001:stats['skipped_ellipse']+=1;continue
                poly=poly.copy();poly[0]=p;poly[-1]=q
            else:stats['skipped_'+curve.name]+=1;continue
            stats[curve.name]+=1
            lines.append(np.array(list(mat.transform_vertices(poly))))
        sections.append(lines)
    return dict(sections=sections,points=points,mount_y=sorted({round(float(c[1]),4) for c in circles}),stats=dict(stats))

rail={hand:read_rail(SRC/f'rail-{hand}.dxf') for hand in 'LR'}
for hand,r in rail.items():
    assert set([-18.,0.,32.,224.])<=set(r['mount_y']),r['mount_y']
    assert abs(np.ptp(r['points'][0][:,1])-350)<1e-5
    assert r['stats'].get('skipped_ellipse',0)==0,r['stats']
# The independently sourced left/right CAD files are mirrors at the vertices.
for l,r in zip(rail['L']['points'],rail['R']['points']):
    assert set(map(tuple,np.round(l*[-1,1,1],5)))==set(map(tuple,np.round(r,5)))

concept={p['name']:p for p in json.loads((ROOT/'work/cambusa-proportions-v08-data.json').read_text())['parts']}
def cbb(k):return bb(np.array(concept[k]['v']))
left_face_x=cbb('B05-divider')[1,0];right_face_x=cbb('B03-right-pegboard')[0,0]
case_width=right_face_x-left_face_x;back_y=cbb('B04-back')[0,1]
left_x,box_y,box_z=cbb('D0-left')[0]
front_y=cbb('D0-face')[0,1];face_thick=box_y-front_y
floor_z=box_z+13
assert (case_width,back_y,front_y,box_y,box_z,face_thick)==(473,488,122,134,847,12)
# Depth datum verified from the series 560H planning drawing. Its second
# inset mounting position is X+37 from the face datum, at rail CAD Y=0.
mount_y=front_y+face_thick+37
# Trial vertical placement: contact with the long upper planar face of the
# moving body. This is an explicitly stated alignment hypothesis, not a
# replacement for a coordinated manufacturer assembly or a physical fit test.
support_z=-9.775
mount_z=floor_z-support_z
T={'L':np.array([left_face_x,mount_y,mount_z]),'R':np.array([right_face_x,mount_y,mount_z])}
cad_dimensions={h:[bb(v).round(6).tolist() for v in r['points']] for h,r in rail.items()}

original=tm.load(V13/'assembled.glb',force='scene')
wood={}
for node in original.graph.nodes_geometry:
    t,name=original.graph.get(node);m=original.geometry[name];v=tm.transform_points(m.vertices,t)
    v=v[:,[0,2,1]]*np.array([1000,-1000,1000])+np.array([left_x,box_y,box_z])
    wood[node]=tm.Trimesh(vertices=v,faces=m.faces,process=False)
assert set(wood)=={'left','right','front','rear','bottom','face'}

def strictly_inside(points,m,min_depth=.05):
    """Point-in-solid with parity ray, ignoring the contact surface band."""
    lo,hi=m.bounds;pts=points[np.all((points>lo+min_depth)&(points<hi-min_depth),axis=1)]
    if not len(pts):return []
    near=tm.proximity.closest_point_naive(m,pts)[1]
    pts=pts[near>min_depth];dists=near[near>min_depth]
    t=m.triangles; a=t[:,0];e=t[:,1]-a;f=t[:,2]-a
    direction=np.array([.412,.273,.869]);direction/=np.linalg.norm(direction)
    h=np.cross(direction,f);det=np.einsum('ij,ij->i',e,h);valid=np.abs(det)>1e-9
    a,e,f,h,inv=a[valid],e[valid],f[valid],h[valid],1/det[valid]
    out=[]
    for p,dist in zip(pts,dists):
        s=p-a;u=np.einsum('ij,ij->i',s,h)*inv;q=np.cross(s,e);v=q@direction*inv
        t=np.einsum('ij,ij->i',f,q)*inv
        hits=(u>=-1e-9)&(v>=-1e-9)&(u+v<=1+1e-9)&(t>1e-9)
        if len(np.unique(np.round(t[hits],6)))%2:out.append(dict(point=np.round(p,4).tolist(),distance_to_wood_surface_mm=round(float(dist),4)))
    return out

findings=[]
for h,r in rail.items():
    for j,pts in enumerate(r['points']):
        for name,m in wood.items():
            inside=strictly_inside(pts+T[h],m)
            if inside:findings.append(dict(hand=h,solid=j,wood=name,vertices_inside=len(inside),witness=max(inside,key=lambda x:x['distance_to_wood_surface_mm'])))

peg=[(y,z) for y in range(50,451,50) for z in range(840,1741,50)]
assert len(peg)==171
peg_radius=6; screw_radius=2
options=[]
for shift in [0,-4]:
    y=front_y+shift;avail=back_y-y;need=350+face_thick+3;rows=[]
    for index in [0,1]:
        delta_z=cbb(f'D{index}-left')[0,2]-box_z
        for local_y in [-18,0,32,224]:
            py=mount_y+shift+local_y;pz=mount_z+delta_z
            nearest=min(peg,key=lambda v:math.hypot(py-v[0],pz-v[1]));d=math.hypot(py-nearest[0],pz-nearest[1])
            rows.append(dict(drawer=index+1,catalog_offset_from_face_mm=round(float(py-y),3),yz_mm=[float(py),float(pz)],
                from_W04_edges_mm=[float(py-cbb('B03-right-pegboard')[0,1]),float(pz-cbb('B03-right-pegboard')[0,2])],
                from_W06_edges_mm=[float(py-cbb('B05-divider')[0,1]),float(pz-cbb('B05-divider')[0,2])],
                nearest_peg_yz_mm=nearest,clearance_to_peg_at_screw_radius_mm=round(d-peg_radius-screw_radius,3)))
    options.append(dict(shift_mm=shift,face_y_mm=float(y),available_mm=float(avail),required_min_mm=float(need),reserve_mm=float(avail-need),
        clear_to_empty_closed_v08_trays_mm=float(y-83),mounting_candidates_not_drill_map=rows))

report=dict(version='tandem-review-v14',status='TRIAL_FIT_ONLY',rail_sku='560H3500B',lock_sku='T51.1700.04 L/R',
    input_sha256={p.name:digest(p) for p in [SRC/'rail-L.dxf',SRC/'rail-R.dxf',SRC/'lock-L.dwg',SRC/'lock-R.dwg',V13/'assembled.glb']},sources=SOURCES,
    rail_acis_body_bounds_mm=cad_dimensions,edge_extraction={k:r['stats'] for k,r in rail.items()},mounting_arc_centres_y={k:r['mount_y'] for k,r in rail.items()},
    placement_basis=dict(x_left=float(left_face_x),x_right=float(right_face_x),cad_mount_row_y0_world_y=float(mount_y),cad_top_face_z=support_z,trial_mount_z=float(mount_z),trial_wood_floor_underface_z=float(floor_z)),
    drawer_width=dict(case_mm=float(case_width),inner_mm=431,nominal_accepted_range_mm=[429.5,431],example_finished_target_mm=430.25),
    v08_geometry_options=options,cad_vertices_inside_v13_wood=findings,lock_dwg_imported=False,
    lock_downloads_identical=digest(SRC/'lock-L.dwg')==digest(SRC/'lock-R.dwg'),hardware_solid_collision_proved=False,
    hold=['Не сверлить по этому отчёту.','Проверить сопоставление опорной поверхности и хвостовика со сборочным CAD Blum либо реальным комплектом.','Импортировать замки, получить углы и глубины пилотов.','Уточнить размеры после отделки и зазор с наполненными дверьми.'])
(OUT/'ПРОВЕРКА.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

# GLB shows imported wire geometry, not approximated solid metal. Use the
# same view to inspect original drawer geometry and numerical witnesses.
sc=tm.Scene()
origin=np.array([left_face_x,front_y,box_z-35]);
def gl_points(v):return (v-origin)[:,[0,2,1]]*np.array([.001,.001,-.001])
for name,m in wood.items():
    v=gl_points(m.vertices)
    sc.add_geometry(tm.Trimesh(vertices=v,faces=m.faces,vertex_colors=np.tile([176,135,89,255],(len(v),1)),process=False),node_name='wood-'+name,geom_name='wood-'+name)
for h,r in rail.items():
    for j,lines in enumerate(r['sections']):
        vertices=[];entities=[]
        for line in lines:
            entities.append(tm.path.entities.Line(np.arange(len(vertices),len(vertices)+len(line))))
            vertices.extend(gl_points(line+T[h]))
        path=tm.path.Path3D(entities=entities,vertices=vertices,colors=np.tile([36,117,177,255],(len(entities),1)),process=False)
        name=f'CAD-560H3500B-{h}-body{j}'
        sc.add_geometry(path,node_name=name,geom_name=name)
for i,f in enumerate(findings):
    p=gl_points(np.array([f['witness']['point']]))[0];m=tm.creation.icosphere(subdivisions=1,radius=.002);m.apply_translation(p)
    m.visual.vertex_colors=np.tile([210,62,40,255],(len(m.vertices),1));sc.add_geometry(m,node_name=f'wood-conflict-{i}')
glb=OUT/'ЯЩИК-И-НАПРАВЛЯЮЩИЕ.glb';glb.write_bytes(sc.export(file_type='glb'))
loaded=tm.load(glb,force='scene')
assert sum(isinstance(m,tm.path.Path3D) for m in loaded.geometry.values())==6
assert len(loaded.geometry)==12+len(findings)
report['review_glb_sha256']=digest(glb)
(OUT/'ПРОВЕРКА.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

font='/System/Library/Fonts/Supplemental/Arial.ttf';bold='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
im=Image.new('RGB',(1500,915),'#f6f6f0');d=ImageDraw.Draw(im)
def txt(x,y,s,size=24,b=False,color='#26372e'):d.text((x,y),s,font=ImageFont.truetype(bold if b else font,size),fill=color)
txt(50,36,'TANDEM 560H3500B: ящик и две направляющие',34,True)
txt(50,86,'Синие линии взяты из CAD Blum · дерево из v13 · проверочное положение',22)
yaw,pitch=math.radians(38),math.radians(29)
R=np.array([math.cos(yaw),math.sin(yaw),0]);U=np.array([-math.sin(yaw)*math.sin(pitch),math.cos(yaw)*math.sin(pitch),math.cos(pitch)])
def screen(p):
    v=np.array(p)-[745,305,903];return tuple(np.array([v@R,-v@U])*1.32+[735,361])
for name,m in wood.items():
    lo,hi=m.bounds
    outline=tm.creation.box(hi-lo);outline.apply_translation((hi+lo)/2)
    for a,b in outline.edges_unique:
        if np.count_nonzero(np.abs(outline.vertices[a]-outline.vertices[b])>1e-6)==1:
            d.line([screen(outline.vertices[a]),screen(outline.vertices[b])],fill='#9a8163',width=2)
for h,r in rail.items():
    for j,lines in enumerate(r['sections']):
        for line in lines:d.line([screen(p) for p in line+T[h]],fill=['#184a79','#8ba7bf','#427fb2'][j],width=2)
for f in findings:
    px,py=screen(f['witness']['point']);d.ellipse((px-8,py-8,px+8,py+8),fill='#bf4e35',outline='white',width=2)
txt(50,670,'Глубина от передней поверхности фасада до задника',24,True)
txt(50,718,'Сейчас: 366 мм доступно − 365 мм минимум = 1 мм запаса',26)
txt(50,767,'Сдвиг ящиков вперёд на 4 мм: 5 мм запаса в компоновке v08',26)
if findings:txt(50,833,'Красные точки: границы CAD попали в дерево при проверочной установке.',22,False,'#9d3b2a')
else:txt(50,833,'Проверены точки CAD; проверка сплошных тел и замков ещё впереди.',22)
im.save(OUT/'ПРОВЕРКА-ГЛУБИНЫ.png')
print(json.dumps(dict(rail_edges=report['edge_extraction'],inside=findings,depth=[(r['reserve_mm'],r['clear_to_empty_closed_v08_trays_mm']) for r in options],output=OUT.name),ensure_ascii=False))
