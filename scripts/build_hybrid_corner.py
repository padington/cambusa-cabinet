"""Full-size v19 corner and door for checking the DIRAK 4-278 mounting planes."""
from itertools import combinations
import json
import math
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely import affinity
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
import trimesh as tm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work'))
from geometry import COLORS, add, cube, render, scene

OUT = ROOT/'outputs/cambusa-hybrid-v19-corner'
OUT.mkdir(exist_ok=True)
CATALOG = 'https://www.dirak.at/uploads/4aaYA9mc/DIRAKHingesc.pdf#page=27'
HARDWARE = 'DIRAK 267-9004.00-00000'
MOUNT_OFFSET = 9.5  # Provisional symmetric interpretation of the 19 mm folded dimension.
AXIS = np.array([6-MOUNT_OFFSET,-19.])
DOOR_Y = AXIS[1]+MOUNT_OFFSET
CENTERS = (960.,1640.)
RADIUS = 3.3
SIDE_THICK = 18.
DOOR_THICK = 18.
CASE_FRONT = -8.
DOOR_EDGE = 21.5
BODY = []
DOOR = []
COLORS.update(wood=[113,81,58,255], door=[107,73,50,255], back=[75,55,42,255],
              frame=[46,50,50,255], rail=[141,150,150,255], tray=[139,105,76,255])


def solid_difference(stock,cuts):
    result = tm.boolean.difference([stock,*cuts],engine='manifold')
    assert result.is_volume
    return result


def bore(axis,start,end,position,radius=RADIUS):
    mesh = tm.creation.cylinder(radius=radius,height=end-start,sections=32)
    if axis == 0:
        mesh.apply_transform(tm.transformations.rotation_matrix(math.pi/2,[0,1,0]))
        mesh.apply_translation([(start+end)/2,*position])
    else:
        mesh.apply_transform(tm.transformations.rotation_matrix(math.pi/2,[1,0,0]))
        mesh.apply_translation([position[0],(start+end)/2,position[1]])
    return mesh


# The cabinet corner is an 18 mm solid side with local mounting rebates.
# Aluminum can still support the box below Z800, independent of the hinge.
side_blank = cube([0,CASE_FRONT,818],[SIDE_THICK,500,1782])
fixed_rebates = [cube([-.1,CASE_FRONT-.1,z-34],[6,13,z+34]) for z in CENTERS]
fixed_row_y = AXIS[1]+19
fixed_bores = [bore(0,-.1,18.1,(fixed_row_y,z+dz)) for z in CENTERS for dz in (-25.5,25.5)]
add(BODY,'Side-18-rebated',solid_difference(side_blank,fixed_rebates+fixed_bores),'wood','case')
add(BODY,'Bottom-18',cube([0,0,800],[1000,500,818]),'wood','case')
add(BODY,'Top-18',cube([0,0,1782],[1000,500,1800]),'wood','case')
add(BODY,'Back-12',cube([18,488,818],[982,500,1782]),'back','case')
add(BODY,'Center-18',cube([491,103,818],[509,488,1782]),'wood','case')
for row,z in enumerate((1138,1458),1):
    add(BODY,f'Left-shelf-{row}-18',cube([18,103,z],[491,488,z+18]),'wood','case')

# Through-bores use the plate pattern in the manufacturer drawing.
# Leaf slabs model its flat regions; knuckle detail and screw heads are not CAD.
door_holes = [(AXIS[0]+32,-25.5),(AXIS[0]+32,25.5),(AXIS[0]+102,0)]
face_bores = [bore(1,DOOR_Y-.1,DOOR_Y+DOOR_THICK+.1,(x,z+dz))
              for z in CENTERS for x,dz in door_holes]
