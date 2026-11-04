"""Check catalog hole patterns and a proposed adapter envelope against v18."""
import json
import math

import numpy as np
from shapely import affinity
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from audit_assembly import MODEL, ROOT, load_parts

OUT = ROOT/'outputs/hinge-frame-review'
OUT.mkdir(exist_ok=True)
parts = load_parts(MODEL/'closed.glb')
doors = {name:mesh for name,mesh in parts.items() if name.startswith('L-') and not name.endswith('-jamb')}
cabinet = {name:mesh for name,mesh in parts.items()
           if not (name.startswith(('L-','R-')) and not name.endswith('-jamb'))}
wood_bounds = doors['L-hinge-stile'].bounds
stile_left, stile_right = wood_bounds[:,0]
door_front = wood_bounds[0,1]
mount_z = (960,1640)
# Catalogue dimensions from DIRAK catalogue pages 532–533 and EMKA front drawing.
catalog_holes = {'EMKA 1056-U18':[(28,-15),(28,15)],
                 'DIRAK 218-9210.00-00000':[(45,-18),(45,18)],
                 'DIRAK 267-9004.00-00000':[(32,-25.5),(32,25.5),(102,0)]}
fit = {}
for article, holes in catalog_holes.items():
    fit[article] = [{'x_mm':x,'relative_z_mm':z,'center_on_stile':bool(stile_left<x<stile_right)}
                    for x,z in holes]
assert [sum(h['center_on_stile'] for h in fit[k]) for k in catalog_holes] == [0,0,1]


def projection(mesh):
    faces = [Polygon(tri[:,:2]) for tri in mesh.triangles]
    return unary_union([face for face in faces if face.area > .0001])


moving = [(projection(mesh),*mesh.bounds[:,2]) for mesh in doors.values()]
stationary = [(box(*mesh.bounds[:,:2].reshape(-1)),*mesh.bounds[:,2]) for mesh in cabinet.values()]


def common_z(a,b):
    return min(a[2],b[2])-max(a[1],b[1]) > .001


# Catalogue fastener centers are checked in projected solid mounting zones.
# The mounting-face offset is a hypothesis pending measurement of the actual hinge.
sweep_results = []
for offset in (8,9.5,11):
    axis = (-6-offset,-20.)
    door_plate_y = axis[1]+offset
    moving_adapter = box(9,door_plate_y,107,door_plate_y+6).union(
        box(74,door_plate_y+6,107,door_front))
    frame_adapter = box(-6,-8,0,29)
    # The catalogue specifies 4 mm plate thickness. At the knuckle the
    # assembly has alternating fingers, whose solid CAD is still needed.
    flat_door_leaf = box(axis[0]+14,door_plate_y-4,axis[0]+116,door_plate_y)
    flat_frame_leaf = box(-10,axis[1]+14,-6,axis[1]+30)
    radius = 3.3
    moving_centers = [axis[0]+32,axis[0]+102]
    frame_center_y = axis[1]+19
    assert all(9+radius<x<107-radius for x in moving_centers)
    assert -8+radius < frame_center_y < 29-radius
    assert stile_left+radius < moving_centers[1] < stile_right-radius
    assert door_plate_y+6 <= -1+1e-9
    motion = moving + [(moving_adapter,z-33,z+33) for z in mount_z]
    motion += [(flat_door_leaf,z-32.5,z+32.5) for z in mount_z]
    fixed = stationary + [(frame_adapter,z-48,z+48) for z in mount_z]
    fixed += [(flat_frame_leaf,z-32.5,z+32.5) for z in mount_z]
    checks = [(shape,[obstacle[0] for obstacle in fixed if common_z((shape,z0,z1),obstacle)])
              for shape,z0,z1 in motion]
    collisions = []
    min_clearance = math.inf
    step = .125
    for index in range(round(270/step)+1):
        angle = index*step
        for shape, obstacles in checks:
            transformed = affinity.rotate(shape,-angle,origin=axis)
            for obstacle in obstacles:
                clearance = transformed.distance(obstacle)
                min_clearance = min(clearance,min_clearance)
                if clearance < .001 and transformed.intersection(obstacle).area > .05:
                    collisions.append(angle)
    furthest = max(math.dist(axis,point) for shape,_,_ in motion for poly in
                   (shape.geoms if shape.geom_type == 'MultiPolygon' else [shape]) for point in poly.exterior.coords)
    rotation_bound = 2*furthest*math.sin(math.radians(step/4))
    seam_gap = 1000-2*(axis[0]+furthest)
    sweep_results.append({
        'axis_to_mounting_face_hypothesis_mm':offset,'axis_xy_mm':axis,
        'door_hole_x_mm':moving_centers,'frame_hole_y_mm':frame_center_y,
        'nominal_modeled_profile_slot_y_mm':15,'frame_hole_to_slot_center_mm':abs(frame_center_y-15),
        'max_sample_step_deg':step,'collision_angles':sorted(set(collisions)),
        'minimum_sample_clearance_mm':round(min_clearance,3),
        'maximum_between_sample_displacement_mm':round(rotation_bound,3),
        'continuous_clearance_bound_mm':round(min_clearance-rotation_bound,3),
        'lower_bound_between_leaves_mm':round(seam_gap,3),
    })

