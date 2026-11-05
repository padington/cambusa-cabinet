from pathlib import Path
import json,traceback
import cadquery as cq
import numpy as np
from types import MethodType
from cq_acis import CadQueryConverter
from blum_acis208 import parse,saved_uv
from cq_acis.model import Vec3,TorusSurfaceEntity,FaceEntity
import math

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/wide-hinge-verification'
report={};arrays={};visual={}
OUT.mkdir(exist_ok=True)
for name in ('blum-71t6650','blum-175h7190'):
    report[name]=[]
    count=7 if name=='blum-71t6650' else 1
    for i in range(count):
        row=dict(body=i)
        try:
            raw=(ROOT/f'outputs/wide-hinge-study/{name}-{i}.sat').read_text()
            model,audit=parse(raw)
            converter=CadQueryConverter(model)
            converter._blum_raw=raw
            converter._saved_surface_pcurve=MethodType(saved_uv,converter)
            source_limits={r['index']:r['saved_scalars'][0] for r in audit if r['type']=='tedge-edge'}
            original=converter._saved_pcurve_tolerance
            def edge_tolerance(self,coedge,saved,placement):
                if coedge is not None and coedge.edge.index in source_limits:
                    allowance=source_limits[coedge.edge.index]
                    return allowance+self.tolerance,dict(edge=coedge.edge.index,coedge=coedge.index,
                        saved_deviation_mm=allowance,model_resolution_mm=self.tolerance,
                        profile='ACIS 20800 exactcur and local TEDGE scalar; projected UV independently bounded')
                if saved is not None:
                    return saved.fit_tolerance+self.tolerance,dict(edge=coedge.edge.index,coedge=coedge.index,
                        saved_uv_fit_mm=saved.fit_tolerance,model_resolution_mm=self.tolerance,
                        profile='ACIS 20800 saved EXPPС on identical spline support; 2D/3D deviation checked')
                return self.tolerance,None
            converter._saved_pcurve_tolerance=MethodType(edge_tolerance,converter)
            def join(self,previous,current,previous_coedge,current_coedge,geometry,placement,limit,loop_index):
                before=self.model.resolve(previous_coedge.edge);after=self.model.resolve(current_coedge.edge)
                end=before.start_vertex if previous_coedge.reversed else before.end_vertex
                start=after.end_vertex if current_coedge.reversed else after.start_vertex
                assert end==start,'UV endpoints must share their original source vertex'
                expected=placement.point_vector(self._vertex_location(end,context='source UV join'))
                points=[geometry.surface.Value(*uv) for uv in (previous,current)]
                deviations=[(Vec3(q.X(),q.Y(),q.Z())-expected).magnitude for q in points]
                gap=points[0].Distance(points[1])
                assert max(*deviations,gap)<=limit,(gap,deviations,limit)
                self.tolerant_pcurve_joins.append(dict(vertex=end.index,loop=loop_index,gap_mm=gap,
                    deviations_to_source_mm=deviations,tolerance_mm=limit,method='original source vertex and local edge/UV fit bound'))
            converter._check_tolerant_join=MethodType(join,converter)
            original_bspline=converter._bspline_face
            def spline_face(self,face,surface,loops,placement):
                result=original_bspline(face,surface,loops,placement)
                if not result.isValid():
                    from OCP.ShapeFix import ShapeFix_Face
                    fixer=ShapeFix_Face(result.wrapped)
                    fixer.SetPrecision(.001001);fixer.SetMaxTolerance(.001001)
                    fixer.Perform()
                    candidate=self.cq.Face(fixer.Face())
                    same_edges=all(any(e.wrapped.IsSame(q.wrapped) for q in candidate.Edges()) for e in result.Edges())
                    print('FACE EDGE IDENTITY',face.index,same_edges,flush=True)
                    print('PLATE FACE HEAL',face.index,result.isValid(),candidate.isValid(),
                          len(result.Edges()),len(candidate.Edges()),result.Area(),candidate.Area(),flush=True)
                    assert candidate.isValid() and same_edges
                    self.blum_face_heals.append(dict(face=face.index,source_3d_edges_unchanged=same_edges,
                        face_count_unchanged=True,area_before_invalid_mm2=result.Area(),area_after_mm2=candidate.Area(),
                        method='ShapeFix_Face UV orientation; same 3D edge identities'))
                    result=candidate
                return result
            converter._bspline_face=MethodType(spline_face,converter)
            original_geometry=converter._closed_analytic_geometry
            def analytic(self,face,surface,placement):
                if isinstance(surface,TorusSurfaceEntity) and abs(surface.major_radius-abs(surface.minor_radius))<1e-10:
                    from cq_acis.cadquery import _TorusGeometry
                    from OCP.Geom import Geom_ToroidalSurface
                    from OCP.gp import gp_Ax3,gp_Dir,gp_Pnt
                    center=placement.point_vector(surface.center)
                    axis=placement.vector(surface.axis).normalized();x=placement.vector(surface.u_direction).normalized();y=axis.cross(x)
                    assert abs(axis.dot(x))<1e-10 and face is not None
                    scale=placement.vector(Vec3(1,0,0)).magnitude
                    major=surface.major_radius*scale;minor=abs(surface.minor_radius)*scale
                    frame=gp_Ax3(gp_Pnt(center.x,center.y,center.z),gp_Dir(axis.x,axis.y,axis.z),gp_Dir(x.x,x.y,x.z))
                    return _TorusGeometry(Geom_ToroidalSurface(frame,major,minor),center,axis,x,y,major,self.tolerance,minor)
                return original_geometry(face,surface,placement)
            converter._closed_analytic_geometry=MethodType(analytic,converter)
            converter.blum_face_heals=[]
            shapes=converter.convert()
            row.update(valid=[s.isValid() for s in shapes],volume=[s.Volume() for s in shapes],decoded=audit,
                       pcurve_checks=converter.pcurve_checks,uv_face_fixes=converter.blum_face_heals,
                       source_face_count=sum(isinstance(e,FaceEntity) for e in model.entities),
                       converted_face_count=len(shapes[0].Faces()))
            assert row['source_face_count']==row['converted_face_count']
            cq.exporters.export(shapes[0],str(OUT/f'{name}-{i}.step'))
            vertices,faces=shapes[0].tessellate(.025,.10)
            arrays[f'{name}-{i}-v']=np.array([v.toTuple() for v in vertices])
            arrays[f'{name}-{i}-f']=np.array(faces,dtype=np.int32)
            vertices,faces=shapes[0].tessellate(.1,.30)
            visual[f'{name}-{i}-v']=np.array([v.toTuple() for v in vertices])
            visual[f'{name}-{i}-f']=np.array(faces,dtype=np.int32)
        except Exception as error:
            chain=[];e=error
            while e is not None:chain.append(f'{type(e).__name__}: {e}');e=e.__cause__
            row['errors']=chain
            traceback.print_exc(limit=3)
        report[name].append(row);print(name,i,{k:v for k,v in row.items() if k not in ('decoded','pcurve_checks')},flush=True)
(OUT/'explicit-conversion.json').write_text(json.dumps(report,indent=2)+'\n')
assert len(arrays)==16 and all('errors' not in row for rows in report.values() for row in rows)
np.savez_compressed(OUT/'factory-meshes.npz',**arrays)
np.savez_compressed(OUT/'factory-visual-meshes.npz',**visual)
