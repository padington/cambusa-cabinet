"""1:1 millimetre DXFs; rear door view is explicitly mirrored.

Hinge node operations plus retained left-panel machining from v31/24 mm study.
Depths are layer names and a separate operation list, not guessed from circles.
"""
import csv,json,hashlib
from pathlib import Path
import ezdxf

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/cambusa-v32-hinge-node'
FOLDER=OUT/'machining';FOLDER.mkdir(exist_ok=True)
operations=[]
def drawing(name,w,h,note):
    doc=ezdxf.new('R2010');doc.units=ezdxf.units.MM;ms=doc.modelspace()
    doc.layers.new('OUTLINE',dxfattribs={'color':7});doc.layers.new('NOTES',dxfattribs={'color':8})
    ms.add_lwpolyline([(0,0),(w,0),(w,h),(0,h)],close=True,dxfattribs={'layer':'OUTLINE'})
    ms.add_text(note,dxfattribs={'height':4,'insert':(0,h+12),'layer':'NOTES'})
    return doc,ms
def circle(doc,ms,name,x,y,d,depth,part,face):
    layer=f'{name}_D{d:g}_Z{depth:g}'.replace('.','p')
    if layer not in doc.layers:doc.layers.new(layer,dxfattribs={'color':1 if name=='CUP' else 3})
    ms.add_circle((x,y),d/2,dxfattribs={'layer':layer})
    operations.append([part,face,name,x,y,d,depth])
def rounded(doc,ms,x0,y0,x1,y1,r,layer):
    if layer not in doc.layers:doc.layers.new(layer,dxfattribs={'color':5})
    b=2**.5-1
    points=[(x0+r,y0,0),(x1-r,y0,b),(x1,y0+r,0),(x1,y1-r,b),
            (x1-r,y1,0),(x0+r,y1,b),(x0,y1-r,0),(x0,y0+r,b)]
    ms.add_lwpolyline(points,format='xyb',close=True,dxfattribs={'layer':layer})
doc,ms=drawing('door-back',452,964,'DOOR BACK VIEW. HINGE EDGE = RIGHT X452. ALL DEPTHS FROM BACK.')
for v in (90,482,874):
    circle(doc,ms,'CUP',429,v,35.2,11.2,'door-18','back; hinge edge right')
    for z in (v-22.5,v+22.5):circle(doc,ms,'PILOT',419.5,z,2.7,8,'door-18','back; hinge edge right')
    rounded(doc,ms,442.5,v-12.5,455,v+12.5,3,'RELIEF_DEPTH3p2_INTERNAL_R3_OPEN_EDGE')
    operations.append(['door-18','back; hinge edge right','RELIEF_WIDTH9.5_HEIGHT25_R3',442.5,v,9.5,3.2])
doc.saveas(FOLDER/'door-back.dxf')
doc,ms=drawing('door-front',452,964,'DOOR FRONT VIEW. HINGE EDGE = LEFT X0. GRIP DEPTH12 FROM FRONT.')
doc.layers.new('GRIP_DEPTH12_R9',dxfattribs={'color':5})
ms.add_lwpolyline([(425,447,0),(425,519,-1),(443,519,0),(443,447,-1)],format='xyb',close=True,dxfattribs={'layer':'GRIP_DEPTH12_R9'})
doc.saveas(FOLDER/'door-front.dxf')
operations.append(['door-18','front; hinge edge left','GRIP_WIDTH18_HEIGHT90_R9',434,483,18,12])
doc,ms=drawing('side-inner',416,969,'LEFT SIDE INNER FACE. X FROM FRONT EDGE. Y FROM BOTTOM. THICKNESS24.')
for v in (90,482,874):
    for z in (v+3-16,v+3+16):circle(doc,ms,'HINGE_PILOT',26,z,2.7,8,'side-24','inner')
for u in (96.5,346.5):
    for v in (338,658):circle(doc,ms,'SHELF_PIN',u,v,6.06,10.3,'side-24','inner')
for u in (43.5,372.5):
    for v in (20,949):circle(doc,ms,'CROSS_DOWEL_ACCESS',u,v,10.1,20.6,'side-24','inner')
doc.saveas(FOLDER/'side-inner.dxf')
doc,ms=drawing('side-outer',416,969,'LEFT SIDE OUTER VIEW. FRONT EDGE RIGHT X416. BLIND PEG HOLES DEPTH16. NO BREAKTHROUGH.')
for i in range(8):
    for j in range(19):circle(doc,ms,'PEG',416-(33+50*i),34.5+50*j,12,16,'side-24','outer; front edge right')
doc.saveas(FOLDER/'side-outer.dxf')
for end in ('bottom','top'):
    doc,ms=drawing(f'side-{end}',416,24,f'LEFT SIDE {end.upper()} EDGE. X FROM FRONT, Y FROM OUTER FACE. DRILL25 INTO PANEL.')
    for u in (43.5,372.5):circle(doc,ms,'EDGE_BOLT',u,9,6.6,25,'side-24',end+' edge')
    doc.saveas(FOLDER/f'side-{end}-edge.dxf')
with (FOLDER/'operations.csv').open('w',newline='') as f:
    w=csv.writer(f,lineterminator='\n');w.writerow(['part','face_datum','operation','drawing_x_mm','drawing_y_mm','diameter_or_width_mm','depth_mm']);w.writerows(operations)
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in FOLDER.glob('*.dxf')}
for p in FOLDER.glob('*.dxf'):
    doc=ezdxf.readfile(p);assert doc.units==ezdxf.units.MM
    assert len(doc.audit().errors)==0
(FOLDER/'manifest.json').write_text(json.dumps(dict(units='mm',dxf_validation='read back and audited',files=manifest,operations=len(operations)),indent=2)+'\n')
print('DXF files',len(manifest),'machining records',len(operations))
