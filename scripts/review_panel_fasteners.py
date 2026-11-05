"""A purchasable side-panel fastening proposal, separate from the v29 model.

FMS 91001201: body D10 x 12.5, transverse M6 axis 7 mm from the
slotted end. Screw and washer envelopes follow the selected DIN products.
No change is made to an earlier cabinet version by importing this module.
"""
import json

import numpy as np
import trimesh as tm

from build_aluminum_corner import cube, cut, overlap_volume, pose
from build_concealed_cabinet import reviewed_structure_with_previous_door, reflected, audit_contacts
from build_frame_joinery import bore
from build_pegboard_cabinet import drill_x, drill_z, right_parts
from build_right_lift import ROOT, export
from build_simple_left_door import AXIS_LEFT

OUT = ROOT / 'outputs/hardware-agreement-v1'


def socket_head_screw(y, z, sign):
    screw = tm.boolean.union([
        drill_z(19, y, z-sign*6, z, 5),
        drill_z(19, y, z, z+sign*45, 3)], engine='manifold')
    # AF5, schematic socket depth 3 mm; no thread helices or tool relief.
    socket = tm.creation.cylinder(radius=5/np.sqrt(3), height=3.2, sections=6)
    socket.apply_translation([19,y,z-sign*4.5])
    return cut(screw,[socket])


def candidate():
    fixed,left,_,joints,_ = reviewed_structure_with_previous_door()
    by_name = {p['name']:p for p in fixed}
    dimensions = []
    for side,prefix,wall_name in [('left','Pegboard','Left-pegboard-18'),
                                  ('right','Right-wall','Right-wall-18')]:
        mirror = (lambda mesh: reflected(mesh)) if side=='right' else (lambda mesh: mesh)
        fills, counterbores = [], {'Bottom':[], 'Top':[]}
        for end,z,base,seat,edge,entry,sign in [
            ('Bottom',820,777.4,779,800,770,1),
            ('Top',1749,1792.6,1791,1769,1800,-1)]:
            for y in (97,426):
                # Reduce the old cylindrical pocket from 15.6 to 14.6 mm.
                # This is a flat-bottom CNC pocket; drill-point depth is not
                # interchangeable with this dimension.
                fills.append(mirror(drill_x(28,y,z,-15.65,-14.6,5.05)))
                # Slotted face X26, far end X13.5; thread axis X19.
                barrel=drill_x(28,y,z,-14.5,-2,5)
                transverse=drill_z(19,y,z-5.1,z+5.1,3.02)
                slit=cube([25.45,y-.55,z-5.1],[26.1,y+.55,z+5.1])
                by_name[f'{prefix}-cross-dowel-{end}-{y}']['mesh']=mirror(cut(barrel,[transverse,slit]))
                by_name[f'{prefix}-M6x45-{end}-{y}']['mesh']=mirror(socket_head_screw(y,base,sign))
                washer=cut(drill_z(19,y,base,seat,9),[
                    drill_z(19,y,min(base,seat)-.1,max(base,seat)+.1,3.2)])
                by_name[f'{prefix}-washer-{end}-{y}']['mesh']=mirror(washer)
                counterbores[end].append(mirror(drill_z(19,y,entry-sign*.1,seat,9.5)))
                bolt_tip=base+sign*45
                engagement=min(abs(bolt_tip-(z-sign*5)),10)
                dimensions.append(dict(side=side,end=end,y_mm=y,
                    barrel_thread_axis_from_slotted_end_mm=7,
                    barrel_slotted_end_recess_from_inner_face_mm=2,
                    barrel_pocket_diameter_mm=10.1,barrel_pocket_flat_depth_mm=14.6,
                    remaining_outer_plywood_mm=3.4,bolt_axis_from_panel_face_mm=9,
                    nut_axis_from_panel_end_mm=20,
                    nominal_shank_overlap_with_barrel_mm=round(engagement,4)))
        by_name[wall_name]['mesh']=tm.boolean.union([by_name[wall_name]['mesh'],*fills],engine='manifold')
        beam_x=4 if side=='left' else 966
        for end,name in [('Bottom',f'Beam-body-side-{beam_x}'),('Top',f'Beam-top-side-{beam_x}')]:
            by_name[name]['mesh']=cut(by_name[name]['mesh'],counterbores[end])
    return fixed,left,dimensions


def main():
    OUT.mkdir(exist_ok=True)
    fixed,left,dimensions=candidate();by_name={p['name']:p for p in fixed}
    checks=dict(status='PROPOSED; NOT USER-APPROVED',fabrication_release=False,
                base_version='cambusa-v29-panel-mount-checkpoint',mounts=dimensions,
                envelopes='Nominal product dimensions; threads, chamfers and slot details simplified',
                poses={},tool_access=[],washer_bearing=[])
    for angle in (0,180):
        bad,threads=audit_contacts(pose(fixed+right_parts(0),left,AXIS_LEFT,angle))
        checks['poses'][angle]=dict(unexpected_contacts=bad,localized_thread_pairs=len(threads))
        assert not bad,bad
    for side,x,prefix,beam_x in [('left',19,'Pegboard',4),('right',981,'Right-wall',966)]:
        for end,seat,head,sign in [('Bottom',779,771.4,-1),('Top',1791,1798.6,1)]:
            beam=by_name[f'Beam-{"body" if end=="Bottom" else "top"}-side-{beam_x}']['mesh']
            for y in (97,426):
                tool=bore([x,y,head],[0,0,sign],0,40,3)
                hits=[p['name'] for p in fixed+left if p['name']!=f'{prefix}-M6x45-{end}-{y}'
                      and overlap_volume(tool,p['mesh'])>.08]
                assert not hits,hits
                # Area actually supported by the flat machined webs, not
                # the entire nominal washer area.
                wafer=cut(drill_z(x,y,seat,seat-sign*.02,9),[
                    drill_z(x,y,seat-.1,seat+.1,3.2)])
                area=overlap_volume(beam,wafer)/.02
                assert area>1,area
                checks['tool_access'].append(dict(side=side,end=end,y=y,hits=hits))
                checks['washer_bearing'].append(dict(side=side,end=end,y=y,
                    supported_area_mm2=round(area,3)))
    window=cube([3,75,769],[35,123,854])
    detail=[]
    for name in ['Left-pegboard-18','Beam-body-side-4','Pegboard-M6x45-Bottom-97',
                 'Pegboard-washer-Bottom-97','Pegboard-cross-dowel-Bottom-97']:
        part=by_name[name]
        mesh=part['mesh'].copy()
        if name in ('Left-pegboard-18','Beam-body-side-4'):
            mesh=tm.boolean.intersection([mesh,window],engine='manifold')
        detail.append(dict(part,mesh=mesh))
    export(OUT/'proposed-panel-joint.glb',detail)
    checks['outside_scope']=['No mechanical strength or tightening torque verification',
        'No claim that advertised inventory is reserved or in the Saint Petersburg shop',
        'No change to the released overview model until the proposal is accepted']
    (OUT/'fit-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    print('8 proposed mounts: no unexpected overlaps; tool approaches and washer support checked.')


if __name__=='__main__':main()