face = cube([DOOR_EDGE,DOOR_Y,821],[497,DOOR_Y+DOOR_THICK,1767])
add(DOOR,'Door-face-18',solid_difference(face,face_bores),'door','door')
inner_y=DOOR_Y+DOOR_THICK
lip_y=inner_y+55
rear_y=lip_y+12
for name,x in [('hinge',74),('meeting',449)]:
    add(DOOR,f'Door-inner-{name}-18',cube([x,inner_y,821],[x+18,rear_y,1767]),'door','door')
for row,z in enumerate((934,1234,1534),1):
    add(DOOR,f'Door-tray-{row}-12',cube([92,inner_y,z],[449,lip_y,z+12]),'tray','door')
    add(DOOR,f'Door-lip-{row}-12',cube([92,lip_y,z+12],[449,rear_y,z+50]),'door','door')
for row,z in enumerate(CENTERS,1):
    plate = cube([AXIS[0]+14,DOOR_Y-4,z-32.5],[AXIS[0]+116,DOOR_Y,z+32.5])
    holes = [bore(1,DOOR_Y-4.1,DOOR_Y+.1,(x,z+dz)) for x,dz in door_holes]
    add(DOOR,f'DIRAK-moving-flat-{row}',solid_difference(plate,holes),'rail','door')
    plate = cube([2,AXIS[1]+14,z-32.5],[6,AXIS[1]+30,z+32.5])
    holes = [bore(0,1.9,6.1,(fixed_row_y,z+dz)) for dz in (-25.5,25.5)]
    add(BODY,f'DIRAK-fixed-flat-{row}',solid_difference(plate,holes),'rail','fixed')

# Left half of the real-sized case. The exterior line of the opposite side
# constrains the leaf sweep, without modelling a redundant second door.
add(BODY,'Opposite-side-18',cube([982,CASE_FRONT,818],[1000,500,1782]),'wood','case')


def pose(angle):
    transform = tm.transformations.rotation_matrix(math.radians(-angle),[0,0,1],[*AXIS,0])
    return BODY + [dict(part,mesh=part['mesh'].copy().apply_transform(transform)) for part in DOOR]


def intersections(parts):
    pairs = []
    for a,b in combinations(parts,2):
        am,bm = a['mesh'],b['mesh']
        envelope_overlap = np.minimum(am.bounds[1],bm.bounds[1])-np.maximum(am.bounds[0],bm.bounds[0])
        if envelope_overlap.min() <= .001:
            continue
        overlap = tm.boolean.intersection([am,bm],engine='manifold')
        if len(overlap.faces) and overlap.volume > .08:
            pairs.append([a['name'],b['name'],round(float(overlap.volume),3)])
    return pairs


def footprint(mesh):
    polygons=[Polygon(face[:,:2]) for face in mesh.triangles]
    return unary_union([poly for poly in polygons if poly.area>.001])


# Conservative body envelopes are used between endpoints. Mount rebate contact
# is accounted for in the exact static 3D test. A single axis models rigid leaves.
fixed = [(box(*p['mesh'].bounds[:,:2].reshape(-1)),*p['mesh'].bounds[:,2]) for p in BODY]
checks = []
for p in DOOR:
    mesh=p['mesh']
    z0,z1=mesh.bounds[:,2]
    obstacles=[shape for shape,bottom,top in fixed if min(z1,top)-max(z0,bottom)>.001]
    checks.append((p['name'],footprint(mesh),obstacles))
hits=[]
clearance=math.inf
step=.125
for index in range(round(270/step)+1):
    angle=index*step
    for name,shape,obstacles in checks:
        moved=affinity.rotate(shape,-angle,origin=tuple(AXIS))
        for obstacle in obstacles:
            distance=moved.distance(obstacle)
            clearance=min(clearance,distance)
            if distance<1e-6 and moved.intersection(obstacle).area>.02:
                hits.append([angle,name])
reach=max(np.linalg.norm(v[:2]-AXIS) for p in DOOR for v in p['mesh'].vertices)
sample_displacement=2*reach*math.sin(math.radians(step/4))
seam_clearance=1000-2*(AXIS[0]+reach)
results={str(angle):intersections(pose(angle)) for angle in (0,90,180,270)}
assert all(not pair for pair in results.values()), results
assert not hits,hits[:10]
assert clearance>sample_displacement and seam_clearance>0

