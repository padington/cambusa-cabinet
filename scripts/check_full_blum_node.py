"""Exact OCCT external-fit audit of the purchased hinge, not its manufacture.

Converted supplier solids overlap in the closed pose. Whether those overlaps
originate in supplier simplification or conversion has not been independently
established. This audit does not certify the internal mechanism.
"""
import json,math
from pathlib import Path
import numpy as np
import cadquery as cq
from blum_wide_kinematics import SixBar

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/wide-hinge-verification'
LINK=SixBar(json.loads((ROOT/'outputs/wide-hinge-study/linkage.json').read_text())['points'])


def box(low,high):
    low=np.array(low);high=np.array(high)
    return cq.Workplane().box(*(high-low)).translate(tuple((high+low)/2)).val()


def pose(shape,body,degrees):
    key={1:'P',2:'B',3:'Q',4:'E',5:'D'}.get(body)
    if key is None:return shape
    s=LINK.opening(degrees);a=s['angles'][body]
    r=np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
    return shape.rotate((0,0,0),(0,0,1),math.degrees(a)).translate((*(s['points'][key]-r@LINK.points[key]),0))


def wood(pockets=True):
    door=box([-445,-56.5,-482],[7,-38.5,482])
    door=door.cut(cq.Solid.makeCylinder(17.6,11.2,cq.Vector(-16,-38.5,0),cq.Vector(0,-1,0)))
    for z in (-22.5,22.5):
        door=door.cut(cq.Solid.makeCylinder(1.35,8,cq.Vector(-25.5,-38.5,z),cq.Vector(0,-1,0)))
    if pockets:
        pocket=cq.Workplane().box(12.5,3.2,25).edges('|Y').fillet(3).translate((3.75,-40.1,0)).val()
        door=door.cut(pocket)
    return door


def bounds(shape):
    b=shape.BoundingBox()
    return np.array([[b.xmin,b.ymin,b.zmin],[b.xmax,b.ymax,b.zmax]])


def common(a,b):
    aa,bb=bounds(a),bounds(b)
    if np.min(np.minimum(aa[1],bb[1])-np.maximum(aa[0],bb[0]))<.00001:return 0.
    return max(0.,float(a.intersect(b).Volume()))


def main():
    shapes=[cq.importers.importStep(str(OUT/f'blum-71t6650-{i}.step')).val() for i in range(7)]
    plate=cq.importers.importStep(str(OUT/'blum-175h7190-0.step')).val()
    door=wood();obstacles={'side-24':box([9,-26,-550],[33,390,550]),
                          'OB3030-post-conservative-box':box([9,-56.5,-550],[39,-26.5,550])}
    report=dict(hinge='71T6650',plate='175H7190',source_solids=8,
        exact_brep=True,pocket_mm=[9.5,25,3.2],pocket_internal_radius_mm=3,
        cup_bore_mm=[35.2,11.2],pilot_mm=[2.7,8],sample_step_degrees=.25,
        collision_volume_threshold_mm3=.001,unexpected=[],converted_internal_intersections=[],
        scope='external fit of commercial product envelopes; not internal mechanism or load certification')
    for i,a in enumerate(shapes):
        for j,b in enumerate(shapes):
            if j<=i:continue
            v=common(a,b)
            if v>.001:report['converted_internal_intersections'].append([i,j,v])
    old=wood(False)
    report['old_door_contact_170_mm3']=common(pose(shapes[2],2,170),pose(old,5,170))
    for name,b in obstacles.items():
        for i in (0,6):
            v=common(shapes[i],b)
            if v>.001:report['unexpected'].append([0,i,name,v])
        v=common(plate,b)
        if v>.001:report['unexpected'].append([0,'plate',name,v])
    # Cup and door move rigidly together, so their one relative test applies
    # to every angle. The side is a full solid: blind pegholes cannot worsen fit.
    v=common(shapes[5],door);report['cup_wood_overlap_mm3']=v
    if v>.001:report['unexpected'].append([0,5,'door',v])
    samples=np.linspace(0,170,681)
    for k,d in enumerate(samples):
        d=float(d);leaf=pose(door,5,d)
        for i,a in enumerate(shapes):
            moving=pose(a,i,d)
            if i!=5:
                v=common(moving,leaf)
                if v>.001:report['unexpected'].append([d,i,'door',v])
            if i not in (0,6):
                for name,b in obstacles.items():
                    v=common(moving,b)
                    if v>.001:report['unexpected'].append([d,i,name,v])
        if k%100==0 or k==len(samples)-1:
            print('exact fit',d,'unexpected',len(report['unexpected']),flush=True)
            (OUT/'exact-fit.json').write_text(json.dumps(report,indent=2)+'\n')
    report['sample_count']=len(samples)
    report['external_nominal_fit_passed']=not report['unexpected']
    report['internal_mechanism_certified']=False
    report['physical_load_test_performed']=False
    (OUT/'exact-fit.json').write_text(json.dumps(report,indent=2)+'\n')
    assert not report['unexpected'],report['unexpected'][:8]


if __name__=='__main__':main()
