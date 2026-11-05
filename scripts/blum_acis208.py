"""Narrow decoder of explicit ACIS 20800 records present in the Blum files.

Does not fit, invent or omit geometry. Legacy knot endpoint multiplicities
are raised by one to express exactly the same clamped spline in OCCT.
The original source records and tolerant scalars are preserved in the audit.
"""
from dataclasses import replace
from contextlib import contextmanager
import math
import cq_acis.entities as dec
from cq_acis import parse_sat_graph
from cq_acis.model import AcisModel,BSplineCurveEntity,BSplineSurfaceEntity,Vec3,ParameterRange


@contextmanager
def inherited_references():
    original=dec._EntityReader.read_ref
    def read(self,expected_type=None):
        if expected_type not in ('vertex','edge','coedge'):return original(self,expected_type)
        ref=original(self,None);target=self.graph.resolve(ref)
        if target is not None and target.type_name not in (expected_type,f't{expected_type}-{expected_type}'):
            raise self._error('Unexpected topology inheritance')
        return ref
    dec._EntityReader.read_ref=read
    try:yield
    finally:dec._EntityReader.read_ref=original


def curve(raw):
    v=raw.values
    assert v[1:5]==('forward','{','exactcur','full')
    assert v[5] in ('nurbs','nubs') and v[7]=='open'
    rational=v[5]=='nurbs';degree=int(v[6]);n=int(v[8]);pos=9
    knots=[];mult=[]
    for i in range(n):
        knots.append(float(v[pos]));mult.append(int(v[pos+1])+(i in (0,n-1)));pos+=2
    count=sum(mult)-degree-1
    poles=[];weights=[]
    for i in range(count):
        poles.append(Vec3(*(float(x) for x in v[pos:pos+3])));pos+=3
        weights.append(float(v[pos]) if rational else 1.)
        if rational:pos+=1
    tail=v[pos:]
    # No support or procedural equation is being discarded here. Exact curves
    # in these files have two null support surfaces and two null UV splines.
    assert tail[:5]==(0,'null_surface','null_surface','nullbs','nullbs'),tail
    assert tail[5:8]==('I','I',0),tail
    rest=tail[8:];number=int(rest[0]);rest=rest[1+number:]
    assert rest==(0,'F',1,'F',0,'}','I','I'),rest
    result=BSplineCurveEntity(raw,v[0],degree,tuple(knots),tuple(mult),tuple(poles),tuple(weights),
                              ParameterRange(knots[0],knots[-1]),0.)
    result.validate()
    return result


def parse(raw):
    graph=parse_sat_graph(raw);assert graph.header.save_version==20800
    records=[];audit=[];definitions=[]
    for entity in graph.entities:
        for i,value in enumerate(entity.values):
            if value=='{' and entity.values[i+1]!='ref':definitions.append((entity,i))
    with inherited_references():
        for e in graph.entities:
            if e.type_name=='intcurve-curve':
                decoded=curve(e)
                audit.append(dict(index=e.index,type=e.type_name,degree=decoded.degree,poles=len(decoded.poles)))
            elif e.type_name=='spline-surface':
                if e.values[3]=='ref':
                    source,pos=definitions[int(e.values[4])]
                else:source,pos=e,2
                decoded=surface(e,source,pos)
                audit.append(dict(index=e.index,type=e.type_name,source_entity=source.index,
                    source_block_start=pos,u_count=decoded.u_count,v_count=decoded.v_count))
            elif e.type_name in ('tvertex-vertex','tedge-edge','tcoedge-coedge'):
                count=2 if e.type_name=='tcoedge-coedge' else 1
                expected={'tvertex-vertex':4,'tedge-edge':10,'tcoedge-coedge':10}[e.type_name]
                assert len(e.values)==expected
                fields=e.values[-count:]
                if count==1:assert 0<=float(fields[0])<.001
                else:assert float(fields[0])<float(fields[1])
                base=e.type_name.split('-')[-1]
                # Geometry stays original. Source dialect extensions are audited
                # separately from the base topological references.
                base_raw=replace(e,type_name=base,values=e.values[:-count])
                decoded=dec.decode_entity(graph,base_raw)
                audit.append(dict(index=e.index,type=e.type_name,saved_scalars=[float(x) for x in fields]))
            else:decoded=dec.decode_entity(graph,e)
            records.append(decoded)
    model=AcisModel(dec.SatModel(graph,()).metadata,tuple(records))
    return model,audit