stile_margin=door_holes[0][0]-DOOR_EDGE
side_margin=fixed_row_y-CASE_FRONT
assert stile_margin>RADIUS and side_margin>RADIUS
parts_by_name={part['name']:part['mesh'] for part in BODY+DOOR}
clear_channels=0
for row,z in enumerate(CENTERS,1):
    for direction,lo,hi,centers,targets in (
        (0,1.9,18.1,[(fixed_row_y,z-25.5),(fixed_row_y,z+25.5)],
         ('Side-18-rebated',f'DIRAK-fixed-flat-{row}')),
        (1,DOOR_Y-4.1,DOOR_Y+DOOR_THICK+.1,[(x,z+dz) for x,dz in door_holes],
         ('Door-face-18',f'DIRAK-moving-flat-{row}')),
    ):
        for center in centers:
            probe=bore(direction,lo,hi,center,radius=3.2)
            for target in targets:
                collision=tm.boolean.intersection([probe,parts_by_name[target]],engine='manifold')
                assert not len(collision.faces) or abs(float(collision.volume))<.01, (target,center)
            clear_channels+=1
assert clear_channels==10

moving_wood=[part['mesh'] for part in DOOR if part['material']!='rail']
wood_mass=np.asarray([mesh.volume*680/1e9 for mesh in moving_wood])
door_com=np.average([mesh.center_mass for mesh in moving_wood],axis=0,weights=wood_mass)
payload_reach=max(np.linalg.norm(vertex[:2]-AXIS)
                  for part in DOOR if part['name'].startswith('Door-tray')
                  for vertex in part['mesh'].vertices)
test_payload=3
test_moment=(wood_mass.sum()*np.linalg.norm(door_com[:2]-AXIS)+test_payload*payload_reach)*9.81/1000
for name,angle in [('closed',0),('open-270',270)]:
    path=OUT/f'{name}.glb'
    path.write_bytes(scene(pose(angle)).export(file_type='glb'))
    reopened=tm.load(path,force='scene')
    assert len(reopened.geometry)==len(BODY)+len(DOOR)

record={
    'iteration':'cambusa-v19-hybrid-corner','hardware':HARDWARE,'source':CATALOG,
    'mounting_face_offset_mm_assumed':MOUNT_OFFSET,'axis_xy_mm':AXIS.tolist(),
    'hinge_centers_z_mm':CENTERS,'hinge_bore_diameter_mm':2*RADIUS,
    'fixed_side_mount_x_mm':6,'fixed_face_rebate_mm':6,'wood_behind_rebate_mm':SIDE_THICK-6,
    'fixed_row_from_front_mm':float(side_margin),'door_holes_x_mm':[float(x) for x,_ in door_holes],
    'door_near_hole_center_from_edge_mm':float(stile_margin),
    'minimum_wood_ligament_to_near_door_bore_mm':round(float(stile_margin-RADIUS),2),
    'door_body_mm':[497-DOOR_EDGE,1767-821,round(rear_y-DOOR_Y,2)],
    'nominal_plywood_mm':[12,18],'external_adapter_plates_in_this_model':0,
    'aligned_bore_channels':clear_channels,
    'wooden_door_mass_kg_assumed_density_680':round(float(wood_mass.sum()),2),
    'test_scenario':{'payload_at_outer_shelf_edge_kg':test_payload,
                     'static_weight_moment_nm_excluding_hardware':round(float(test_moment),2)},
    'endpoint_solid_intersections_mm3':results,'sample_step_deg':step,
    'minimum_sample_clearance_mm':round(clearance,3),
    'continuous_clearance_lower_bound_mm':round(clearance-sample_displacement,3),
    'opposite_door_separation_lower_bound_mm':round(float(seam_clearance),3),
    'not_checked':['Exact hinge CAD, pin and screw heads','Fastener strength at the edge','Loaded door, carcass and wall attachment'],
    'release_for_machining':False,
}
(OUT/'ПРОВЕРКА.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')

