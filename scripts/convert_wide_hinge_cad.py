"""Preserve factory SAT and convert supported solids without repairing geometry.

Requires the separate requirements-cad.txt environment. Failures are recorded,
never silently replaced by a pretend factory mesh.
"""
import json
from pathlib import Path

import cadquery as cq
from cq_acis import import_sat_data
import ezdxf
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/wide-hinge-study'


def main():
    OUT.mkdir(exist_ok=True);report={};arrays={}
    for name in ('blum-71t6650','blum-175h7190'):
        report[name]=[]
        doc=ezdxf.readfile(ROOT/f'inputs/supplier-cad/{name}.dxf')
        assert int(doc.header['$INSUNITS'])==4,'CAD must use millimetres'
        for i,solid in enumerate(doc.modelspace().query('3DSOLID')):
            # DXF chunks after the three SAT header lines split even individual
            # numeric tokens; adding newlines at every chunk corrupts them.
            raw='\n'.join(solid.sat[:3])+'\n'+''.join(solid.sat[3:])
            path=OUT/f'{name}-{i}.sat';path.write_text(raw)
            row=dict(part=i)
            try:
                shape=import_sat_data(raw).val()
                assert shape.isValid() and shape.Volume()>0
                cq.exporters.export(shape,str(OUT/f'{name}-{i}.step'))
                vertices,faces=shape.tessellate(.1,.15)
                v=np.array([q.toTuple() for q in vertices]);f=np.array(faces,dtype=np.int32)
                arrays[f'{name}-{i}-v']=v;arrays[f'{name}-{i}-f']=f
                row.update(valid=True,volume=shape.Volume(),bounds=[v.min(axis=0).tolist(),v.max(axis=0).tolist()],triangles=len(faces))
            except Exception as error:
                row['error']=f'{type(error).__name__}: {error}'
            print(name,i,row,flush=True);report[name].append(row)
    assert set(arrays)=={f'blum-71t6650-{i}-{key}' for i in (1,6) for key in ('v','f')}
    np.savez_compressed(OUT/'factory-meshes.npz',**arrays)
    (OUT/'cad-conversion.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
