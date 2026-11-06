from pathlib import Path
import numpy as np
from scipy.interpolate import BSpline
from cq_acis.model import *
from blum_sab208 import parse
import json
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'outputs/blum-independent-v33'
models={i:parse((ROOT/f'inputs/supplier-cad/demos-71t6650/body-{i}.sab').read_bytes())[0] for i in (2,4)}
def v(a):return np.array([a.x,a.y,a.z])
def chain(m,ref,field):
 result=[]
 while not ref.is_null:
  e=m.resolve(ref);result.append(e);ref=getattr(e,field)
 return result

def edgepoints(m,e,n=4097):
 c=m.resolve(e.curve);t=np.linspace(e.start_parameter,e.end_parameter,n)*(-1 if e.reversed else 1)
 if isinstance(c,StraightCurveEntity):p=v(c.origin)[None,:]+t[:,None]*v(c.direction)
 elif isinstance(c,EllipseCurveEntity):
  a=v(c.major_axis);b=np.cross(v(c.normal)/np.linalg.norm(v(c.normal)),a)*c.ratio
  p=v(c.center)[None,:]+np.cos(t[:,None])*a+np.sin(t[:,None])*b
 elif isinstance(c,BSplineCurveEntity):
  k=np.repeat(c.knots,c.multiplicities);w=np.array(c.weights);xyz=np.array([v(q) for q in c.poles]);p=BSpline(k,xyz*w[:,None],c.degree)(t)/BSpline(k,w,c.degree)(t)[:,None]
 else:raise AssertionError(type(c))
 a=v(m.resolve(m.resolve(e.start_vertex).point).location);b=v(m.resolve(m.resolve(e.end_vertex).point).location)
 error=max(np.linalg.norm(p[0]-a),np.linalg.norm(p[-1]-b));assert error<.001,(e.index,error)
 return p

def loop_points(m,loop):
 result=[];first=loop.coedge;ref=first
 while True:
  co=m.resolve(ref);p=edgepoints(m,m.resolve(co.edge))
  if co.reversed:p=p[::-1]
  result.extend(p);ref=co.next_coedge
  if ref==first:break
 return np.array(result)

def prepare(m):
 out=[]
 for e in m.entities:
  if isinstance(e,FaceEntity):
   s=m.resolve(e.surface);loops=chain(m,e.loop,'next_loop');polys=[loop_points(m,l) for l in loops];points=np.vstack(polys)
   out.append((e,s,polys,points.min(axis=0),points.max(axis=0)))
 return out
faces={i:prepare(m) for i,m in models.items()}
def ray(p,faces):
 hits=[];uncertain=[]
 for e,s,loops,lo,hi in faces:
  if isinstance(s,PlaneSurfaceEntity):
   normal=v(s.normal)
   if abs(normal[2])<1e-12:continue
   t=np.dot(normal,v(s.origin)-p)/normal[2]
   if t<=1e-8:continue
   q=p+np.array([0,0,t]);drop=np.argmax(np.abs(normal));axes=[j for j in range(3) if j!=drop]
   inside=False;distance=1e9
   for poly in loops:
    a=poly[:,axes];b=np.roll(a,-1,axis=0);test=q[axes]
    select=(a[:,1]>test[1])!=(b[:,1]>test[1])
    crossings=a[select,0]+(test[1]-a[select,1])*(b[select,0]-a[select,0])/(b[select,1]-a[select,1])
    inside^=np.count_nonzero(test[0]<crossings)%2==1
    ab=b-a;den=(ab*ab).sum(axis=1);den[den<1e-20]=1
    proj=np.clip(((test-a)*ab).sum(axis=1)/den,0,1)
    distance=min(distance,float(np.linalg.norm(a+proj[:,None]*ab-test,axis=1).min()))
   if inside:hits.append((t,e.index,distance))
  elif isinstance(s,ConeSurfaceEntity):
   assert abs(s.ratio)==1
   a=v(s.axis)*s.cos_half_angle;a/=np.linalg.norm(a);u=p-v(s.center);d=np.array([0.,0.,1.]);ua=u@a;da=d@a;ur=u-ua*a;dr=d-da*a
   k=s.sin_half_angle/abs(s.cos_half_angle);r=np.linalg.norm(v(s.major_axis))+k*ua;rk=k*da
   coeff=[dr@dr-rk*rk,2*(ur@dr-r*rk),ur@ur-r*r]
   if abs(coeff[0])<1e-12:
    roots=[] if abs(coeff[1])<1e-12 else [-coeff[2]/coeff[1]]
   else:roots=np.roots(coeff)
   for t in roots:
    if abs(complex(t).imag)>1e-8 or float(complex(t).real)<=1e-8:continue
    t=float(complex(t).real);q=p+np.array([0,0,t])
    if np.all(q>=lo-.001) and np.all(q<=hi+.001):uncertain.append((t,e.index))
  else:raise AssertionError(type(s))
 return dict(inside=len(hits)%2==1,hits=hits,curved_possible=uncertain)
center=np.array([-32.54508578,-20.78081606,0.0])
result=[]
for p in [center]+[center+np.array([x,y,z]) for x in (-.1,.1) for y in (-.1,.1) for z in (-.1,.1)]:
 rows={i:ray(p,ff) for i,ff in faces.items()}
 assert all(r['inside'] and not r['curved_possible'] for r in rows.values())
 assert min(h[2] for r in rows.values() for h in r['hits'])>.08
 result.append(dict(point=p.tolist(),bodies=rows))
report=dict(passed=True,method='Independent +Z ray parity from original binary source planes and exact source edge evaluations; no OCCT topology or Boolean classification',
 scope='Confirms source overlap of bodies 2 and 4 at nine interior witness points, not the physical hinge mechanism',
 curve_samples_per_edge=4097,minimum_hit_distance_to_trim_mm=min(h[2] for row in result for r in row['bodies'].values() for h in r['hits']),witnesses=result)
(P/'source-ray-check.json').write_text(json.dumps(report,indent=2)+'\n')
print('Independent source overlap confirmed at',len(result),'points; minimum trim margin',report['minimum_hit_distance_to_trim_mm'])
