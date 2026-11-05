"""Six-bar linkage of Blum 71T6650, with pivots extracted from factory SAT.

Rigid bodies 0/6 are fixed; 1=P-B, 2=B-C-D, 3=Q-C-E,
4=E-F, 5=D-F (cup). No 110-degree motion is extrapolated.
"""
import math
from pathlib import Path
import json
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def rotation(a):
    c,s=math.cos(a),math.sin(a)
    return np.array([[c,-s],[s,c]])


def branch(a,b,p):
    u,v=b-a,p-a
    return 1 if u[0]*v[1]-u[1]*v[0]>0 else -1


def intersection(a,ra,b,rb,sign):
    span=b-a;d=np.linalg.norm(span)
    k=(ra*ra-rb*rb+d*d)/(2*d)
    h2=ra*ra-k*k
    if h2<-.000001:raise ValueError('Linkage beyond its circle-intersection domain')
    u=span/d
    return a+k*u+sign*math.sqrt(max(0,h2))*np.array([-u[1],u[0]])


def angle(old,new):
    return math.atan2(old[0]*new[1]-old[1]*new[0],np.dot(old,new))


class SixBar:
    def __init__(self,points):
        self.points={k:np.array(v,float) for k,v in points.items()}
        p=self.points
        self.bc=np.linalg.norm(p['C']-p['B']);self.qc=np.linalg.norm(p['C']-p['Q'])
        self.df=np.linalg.norm(p['F']-p['D']);self.ef=np.linalg.norm(p['F']-p['E'])
        self.c_sign=branch(p['B'],p['Q'],p['C']);self.f_sign=branch(p['D'],p['E'],p['F'])

    def state(self,phi):
        p=self.points
        B=p['P']+rotation(phi)@(p['B']-p['P'])
        C=intersection(B,self.bc,p['Q'],self.qc,self.c_sign)
        a2=angle(p['C']-p['B'],C-B);a3=angle(p['C']-p['Q'],C-p['Q'])
        D=B+rotation(a2)@(p['D']-p['B'])
        E=p['Q']+rotation(a3)@(p['E']-p['Q'])
        F=intersection(D,self.df,E,self.ef,self.f_sign)
        a4=angle(p['F']-p['E'],F-E);a5=angle(p['F']-p['D'],F-D)
        return dict(points={**p,'B':B,'C':C,'D':D,'E':E,'F':F},angles={0:0,1:phi,2:a2,3:a3,4:a4,5:a5,6:0})

    def opening(self,degrees):
        """Inverse on the continuous opening branch; the product stop is 170°.

        No wrapping past the catalogue stop or alternate assembly branch.
        """
        if not 0<=degrees<=170:raise ValueError('71T6650 catalogue range is 0–170 degrees')
        lo,hi=0.0,math.radians(125)
        assert math.degrees(self.state(hi)['angles'][5])>170
        target=math.radians(degrees)
        for _ in range(52):
            middle=(lo+hi)/2
            if self.state(middle)['angles'][5]<target:lo=middle
            else:hi=middle
        return self.state((lo+hi)/2)

    def transform(self,body,degrees,center_z=0,offset=(43,79.5)):
        """Transform closed world meshes, including a door fixed to cup body 5."""
        state=self.opening(degrees)
        return self.transform_state(body,state,offset)

    def transform_state(self,body,state,offset=(43,79.5)):
        """Same placement for a supplied six-bar state (e.g. a uniform phi grid)."""
        origin={1:'P',2:'B',3:'Q',4:'E',5:'D'}.get(body)
        t=np.eye(4)
        if origin is None:return t
        old=np.asarray(offset)+self.points[origin]*[-1,1]
        new=np.asarray(offset)+state['points'][origin]*[-1,1]
        r=rotation(-state['angles'][body])
        t[:2,:2]=r;t[:2,3]=new-r@old
        return t

    def residual(self,degrees):
        s=self.opening(degrees);p=s['points'];old=self.points
        pairs=('PB','BC','BD','CD','QC','QE','CE','EF','DF')
        return max(abs(np.linalg.norm(p[a]-p[b])-np.linalg.norm(old[a]-old[b])) for a,b in pairs)


def extract():
    import ezdxf
    from ezdxf.acis import api,sat
    document=ezdxf.readfile(ROOT/'inputs/supplier-cad/blum-71t6650.dxf')
    axes=[]
    for solid in document.modelspace().query('3DSOLID'):
        body,=api.load_dxf(solid);matrix=body.transform.matrix;circles=[]
        for e in sat.parse_sat(solid.sat).entities:
            if e.name!='cone-surface':continue
            v=np.array([float(x) for x in e.data[1:11]])
            center=np.array(matrix.transform(v[:3]));normal=np.array(matrix.transform_direction(v[3:6]))
            if abs(normal[2])>.999:circles.append(center[:2])
        axes.append(circles)
    point_specs={'P':(0,1,[-25.177,.91]),'Q':(0,3,[-18.675,-39.582]),
                 'B':(1,2,[-35.224,21.488]),'C':(2,3,[-28.208,-20.909]),
                 'D':(2,5,[-4.5,-41.7]),'E':(3,4,[-59.202,-8.78]),'F':(4,5,[-32.5,-34.7])}
    points={}
    for name,(first,second,approx) in point_specs.items():
        a=min(axes[first],key=lambda v:np.linalg.norm(v-approx))
        b=min(axes[second],key=lambda v:np.linalg.norm(v-approx))
        assert np.linalg.norm(a-b)<.00001,(name,a,b)
        assert np.linalg.norm(a-approx)<.01
        points[name]=((a+b)/2).tolist()
    return points


if __name__=='__main__':
    points=extract();link=SixBar(points)
    output=dict(points=points,scan={})
    for direction in (1,-1):
        samples=[]
        for degrees in np.arange(0,180,.25):
            try:s=link.state(math.radians(float(direction*degrees)))
            except ValueError:break
            samples.append([direction*float(degrees),math.degrees(s['angles'][5])])
        output['scan'][direction]=samples
        print('direction',direction,'last',samples[-1], 'cup range',min(p[1] for p in samples),max(p[1] for p in samples),flush=True)
    folder=ROOT/'outputs/wide-hinge-study';folder.mkdir(exist_ok=True)
    (folder/'linkage.json').write_text(json.dumps(output,indent=2)+'\n')