def surface(raw,source,start):
    v=source.values;pos=start+1
    assert v[pos:pos+3]==('exactsur','full','nurbs');pos+=3
    ud,vd=map(int,v[pos:pos+2]);pos+=2
    assert v[pos:pos+5]==('both','open','open','high','none');pos+=5
    un,vn=map(int,v[pos:pos+2]);pos+=2
    def knots(n):
        nonlocal pos
        k=[];m=[]
        for i in range(n):
            k.append(float(v[pos]));m.append(int(v[pos+1])+(i in (0,n-1)));pos+=2
        return tuple(k),tuple(m)
    uk,um=knots(un);vk,vm=knots(vn)
    uc=sum(um)-ud-1;vc=sum(vm)-vd-1;poles=[];weights=[]
    for i in range(uc*vc):
        poles.append(Vec3(*(float(x) for x in v[pos:pos+3])));weights.append(float(v[pos+3]));pos+=4
    end=pos
    while v[end]!='}':end+=1
    tail=v[pos:end]
    assert tail==(0,0,len(uk)-2,*uk[1:-1],0,0,len(vk)-2,*vk[1:-1],0,'F',1,'F',0,'F',1,'F',0)
    result=BSplineSurfaceEntity(raw,raw.values[0],ud,vd,uk,vk,um,vm,uc,vc,tuple(poles),tuple(weights),
                               False,None,None,0.)
    result.validate()
    return result


def saved_uv(converter,coedge,geometry,first,last,reverse_3d):
    from types import SimpleNamespace
    from dataclasses import fields
    from cq_acis._supported_curves import array
    from OCP.Geom2d import Geom2d_BSplineCurve
    from OCP.TColgp import TColgp_Array1OfPnt2d
    from OCP.TColStd import TColStd_Array1OfReal,TColStd_Array1OfInteger
    from OCP.gp import gp_Pnt2d
    if coedge is None or coedge.pcurve.is_null or not hasattr(geometry,'source_surface'):return None,None
    raw=converter.model.resolve(coedge.pcurve);v=raw.values
    assert v[3:6]==('{','exppc','nubs') and v[7]=='open'
    degree=int(v[6]);n=int(v[8]);pos=9;knots=[];mult=[]
    for i in range(n):
        knots.append(float(v[pos]));mult.append(int(v[pos+1])+(i in (0,n-1)));pos+=2
    count=sum(mult)-degree-1
    poles=[tuple(float(x) for x in v[pos+2*i:pos+2*i+2]) for i in range(count)];pos+=2*count
    fit=float(v[pos]);assert 0<=fit<=.001;pos+=1
    assert v[pos:pos+2]==('spline','forward');pos+=2
    assert v[pos]=='{'
    graph=parse_sat_graph(converter._blum_raw)
    definitions=[(e,i) for e in graph.entities for i,x in enumerate(e.values) if x=='{' and e.values[i+1]!='ref']
    if v[pos+1]=='ref':source,start=definitions[int(v[pos+2])]
    else:source,start=raw,pos
    associated=surface(geometry.source_geometry.raw,source,start)
    assert all(getattr(associated,f.name)==getattr(geometry.source_geometry,f.name)
               for f in fields(associated) if f.name not in ('raw','pattern'))
    reversed_=v[2]=='reversed';assert v[2] in ('forward','reversed')
    if reversed_ ^ reverse_3d:
        poles=poles[::-1];knots=[-k for k in knots[::-1]];mult=mult[::-1]
    mapped=[first+(k-knots[0])/(knots[-1]-knots[0])*(last-first) for k in knots]
    curve=Geom2d_BSplineCurve(array([gp_Pnt2d(*p) for p in poles],TColgp_Array1OfPnt2d),
        array(mapped,TColStd_Array1OfReal),array(mult,TColStd_Array1OfInteger),degree,False)
    view=SimpleNamespace(raw=raw,fit_tolerance=fit,degree=degree,reversed=reversed_,
                         support_reversed=False,support=SimpleNamespace(index=geometry.source_surface))
    return curve,view
