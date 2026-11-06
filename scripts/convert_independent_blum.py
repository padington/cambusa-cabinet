"""Convert the independently sourced Demos binary CAD, preserving source faces."""
from pathlib import Path
import json,traceback
import cadquery as cq
import numpy as np
from types import MethodType
from cq_acis import CadQueryConverter
from blum_sab208 import parse
from blum_acis208 import saved_uv
from cq_acis.model import Vec3,TorusSurfaceEntity,FaceEntity
import math

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/blum-independent-v33'
report={};arrays={};visual={}
OUT.mkdir(exist_ok=True)
for name in ('blum-71t6650',):
    report[name]=[]
    count=7 if name=='blum-71t6650' else 1
    for i in range(count):
        row=dict(body=i,conversion_join_tolerance_mm=1e-5)
        try:
            raw=(ROOT/f'inputs/supplier-cad/demos-71t6650/body-{i}.sab').read_bytes()
            model,audit=parse(raw)
            converter=CadQueryConverter(model)
            converter.tolerance=1e-5  # 0.01 micron numerical joins; factory surfaces remain unchanged.
            converter._blum_raw=raw
            converter._saved_surface_pcurve=MethodType(saved_uv,converter)
            source_limits={r['index']:r['saved_scalars'][0] for r in audit if r['type']=='tedge-edge'}
            original=converter._saved_pcurve_tolerance
            def edge_tolerance(self,coedge,saved,placement):
                if coedge is not None and coedge.edge.index in source_limits:
                    allowance=source_limits[coedge.edge.index]
                    return allowance+self.tolerance,dict(edge=coedge.edge.index,coedge=coedge.index,
                        saved_deviation_mm=allowance,conversion_join_tolerance_mm=self.tolerance,
                        profile='ACIS 20800 exactcur and local TEDGE scalar; projected UV independently bounded')
                if saved is not None:
                    return saved.fit_tolerance+self.tolerance,dict(edge=coedge.edge.index,coedge=coedge.index,
                        saved_uv_fit_mm=saved.fit_tolerance,conversion_join_tolerance_mm=self.tolerance,
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
                if isinstance(surface,TorusSurfaceEntity) and 0 < surface.major_radius <= abs(surface.minor_radius):
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
            # Kernel vertex joins may use only tolerances declared by this source.
            from OCP.BRep import BRep_Builder
            original_edge=converter._edge
            vertex_limits={r['index']:r['saved_scalars'][0] for r in audit if r['type']=='tvertex-vertex'}
            converter.source_vertex_tolerance_checks=[]
            def qualified_edge(self,coedge,placement):
                result=original_edge(coedge,placement)
                edge=self.model.resolve(coedge.edge)
                candidates=[]
                for ref in (edge.start_vertex,edge.end_vertex):
                    point=placement.point_vector(self._vertex_location(ref,context='source join tolerance'))
                    bound=max(vertex_limits.get(ref.index,0),source_limits.get(edge.index,0))+self.tolerance
                    candidates.append((point,bound,ref.index))
                builder=BRep_Builder()
                for v in result.Vertices():
                    point,bound,index=min(candidates,key=lambda row:(Vec3(*v.toTuple())-row[0]).magnitude)
                    distance=(Vec3(*v.toTuple())-point).magnitude
                    assert distance<=bound,(edge.index,index,distance,bound)
                    builder.UpdateVertex(v.wrapped,bound)
                    self.source_vertex_tolerance_checks.append(dict(edge=edge.index,vertex=index,distance_mm=distance,source_bound_plus_resolution_mm=bound))
                return result
            converter._edge=MethodType(qualified_edge,converter)
            previous_pcurve_tolerance=converter._saved_pcurve_tolerance
            def vertex_aware_tolerance(self,coedge,saved,placement):
                old,detail=previous_pcurve_tolerance(coedge,saved,placement)
                if coedge is not None:
                    edge=self.model.resolve(coedge.edge)
                    old=max(old,max(vertex_limits.get(v.index,0) for v in (edge.start_vertex,edge.end_vertex))+self.tolerance)
                return old,detail
            converter._saved_pcurve_tolerance=MethodType(vertex_aware_tolerance,converter)
            # Build every plane on its declared factory support, not a plane
            # inferred from approximately coincident tolerant wire vertices.
            original_plane=converter._plane_face
            def explicit_plane(self,face,loops,placement):
                try:return original_plane(face,loops,placement)
                except Exception:pass
                from cq_acis._supported_curves import support_geometry
                from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
                from OCP.ShapeFix import ShapeFix_Face
                geometry=support_geometry(self,self._resolve_geometry(face.surface),placement)
                wires=[self._wire(loop,placement,geometry) for loop in loops]
                builder=BRepBuilderAPI_MakeFace(geometry.surface,wires[0].wrapped,True)
                for w in wires[1:]:builder.Add(w.wrapped)
                result=self.cq.Face(builder.Face())
                fixer=ShapeFix_Face(result.wrapped)
                if fixer.FixOrientation():
                    fixed=self.cq.Face(fixer.Face())
                    assert len(fixed.Edges())==len(result.Edges())
                    assert all(any(e.wrapped.IsSame(f.wrapped) for f in fixed.Edges()) for e in result.Edges())
                    result=fixed
                return self._reverse_face(result) if face.reversed else result
            converter._plane_face=MethodType(explicit_plane,converter)
            original_closed=converter._closed_analytic_face
            def bounded_closed(self,face,surface,loops,placement):
                result=original_closed(face,surface,loops,placement)
                if not result.isValid():
                    from OCP.ShapeFix import ShapeFix_Face
                    fixer=ShapeFix_Face(result.wrapped);fixer.SetPrecision(self.tolerance);fixer.Perform()
                    fixed=self.cq.Face(fixer.Face())
                    same=(len(fixed.Edges())==len(result.Edges()) and
                        all(any(e.wrapped.IsSame(f.wrapped) for f in fixed.Edges()) for e in result.Edges()))
                    assert same and fixed.isValid(),(face.index,same,fixed.isValid())
                    self.blum_face_heals.append(dict(face=face.index,source_edges_unchanged=True,method='UV chart fix on original analytic support'))
                    result=fixed
                return result
            converter._closed_analytic_face=MethodType(bounded_closed,converter)
            converter.blum_face_heals=[]
            shapes=converter.convert()
            row.update(valid=[s.isValid() for s in shapes],volume=[s.Volume() for s in shapes],decoded=audit,
                       pcurve_checks=converter.pcurve_checks,uv_face_fixes=converter.blum_face_heals,vertex_join_checks=converter.source_vertex_tolerance_checks,
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
        report[name].append(row);print(name,i,{k:v for k,v in row.items() if k not in ('decoded','pcurve_checks','vertex_join_checks')},flush=True)
(OUT/'explicit-conversion.json').write_text(json.dumps(report,indent=2)+'\n')
assert len(arrays)==14 and all('errors' not in row for rows in report.values() for row in rows)
np.savez_compressed(OUT/'factory-meshes.npz',**arrays)
np.savez_compressed(OUT/'factory-visual-meshes.npz',**visual)
