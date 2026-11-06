import cadquery as cq
from pathlib import Path
import json
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/wide-hinge-verification'
import argparse
parser=argparse.ArgumentParser(description='Seat nominal 609.1500 screws in supplier CAD')
parser.add_argument('--cad-dir',type=Path,default=OUT)
OUT=parser.parse_args().cad_dir
def screw():
    # Blum 609.1500: total 15 incl head, head Ø7 / H2.09. Thread is an envelope.
    return cq.Workplane('XZ').polyline([(0,0),(3.5,0),(3.5,.34),(1.75,2.09),
        (1.75,12.5),(0,15)]).close().revolve().val()
s=screw();print('screw bounds',s.BoundingBox().xmin,s.BoundingBox().zmax,flush=True)
report={};arrays={}
for name,part,point,direction,interval in [
    ('plate','blum-175h7190-0',(0,0,16),(1,0,0),(3.5,9)),
    ('cup','blum-71t6650-5',(-25.5,0,22.5),(0,-1,0),(33,38.5))]:
    metal=cq.importers.importStep(str(OUT/f'{part}.step')).val()
    oriented=s.rotate((0,0,0),(0,1,0),90) if name=='plate' else s.rotate((0,0,0),(1,0,0),90)
    def moved(t):
        p=(t,point[1],point[2]) if name=='plate' else (point[0],-t,point[2])
        return oriented.translate(p)
    lo,hi=interval
    assert metal.intersect(moved(lo)).Volume()<1e-6
    previous=lo
    for t in np.linspace(lo,hi,81)[1:]:
        if metal.intersect(moved(float(t))).Volume()>1e-5:
            lo,hi=previous,float(t);break
        previous=float(t)
    else:raise AssertionError('No physical screw head seat found in the factory CAD')
    for i in range(32):
        middle=(lo+hi)/2
        if metal.intersect(moved(middle)).Volume()<1e-6:lo=middle
        else:hi=middle
    t=round(lo,4)-.001
    p=(t,point[1],point[2]) if name=='plate' else (point[0],-t,point[2])
    report[name]=dict(native_head_top=p,direction=direction,total_length_mm=15,
                     nominal_head_diameter_mm=7,nominal_head_height_mm=2.09,
                     seat_interval_mm=[lo,hi],contact_gap_margin_mm=.001,
                     metal_overlap_mm3=metal.intersect(moved(t)).Volume())
    cq.exporters.export(moved(t),str(OUT/f'screw-{name}.step'))
    vertices,faces=moved(t).tessellate(.04,.2)
    arrays[f'{name}-v']=np.array([v.toTuple() for v in vertices]);arrays[f'{name}-f']=np.array(faces,dtype=np.int32)
    print(name,report[name],flush=True)
(OUT/'screw-seats.json').write_text(json.dumps(report,indent=2)+'\n')
np.savez_compressed(OUT/'screw-meshes.npz',**arrays)
