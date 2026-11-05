"""v29 structural checkpoint and inspectable 18 mm side-panel connections.

Uses the reviewed v28 hinge, not the unresolved concealed-hinge candidate.
"""
import argparse
import base64
import csv
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import trimesh as tm

from build_aluminum_corner import cube, cut, overlap_volume
from build_concealed_cabinet import OUT, reviewed_structure_with_previous_door, audit_contacts
from build_frame_joinery import bore, cad_parts
from build_pegboard_cabinet import right_parts, right_leaf, slot_end
from build_right_lift import ROOT, SECTIONS, audit_leaf, export
from build_simple_left_door import AXIS_LEFT, detail_parts, door_sweep, hinge_motion
from build_aluminum_corner import pose


def details(fixed, left):
    by_name = {p['name']:p for p in fixed}

    def clip(part, low, high):
        mesh = tm.boolean.intersection([part['mesh'], cube(low, high)], engine='manifold')
        return dict(part, mesh=mesh)

    wood = by_name['Left-pegboard-18']
    beam = by_name['Beam-body-side-4']
    hardware = [by_name[f'Pegboard-{kind}-Bottom-97']
                for kind in ('M6x45', 'washer', 'cross-dowel')]
    mounts = [clip(wood, [3,75,799.9], [35,123,854]),
              clip(beam, [3,75,769.9], [35,123,800.1]), *hardware]
    section = [clip(p, [3,97,760], [35,123,855]) if i < 2 else p
               for i,p in enumerate(mounts)]
    # Offsets expose the blind pocket and transverse nut; exploded views are
    # explanatory, not simulated installation paths.
    deltas = ([0,0,32], [0,0,0], [0,0,-24], [0,0,-12], [23,0,32])
    mounts = [dict(p, delta=delta) for p,delta in zip(mounts,deltas)]
    section = [dict(p, delta=delta) for p,delta in zip(section,deltas)]
    corner = []
    for p in fixed:
        name=p['name']
        if name in ('Post-4-23', 'Beam-top-side-4', 'Beam-top-front'):
            corner.append(clip(p, [3,22,1710], [94,113,1801]))
        elif name.startswith(('Cube-2069-4-23', 'Cube-bolt-M8x25-4-23', 'Cube-cap-4-23')):
            corner.append(p)
    foot = [clip(by_name['Post-4-23'], [3,22,43.9], [35,54,123])]
    foot += [p for p in fixed if p['name'] in ('Levelling-foot-D49M8H30-4-23',
                                              'Foot-locknut-M8-4-23')]
    return dict(mount=mounts, section=section, corner=corner, foot=foot,
                hinge=detail_parts(fixed,left))


def payload(fixed, left, detail, joints):
    geo, mesh_keys = {}, {}
    native_connectors=cad_parts()
    by_joint={j['id']:j for j in joints}

    def encode(part, top=None, moving=False):
        if part['name'].startswith('RSI-') and '::' in part['name']:
            sku,jid,number=part['name'].split('::');sku=sku.split('-')[1]
            joint=by_joint[jid];access,along=joint['access'],joint['along']
            axes=np.column_stack((np.cross(access,along),access,along))
            origin=joint['point']-.25*along if sku=='5212' and number=='1' else joint['point']
            encoded=encode(dict(name='',mesh=native_connectors[sku][int(number)-1],material=part['material']))
            encoded.update(axes=axes.flatten().tolist(),
                           origin=(origin+axes@encoded['origin']).tolist(),hardware='frame')
            return encoded
        mesh = part['mesh']
        origin = mesh.bounds.mean(axis=0).round(4)
        vertices = np.rint(np.round((mesh.vertices-origin)*16,6)).astype('<i2')
        faces = mesh.faces.astype('<u2')
        assert len(mesh.vertices)<65536 and np.max(np.abs((mesh.vertices-origin)*16))<32767
        key = hashlib.sha256(vertices.tobytes()+faces.tobytes()).hexdigest()
        if key not in mesh_keys:
            name = f'g{len(geo)}'; mesh_keys[key] = name
            geo[name] = dict(v=base64.b64encode(vertices.tobytes()).decode(),
                             f=base64.b64encode(faces.tobytes()).decode())
        else:
            name = mesh_keys[key]
        material = {'back':'wood','rail':'handle','rubber':'frame'}.get(part['material'],part['material'])
        hardware = ('panel' if part['name'].startswith(('Pegboard-M6','Pegboard-washer',
                    'Pegboard-cross','Right-wall-M6','Right-wall-washer','Right-wall-cross')) else
                    'hinge' if part['name'].startswith(('Left-hinge','Left-profile','Left-panel')) else
                    'frame' if part['name'].startswith(('RSI-','Cube-','Foot-locknut')) else None)
        return dict(geo=name, origin=origin.tolist(), axes=[1,0,0,0,1,0,0,0,1],m=material,
                    top=top,display=None,left=moving,hardware=hardware,
                    **({'delta':part['delta']} if part.get('delta') is not None else {}))

    support=json.loads(gzip.decompress(base64.b64decode((ROOT/'work/viewer-v28-support-data.txt').read_text())))
    data={key:support[key] for key in ('tilt','slotStart','slotEnd','pivotY','pivotBelow')}
    data.update(leftAxis=AXIS_LEFT.tolist(),slotEnds={top:slot_end(top) for _,top in SECTIONS})
    data['full']=[encode(p) for p in fixed]+[encode(p,moving=True) for p in left]+[
        encode(p,top=top) for _,top in SECTIONS for p in right_leaf(top)]
    refs={p['name']:i for i,p in enumerate(fixed)}
    data['frame']=[dict(ref=i) for name,i in refs.items()
                   if name.startswith(('Post-','Beam-','RSI-','Cube-','Levelling-foot','Foot-locknut'))]
    data['right']=[dict(ref=i) for name,i in refs.items() if name in ('Right-wall-18','Center-18')
                   or name.startswith(('Shelf-Right-','Shelf-pin-Right-','Right-wall-','Right-runner-','Runner-spacer-'))]
    data['peg']=[dict(ref=refs['Left-pegboard-18'])]
    for key,parts in detail.items(): data[key]=[encode(p,moving=p.get('left',False)) for p in parts]
    data['geo']=geo
    data['mounts']=[dict(id=f'{side}{index}',point=[x,y,z])
                    for side,x in [('Л',19),('П',981)]
                    for index,(y,z) in enumerate(((97,790),(426,790),(97,1780),(426,1780)),1)]
    return data