image=Image.new('RGB',(1380,890),'#f6f5f1')
draw=ImageDraw.Draw(image)
try:
    font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',24)
    title=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf',34)
except OSError:
    font=ImageFont.load_default(size=24)
    title=ImageFont.load_default(size=34)
draw.text((30,24),'Cambusa v19 · пробный узел DIRAK в масштабе 1:1',font=title,fill='#25352b')
for x,label,angle,yaw in ((0,'Закрыто · привязка по чертежу',0,25),(690,'Расчётный вид на 270°',270,-35)):
    image.paste(render(pose(angle),690,740,yaw=yaw,pitch=12),(x,94))
    draw.text((x+28,842),label,font=font,fill='#25352b')
image.save(OUT/'preview.png')

# Printed 1:1 checking pattern derived from the same coordinates as the bores.
svg = [
    '<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297" role="img">',
    '<title>Шаблон сверки отверстий DIRAK 267-9004 в масштабе 1:1</title>',
    '<rect width="210" height="297" fill="white"/>',
    '<g font-family="sans-serif" fill="#23312d" font-size="3.7">',
    '<text x="14" y="17" font-size="6" font-weight="bold">Cambusa v19 · проверка петли</text>',
    '<text x="14" y="26">DIRAK 267-9004.00-00000 · масштаб 1:1 · печать 100%</text>',
    '<text x="14" y="34">Шаблон для сверки. Присадка к заказу не выпущена.</text>',
]
for caption,cy,holes,edge_offsets in (
    ('Створка · снаружи',83,[(x-DOOR_EDGE,dz) for x,dz in door_holes],[7,77]),
    ('Боковина · снаружи',177,[(side_margin,dz) for dz in (-25.5,25.5)],[8]),
):
    x0=25
    svg.append(f'<text x="14" y="{cy-36}" font-size="4.5" font-weight="bold">{caption}</text>')
    svg.append(f'<line x1="{x0}" y1="{cy-31}" x2="{x0}" y2="{cy+31}" stroke="#23312d" stroke-width=".35"/>')
    svg.append(f'<line x1="{x0-4}" y1="{cy}" x2="{x0+109}" y2="{cy}" stroke="#74827c" stroke-dasharray="1.5 1"/>')
    for x,dz in holes:
        cx,cy0=x0+x,cy-dz
        svg.append(f'<circle cx="{cx:g}" cy="{cy0:g}" r="{RADIUS}" fill="white" stroke="#31483f" stroke-width=".35"/>')
        svg.append(f'<path d="M {cx-1:g},{cy0:g} h 2 m -1,-1 v 2" fill="none" stroke="#31483f" stroke-width=".22"/>')
    offsets=' / '.join(str(offset) for offset in edge_offsets)
    svg.append(f'<text x="139" y="{cy-6}">От кромки {offsets} мм</text>')
    svg.append(f'<text x="139" y="{cy+2}">Разнос крайних 51 мм</text>')
    svg.append(f'<text x="139" y="{cy+10}">Отверстия Ø6,6 мм</text>')
svg.extend([
    '<rect x="141" y="224" width="50" height="50" fill="none" stroke="#23312d" stroke-width=".3"/>',
    '<text x="166" y="251" text-anchor="middle">50 × 50 мм</text>',
    '<text x="14" y="231">Измерьте квадрат после печати.</text>',
    '<text x="14" y="241">Один рисунок на каждую петлю.</text>',
    '<text x="14" y="251">Высоты осей 960 и 1640 мм от пола.</text>',
    '</g></svg>',
])
(OUT/'контроль-1к1.svg').write_text('\n'.join(svg)+'\n')
print(json.dumps(record,ensure_ascii=False))