# Weight moment around the horizontal axis through the hinge stack. An explicit
# test payload is placed at the far end of the shelves, not treated as a rating.
axis = sweep_results[1]['axis_xy_mm']
volumes = np.array([mesh.volume for mesh in doors.values()])
masses = volumes*np.array([720 if name.endswith('-stile') else 680 for name in doors])/1e9
com = np.average([mesh.center_mass for mesh in doors.values()],axis=0,weights=masses)
empty_mass = float(masses.sum())
farthest_shelf = max(math.dist(axis,vertex[:2]) for name,mesh in doors.items() if '-shelf-' in name for vertex in mesh.vertices)
load = []
for payload in (0,3,6):
    moment = (empty_mass*math.dist(axis,com[:2])+payload*farthest_shelf)*9.81/1000
    load.append({'door_storage_payload_kg':payload,'door_and_payload_weight_n':round((empty_mass+payload)*9.81,1),
                 'weight_moment_nm':round(moment,1),
                 'radial_reaction_from_weight_per_hinge_n':round(moment/((mount_z[1]-mount_z[0])/1000),1)})
plan = json.loads((MODEL/'planning/plan.json').read_text())
parts_plan = [part['id'] for part in plan['parts']]

# Try a common 12 mm stock for the current 9 and 12 mm rectangular blanks.
# This compares stock, independently of the joinery changes needed.
blanks = [part for part in plan['parts'] if part['stock'] in ('plywood-9','plywood-12')]
bins = []
for part in sorted(blanks,key=lambda p:(math.prod(p['blank_mm']),p['id']),reverse=True):
    w,h = (size+6 for size in part['blank_mm'])
    found = next(((sheet,i) for sheet in bins for i,(width,height) in enumerate(sheet)
                  if width>=w and height>=h),None)
    if found is None:
        bins.append([(1511,1511)])
        found = bins[-1],0
    sheet,i = found
    width,height = sheet.pop(i)
    sheet.extend(((width-w,h),(width,height-h)))
sheet_count_18 = sum(sheet['stock']=='plywood-18' for sheet in plan['sheets'])

report = {
    'base':'cambusa-v18','original_axis_xy_mm':[0,-5],
    'door_stile_x_range_mm':[float(stile_left),float(stile_right)],
    'nominal_hinge_center_z_mm':mount_z,
    'direct_catalog_holes_with_original_axis':fit,
    'adapter_envelope_study':sweep_results,
    'scope':'Projected door, adapters and flat leaf envelopes. Knuckle, screws and actual axis offset are excluded.',
    'modeled_empty_door_without_hardware_kg':round(empty_mass,2),
    'modeled_empty_door_center_of_mass_mm':com.round(2).tolist(),
    'static_load_cases':load,
    'extrusion_frame':{'posts':sum(p.startswith('Post-') for p in parts_plan),
                       'crossmembers':sum(p.startswith('Beam-') for p in parts_plan),
                       'crossmember_ends':2*sum(p.startswith('Beam-') for p in parts_plan),
                       'additional_shelf_angles':sum(p.startswith('ShelfAngle-') for p in parts_plan)},
    'two_gauge_stock_study':{'sheet_mm':[1525,1525],'sheets_12_mm':len(bins),
                             'sheets_18_mm':sheet_count_18,
                             'requires_back_and_lip_joinery_redesign':True},
    'manufacturing_ready':False,
}
(OUT/'ПРОВЕРКА.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

# Overlay exact bore centers on the front-view wood and frame zones.
svg = [
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 485" role="img">',
    '<title>Крепёж длинной петли DIRAK и стойка створки v18</title>',
    '<rect width="1120" height="485" fill="#f7f4ec"/>',
    '<g font-family="system-ui,sans-serif" fill="#23312d">',
    '<text x="32" y="45" font-size="25" font-weight="bold">DIRAK 267-9004 · где окажутся отверстия</text>',
    '<text x="32" y="76" font-size="16">Вид спереди при оси X = 0 мм · крепёж в стойку попадает только в одной точке</text>',
]
origin_x, origin_z, scale = 95, 241, 7.8
for left,right,paint,caption in (
    (0,30,'#707d7d','Профиль'),
    (31,67,'#a69a82','Косяк'),
    (stile_left,stile_right,'#b78b63','Стойка створки'),
):
    start = origin_x+left*scale
    width = (right-left)*scale
    svg.append(f'<rect x="{start}" y="119" width="{width}" height="252" rx="2" fill="{paint}" opacity=".38"/>')
    svg.append(f'<text x="{start+width/2}" y="397" text-anchor="middle" font-size="17">{caption}</text>')
svg.append(f'<line x1="{origin_x}" y1="105" x2="{origin_x}" y2="381" stroke="#23312d" stroke-width="2"/>')
for hole in fit['DIRAK 267-9004.00-00000']:
    x = origin_x + hole['x_mm']*scale
    y = origin_z - hole['relative_z_mm']*4
    color = '#29755a' if hole['center_on_stile'] else '#a44739'
    svg.append(f'<circle cx="{x}" cy="{y}" r="9" fill="#f7f4ec" stroke="{color}" stroke-width="3"/>')
    svg.append(f'<text x="{x+15}" y="{y+5}" fill="{color}" font-size="16">X = {hole["x_mm"]} мм</text>')
svg.extend([
    '<text x="95" y="423" font-size="16">Ось</text>',
    '<text x="340" y="423" font-size="16">Оба ближних отверстия над неподвижным косяком</text>',
    '<text x="32" y="463" font-size="15">Размеры отверстий взяты из каталога DIRAK, границы дерева и профиля из закрытой модели v18.</text>',
    '</g></svg>',
])
(OUT/'привязка-DIRAK.svg').write_text('\n'.join(svg)+'\n')
print(json.dumps({k:report[k] for k in ('adapter_envelope_study','modeled_empty_door_without_hardware_kg','static_load_cases','extrusion_frame')},ensure_ascii=False))
