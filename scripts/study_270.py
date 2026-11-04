"""Plan-view envelope study. The axis is idealized and has no hardware attached."""
from html import escape
import json
import math

from shapely import affinity
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from audit_assembly import ROOT, load_parts

MODEL = ROOT / 'outputs/cambusa-frame-v17'

AXIS = (0., -5.)
parts = load_parts(MODEL/'closed.glb')
left = {name:mesh for name,mesh in parts.items() if name.startswith('L-') and not name.endswith('-jamb')}
stationary = {name:mesh for name,mesh in parts.items()
              if not (name.startswith(('L-','R-')) and not name.endswith('-jamb'))}


def footprint(mesh):
    polygons = [Polygon(face[:, :2]) for face in mesh.triangles]
    return unary_union([poly for poly in polygons if poly.area > .0001])


leaves = {name:footprint(mesh) for name,mesh in left.items()}
wall_boxes = {name:box(*mesh.bounds[:, :2].reshape(-1)) for name,mesh in stationary.items()}
adjacent = {
    name: [obstacle for obstacle,mesh in stationary.items()
           if min(door.bounds[1,2],mesh.bounds[1,2])-max(door.bounds[0,2],mesh.bounds[0,2]) > .001]
    for name,door in left.items()
}
conflicts = []
for step in range(541):
    angle = step/2
    for name,shape in leaves.items():
        rotated = affinity.rotate(shape,-angle,origin=AXIS)
        for obstacle in adjacent[name]:
            area = rotated.intersection(wall_boxes[obstacle]).area
            if area > .05:
                conflicts.append([angle,name,obstacle,round(area,2)])
shape = unary_union(list(leaves.values()))
parked = affinity.rotate(shape,-270,origin=AXIS)
park_min_x, park_min_y, park_max_x, park_max_y = parked.bounds
full_radius = max(math.hypot(x-AXIS[0],y-AXIS[1]) for mesh in left.values() for x,y,z in mesh.vertices)
report = {
    'model':'cambusa-v17','axis_left_xy_mm':AXIS,'axis_right_xy_mm':[1000-AXIS[0],AXIS[1]],
    'scope':'2D conservative projection against box envelopes by part height, sampled every 0.5 degrees',
    'body_overlap_samples':conflicts,
    'leaf_separation_lower_bound_mm':round(1000-2*full_radius,2),
    'parked_lateral_clearance_mm':round(-park_min_x,2),
    'parked_gap_to_left_side_mm':round(-park_max_x,2),
    'parked_y_range_mm':[round(park_min_y,2),round(park_max_y,2)],
    'candidate_hinge':'EMKA 1056-U18, application-specific fit and load unverified',
    'hardware_verified':False,
}
(MODEL/'ХОД-270.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
canvas = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 610" role="img">',
          '<title>Расчётная парковка дверей на 270°</title>',
          '<rect width="100%" height="100%" fill="#f6f4ee"/>',
          '<g font-family="system-ui, sans-serif" fill="#252c2b">',
          '<text x="32" y="47" font-size="27" font-weight="bold">270° · створки вдоль боковин</text>',
          '<text x="32" y="76" font-size="17">Вид сверху · выносная ось как гипотеза · корпус 1000 × 500 мм</text>']
for index,angle in enumerate((0,90,180,270)):
    column,row=index%2,index//2
    cx=280+560*column
    cy=175+250*row
    scale=.20
    def coords(x,y):return cx+(x-500)*scale,cy-y*scale
    def draw_polygon(geom,color):
        if geom.geom_type == 'Polygon':
            points = ' '.join(f'{a:.2f},{b:.2f}' for a,b in (coords(x,y) for x,y in geom.exterior.coords))
            canvas.append(f'<polygon points="{points}" fill="{color}" stroke="#4d4133" stroke-width=".9"/>')
        else:
            for poly in geom.geoms:
                if poly.area > .01:
                    draw_polygon(poly,color)
    draw_polygon(box(0,0,1000,500),'#e6ddcb')
    left_shape=affinity.rotate(shape,-angle,origin=AXIS)
    draw_polygon(left_shape,'#a17851')
    draw_polygon(affinity.scale(left_shape,xfact=-1,yfact=1,origin=(500,0)),'#a17851')
    for x in (0,1000):
        a,b=coords(x,AXIS[1])
        canvas.append(f'<circle cx="{a}" cy="{b}" r="2.7" fill="#353d3a"/>')
    labels={0:'0° · закрыто',90:'90° · перед шкафом',180:'180° · створки в стороны',270:'270° · створки вдоль боковин'}
    canvas.append(f'<text x="{cx-220}" y="{cy+121}" font-size="17">{escape(labels[angle])}</text>')
canvas.append('</g></svg>')
(MODEL/'ход-270.svg').write_text('\n'.join(canvas)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='body_overlap_samples'},ensure_ascii=False))
print('samples with collisions',len(conflicts),'first',conflicts[:5])
