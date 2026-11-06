"""Place the source DWG on its measured mounting datums with one rigid rotation.

The source flange normal is tilted by 3.27e-7 rad from file Y. This rotation
belongs to the installation coordinate frame, not to any individual part.
"""
from pathlib import Path
import json,math,shutil
import numpy as np
import cadquery as cq
from blum_sab208 import parse
from cq_acis.model import PlaneSurfaceEntity

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'outputs/blum-independent-v33'
OUT=SOURCE/'canonical'

def main():
    OUT.mkdir(exist_ok=True)
    cup,_=parse((ROOT/'inputs/supplier-cad/demos-71t6650/body-5.sab').read_bytes())
    flange=cup.resolve(789)
    assert isinstance(flange,PlaneSurfaceEntity)
    n=np.array([flange.normal.x,flange.normal.y,flange.normal.z]);n/=np.linalg.norm(n)
    assert abs(n[0])<1e-12 and n[1]>.999
    angle=math.atan2(-n[2],n[1]);c,s=math.cos(angle),math.sin(angle)
    rotation=np.array([[1.,0,0],[0,c,-s],[0,s,c]])
    assert np.linalg.norm(rotation@n-[0,1,0])<1e-12
    point=rotation@np.array([flange.origin.x,flange.origin.y,flange.origin.z])
    assert abs(point[1]+38.5)<1e-9
    records=[]
    for i in range(7):
        path=SOURCE/f'blum-71t6650-{i}.step'
        shape=cq.importers.importStep(str(path)).val()
        moved=shape.rotate((0,0,0),(1,0,0),math.degrees(angle))
        assert moved.isValid()
        cq.exporters.export(moved,str(OUT/path.name))
        records.append(dict(body=i,volume_before=shape.Volume(),volume_after=moved.Volume(),valid=True))
    for name in ('factory-meshes.npz','factory-visual-meshes.npz'):
        data=np.load(SOURCE/name)
        arrays={k:data[k]@rotation.T if k.endswith('-v') else data[k] for k in data.files}
        original_plate=np.load(ROOT/'outputs/wide-hinge-verification'/name)
        for key in ('blum-175h7190-0-v','blum-175h7190-0-f'):
            arrays[key]=original_plate[key]
        np.savez_compressed(OUT/name,**arrays)
    shutil.copyfile(ROOT/'outputs/wide-hinge-verification/blum-175h7190-0.step',OUT/'blum-175h7190-0.step')
    report=dict(source_plane_entity=789,source_normal=n.tolist(),source_point=[flange.origin.x,flange.origin.y,flange.origin.z],
        rotation_axis=[1,0,0],rotation_degrees=math.degrees(angle),rotation_matrix=rotation.tolist(),translation=[0,0,0],
        nominal_flange_y_mm=float(point[1]),individual_part_adjustments=False,bodies=records)
    (OUT/'alignment.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Common datum rotation degrees',math.degrees(angle),'flange Y',point[1])

if __name__=='__main__':main()