def build_outputs(check=True):
    OUT.mkdir(exist_ok=True)
    fixed,left,rows,joints,seats=reviewed_structure_with_previous_door()
    detail=details(fixed,left)
    checks=dict(version='cambusa-v29-structural-checkpoint', fabrication_release=False,
                left_hinge='RSI 3025, retained v28; concealed Blum candidate not released',
                panel_mount_count=8, mounts_per_side=4, height_mm=1800,
                lower_beam_clearance_mm=140,
                frame_connectors={'5212':14,'5211':2,'2069':4},
                cube_bolts_M8x25=12, included_cube_caps=12,
                levelling_feet_D49M8H30=4, foot_locknuts_M8=4,
                cube_bolt_seats_mm=seats,
                caveats=['Load capacity, bolt preload and physical sample are not verified.',
                         'Cross dowels and generic screws are dimensional envelopes, not supplier CAD.',
                         'Concealed hinge candidate has link-to-door collisions at 110 degrees.'])
    if check:
        checks['poses']={}
        for a in (0,180):
            assembly=pose(fixed+right_parts(0),left,AXIS_LEFT,a)
            bad,threads=audit_contacts(assembly)
            checks['poses'][a]={'unexpected_contacts':bad,'localized_thread_contacts':threads}
            assert not bad,bad
            export(OUT/f'cabinet-{a}.glb',assembly)
        checks['left_sweep']=door_sweep(fixed,left)
        assert checks['left_sweep'][2]>0
        checks['hinge_motion_collisions']=hinge_motion(fixed,left)
        assert not checks['hinge_motion_collisions']
        checks['right_sweep']=[audit_leaf(right_leaf(z),fixed+left,z,slot_end(z)) for _,z in SECTIONS]
        assert min(r[1] for r in checks['right_sweep'])>0
        # Check all eight straight approaches with a 6 mm diameter tool.
        checks['panel_bolt_tool_access']=[]
        by_name={p['name']:p for p in fixed}
        for side,x,prefix,beam in [('left',19,'Pegboard',4),('right',981,'Right-wall',966)]:
            for y in (97,426):
                for top in (False,True):
                    z=1798.6 if top else 771.4
                    direction=[0,0,1 if top else -1]
                    tool=bore([x,y,z],direction,0,40,3)
                    hits=[p['name'] for p in fixed+left
                          if not p['name'].startswith(prefix+'-') and overlap_volume(tool,p['mesh'])>.08]
                    assert not hits,hits
                    checks['panel_bolt_tool_access'].append(dict(side=side,y=y,top=top,hits=hits))
        width=np.vstack([p['mesh'].bounds for p in fixed+left])[:,0]
        checks['width_including_feet_mm']=float(width.max()-width.min())
        (OUT/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
        with (OUT/'panels-and-shelves.csv').open('w',newline='') as stream:
            writer=csv.writer(stream,lineterminator='\n')
            writer.writerow(['part','size_a_mm','size_b_mm','stock_mm','count']);writer.writerows(rows)
        with (OUT/'profile-cuts.csv').open('w',newline='') as stream:
            writer=csv.writer(stream,lineterminator='\n');writer.writerow(['part','stock','length_mm'])
            for p in fixed:
                if p['name'].startswith(('Post-','Beam-')):
                    writer.writerow([p['name'],'OB-3030',round(float(max(p['mesh'].extents)),3)])
        for key,parts in detail.items():export(OUT/f'{key}-detail.glb',parts)
    model=payload(fixed,left,detail,joints)
    vertex_error=0.0
    for expected,encoded in zip(fixed+left,model['full']):
        geometry=model['geo'][encoded['geo']]
        vertices=np.frombuffer(base64.b64decode(geometry['v']),dtype='<i2').reshape(-1,3)/16
        placed=vertices@np.asarray(encoded['axes']).reshape(3,3).T+encoded['origin']
        error=float(np.abs(placed-expected['mesh'].vertices).max())
        assert error<.055,(expected['name'],error)
        vertex_error=max(vertex_error,error)
    data=base64.b64encode(gzip.compress(json.dumps(model,separators=(',',':')).encode())).decode()
    template=(ROOT/'work/viewer-v29-template.html').read_text()
    result=template.replace('__MODEL_DATA__',data)
    assert len(result.encode())<1_000_000,len(result.encode())
    (OUT/'viewer.html').write_text(result)
    if check:
        checks['viewer_max_vertex_coordinate_error_mm']=vertex_error
        (OUT/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--skip-checks',action='store_true')
    parser.add_argument('--output',type=Path);args=parser.parse_args()
    result=build_outputs(not args.skip_checks)
    if args.output:args.output.write_text(result)
    print(f'{len(result.encode())} bytes',flush=True)
