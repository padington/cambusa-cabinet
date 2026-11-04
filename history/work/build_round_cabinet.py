from pathlib import Path
import sys, json, math, zipfile
sys.path.insert(0, str(Path(__file__).parent / 'vendor'))
import numpy as np
import trimesh as tm
from shapely.geometry import Point, box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs' / 'round-cabinet'
OUT.mkdir(parents=True, exist_ok=True)
R, TH, CAP, PLY, CLEAR = 28., 28., 4., 15., .3

def cuboid(size, center):
    m = tm.creation.box(size)
    m.apply_translation(center)
    return m

def extrude(poly, height):
    return tm.creation.extrude_polygon(poly, height, engine='earcut')

def components(mesh):
    parent=list(range(len(mesh.vertices)))
    def root(a):
        while parent[a]!=a:
            parent[a]=parent[parent[a]]; a=parent[a]
        return a
    for face in mesh.faces:
        a=root(int(face[0]))
        for b in face[1:]: parent[root(int(b))]=a
    return len({root(i) for i in range(len(parent))})

def connector(kind='L', clearance=CLEAR, resolution=128):
    s = PLY + clearance
    body = tm.creation.cylinder(R, TH, sections=resolution)
    body.apply_translation([0,0,TH/2])
    v = box(-s/2, -s/2 if kind=='L' else -R-2, s/2, R+2)
    h = box(s/2-.2, -s/2, R+2, s/2)
    slots = extrude(unary_union([v,h]), TH-CAP+1)
    slots.apply_translation([0,0,CAP])
    result = tm.boolean.difference([body,slots], engine='manifold')
    result.remove_unreferenced_vertices()
    assert result.is_watertight and result.is_volume
    assert components(result) == 1
    return result

checks=[]
for kind in ['L','T']:
    m=connector(kind)
    fn=f'round-{kind.lower()}-15mm-gap03.stl'
    m.export(OUT/fn)
    checks.append(dict(file=fn,watertight=bool(m.is_watertight),components=components(m),bounds_mm=np.round(m.extents,3).tolist(),volume_cm3=round(m.volume/1000,2)))

plate=cuboid([95,26,10],[47.5,13,5])
cutters=[]
for x,c in zip([14,47.5,81],[.15,.3,.45]):
    cutters.append(cuboid([15+c,28,9],[x,13,6.5]))
plate=tm.boolean.difference([plate,*cutters],engine='manifold')
plate.export(OUT/'fit-test-015-030-045.stl')
checks.append(dict(file='fit-test-015-030-045.stl',watertight=bool(plate.is_watertight),components=components(plate),bounds_mm=np.round(plate.extents,3).tolist(),volume_cm3=round(plate.volume/1000,2)))

parts=[]
def add(name, mesh, mat, moving=False):
    parts.append(dict(name=name,mesh=mesh,material=mat,moving=moving))

for x,label in [(28,'left'),(372,'right')]:
    add(f'side-{label}', cuboid([15,336,1159],[x,172,600]), 'wood')
for z,label in [(28,'base'),(870,'divider'),(1172,'top')]:
    add(label, cuboid([329,336,15],[200,172,z]), 'wood')

# A screwed plywood back braces the cabinet; 4 mm spacers clear rear caps.
add('back-6mm',cuboid([359,6,1159],[200,347,600]),'back')
for x in [28,372]:
    for lo,hi in [(60,838),(902,1140)]:
        add('back-spacer',cuboid([15,4,hi-lo],[x,342,(lo+hi)/2]),'back')
for z in [28,870,1172]:
    add('back-spacer',cuboid([280,4,15],[200,342,z]),'back')

# Fixed narrow fascia strips allow a rectangular door to pass the round nodes.
for lo,hi,cz in [(35.5,58,28),(840,862.5,870)]:
    poly=box(35.5,lo,364.5,hi)
    for x in [28,372]:
        poly=poly.difference(Point(x,cz).buffer(28.5,quad_segs=32))
    m=extrude(poly,15)
    m.apply_transform(np.array([[1,0,0,0],[0,0,1,4],[0,1,0,0],[0,0,0,1]],float))
    add('front-fascia',m,'wood')

# One removable shelf on ordinary metal pins, behind the door.
add('inner-shelf',cuboid([325,306,15],[200,187,442.5]),'wood')
for x in [36.5,363.5]:
    for y in [70,300]:
        pin=tm.creation.cylinder(2.5,8,sections=16)
        pin.apply_transform(tm.transformations.rotation_matrix(math.pi/2,[0,1,0]))
        pin.apply_translation([x,y,432.5]); add('shelf-pin',pin,'metal')

door=cuboid([325,15,778],[200,11.5,449])
hole=tm.creation.cylinder(12,20,sections=64)
hole.apply_transform(tm.transformations.rotation_matrix(math.pi/2,[1,0,0]))
hole.apply_translation([340,11.5,449])
door=tm.boolean.difference([door,hole],engine='manifold')
add('door',door,'wood',True)
for z in [210,690]:
    hinge=tm.creation.cylinder(2.5,36,sections=16)
    hinge.apply_translation([37.5,4,z]); add('hinge-schematic',hinge,'metal')
    add('hinge-leaf-schematic',cuboid([15,2,30],[45,5,z]),'metal',True)

for rear in [False,True]:
    for x,sx in [(28,1),(372,-1)]:
        for z,sz,kind in [(28,1,'L'),(870,1,'T'),(1172,-1,'L')]:
            m=connector(kind,resolution=48)
            tr=np.array([[sx,0,0,x],[0,0,-1 if rear else 1,344 if rear else 0],[0,sz,0,z],[0,0,0,1]],float)
            m.apply_transform(tr)
            add(f'{kind}-connector',m,'connector')

# Anti-tip brackets are schematic metal hardware, not printable parts.
for x in [100,300]:
    add('wall-bracket-schematic',cuboid([24,2,34],[x,351,1130]),'metal')
    add('wall-bracket-schematic',cuboid([24,20,2],[x,342,1114]),'metal')

colors={'wood':[203,174,128,255],'back':[171,143,103,255],'connector':[52,91,83,255],'metal':[125,132,134,255]}
scene=tm.Scene()
for i,p in enumerate(parts):
    p['mesh'].visual.vertex_colors=colors[p['material']]
    scene.add_geometry(p['mesh'],node_name=f"{i:02d}-{p['name']}")
scene.apply_transform(tm.transformations.rotation_matrix(-math.pi/2,[1,0,0]))
scene.apply_transform(np.diag([.001,.001,.001,1]))
scene.export(OUT/'cabinet-concept.glb')

def mesh_json(mesh):
    return dict(v=np.round(mesh.vertices,3).tolist(),f=mesh.faces.tolist())
data=dict(parts=[dict(name=p['name'],material=p['material'],moving=p['moving'],**mesh_json(p['mesh'])) for p in parts],detail=mesh_json(connector('L',resolution=48)),detailT=mesh_json(connector('T',resolution=48)))
(ROOT/'work'/'cabinet-meshes.json').write_text(json.dumps(data,separators=(',',':')))
(OUT/'geometry-checks.json').write_text(json.dumps(checks,indent=2))
print(json.dumps(checks,ensure_ascii=False,indent=2))
print('Preview geometry bytes:',(ROOT/'work'/'cabinet-meshes.json').stat().st_size)
