"""Recheck the independent source and the v33 relief, including a clearance target."""
import json
from pathlib import Path
import numpy as np
import cadquery as cq
from check_full_blum_node import pose,box,common
import blum_node_v33_spec as spec

ROOT=Path(__file__).resolve().parents[1]
CAD=ROOT/'outputs/blum-independent-v33/canonical'
OUT=ROOT/f'outputs/{spec.VERSION}'

def main():
    OUT.mkdir(exist_ok=True)
    shapes=[cq.importers.importStep(str(CAD/f'blum-71t6650-{i}.step')).val() for i in range(7)]
    plate=cq.importers.importStep(str(CAD/'blum-175h7190-0.step')).val()
    door=spec.native_door()
    obstacles={'side-24':box([9,-26,-550],[33,390,550]),
        'OB3030-post-conservative-box':box([9,-56.5,-550],[39,-26.5,550])}
    report=dict(version=spec.VERSION,hinge='71T6650',plate='175H7190',
        source='Independent Demos DWG; all seven bodies; common mounting-datum rotation',
        pocket_mm=[spec.RELIEF_WIDTH,spec.RELIEF_HEIGHT,spec.RELIEF_DEPTH],
        pocket_radius_mm=spec.RELIEF_RADIUS,cup_bore_mm=[spec.CUP_DIAMETER,spec.CUP_DEPTH],
        exact_brep=True,sample_step_degrees=.25,collision_volume_threshold_mm3=.001,
        target_moving_link_clearance_mm=spec.TARGET_MOVING_LINK_CLEARANCE,
        unexpected=[],minimum_moving_link_clearance={},factory_model_internal_overlaps=[])
    for i,a in enumerate(shapes):
        for j in range(i+1,7):
            v=common(a,shapes[j])
            if v>.001:report['factory_model_internal_overlaps'].append([i,j,v])
    for name,b in obstacles.items():
        for i in (0,6):
            v=common(shapes[i],b)
            if v>.001:report['unexpected'].append([0,i,name,v])
        v=common(plate,b)
        if v>.001:report['unexpected'].append([0,'plate',name,v])
    v=common(shapes[5],door);report['cup_wood_overlap_mm3']=v
    if v>.001:report['unexpected'].append([0,5,'door',v])
    for k,d in enumerate(np.linspace(0,170,681)):
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
            if i in (1,2,3,4):
                distance=moving.distance(leaf)
                previous=report['minimum_moving_link_clearance'].get(str(i),dict(mm=1e9))
                if distance<previous['mm']:report['minimum_moving_link_clearance'][str(i)]=dict(mm=distance,degrees=d)
        if k%100==0 or k==680:
            print('v33 angle',d,'unexpected',len(report['unexpected']),flush=True)
            (OUT/'exact-fit.json').write_text(json.dumps(report,indent=2)+'\n')
    report.update(sample_count=681,external_nominal_fit_passed=not report['unexpected'],
        sampled_clearance_target_passed=all(r['mm']>=spec.TARGET_MOVING_LINK_CLEARANCE for r in report['minimum_moving_link_clearance'].values()),
        source_overlap_independently_confirmed_for_bodies=[2,4],
        physical_test_performed=False,extreme_adjustment_combinations_checked=False,
        scope='Purchased hinge exterior fit at nominal adjustment, using the previous factory-derived six-bar pivot graph; source CAD bodies are not physically disjoint internal components. Finite angular samples, not a continuous clearance certificate.')
    (OUT/'exact-fit.json').write_text(json.dumps(report,indent=2)+'\n')
    assert report['external_nominal_fit_passed'] and report['sampled_clearance_target_passed']

if __name__=='__main__':main()
