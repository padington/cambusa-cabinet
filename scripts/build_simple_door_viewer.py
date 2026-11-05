"""Build the v28 interactive viewer from the same parts as the audited GLBs."""
import argparse
import base64
import gzip
import json
from pathlib import Path

import numpy as np

from build_frame_joinery import cad_parts
from build_simple_left_door import (
    ROOT, OUT, AXIS_LEFT, HINGE_CENTERS, cabinet,
    detail_parts, supplier_meshes,
)
from build_pegboard_cabinet import right_leaf, slot_end
from build_right_lift import SECTIONS


def encode(part, top=None, left=False, delta=None):
    mesh = part['mesh']
    quantized = np.rint(mesh.vertices * 16)
    assert np.max(np.abs(quantized)) < 32768 and len(mesh.vertices) < 65536
    return dict(v=base64.b64encode(quantized.astype('<i2').tobytes()).decode(),
                f=base64.b64encode(mesh.faces.astype('<u2').tobytes()).decode(),
                m={'back':'wood', 'rail':'handle', 'rubber':'frame'}.get(
                    part['material'], part['material']),
                top=top, display=None, left=left,
                **({'delta':delta} if delta is not None else {}))


def payload():
    fixed, left, _, joints, _, _ = cabinet()
    previous = json.loads(gzip.decompress(base64.b64decode(
        (ROOT / 'work/viewer-v28-support-data.txt').read_text())))
    data = {key:previous[key] for key in (
        'tilt', 'slotStart', 'slotEnd', 'pivotY', 'pivotBelow')}
    data['leftAxis'] = AXIS_LEFT.tolist()
    geo = {}
    for sku, parts in cad_parts().items():
        for i, mesh in enumerate(parts, 1):
            geo[f'{sku}-{i}'] = encode(dict(mesh=mesh, material='fastener'))
    for sku in ('3025', '5049'):
        for i, mesh in enumerate(supplier_meshes(sku)):
            geo[f'{sku}-{i}'] = encode(dict(mesh=mesh,
                                          material='handle' if sku == '3025' else 'fastener'))
    data['geo'] = geo

    def encode_placed(part, moving=False):
        name = part['name']
        if name.startswith('Left-hinge-'):
            index, _, number = name.split('-')[2:]
            return dict(geo=f'3025-{number}', axes=[1,0,0,0,0,-1,0,1,0],
                        origin=[34,16.5,HINGE_CENTERS[int(index)-1]-25], left=moving)
        if name.startswith('Left-profile-nut-'):
            # Both the nut and spring ball share the native supplier axes.
            center = part['mesh'].bounds.mean(axis=0)
            native = supplier_meshes('5049')[int(name[-1])].bounds.mean(axis=0)
            return dict(geo='5049-'+name[-1], axes=[1,0,0,0,1,0,0,0,1],
                        origin=(center-native).tolist())
        return encode(part, left=moving)

    overview = [p for p in fixed if p['material'] != 'fastener' or
                p['name'].startswith('Left-')]
    data['full'] = [encode_placed(p) for p in overview] + [encode_placed(p, True) for p in left] + [
        encode(p, top) for _, top in SECTIONS for p in right_leaf(top)]
    refs = {p['name']:i for i,p in enumerate(overview)}
    by_id = {j['id']:j for j in joints}

    def connector_ref(name, delta=None):
        sku, jid, number = name.split('::')
        sku = sku.split('-')[1]
        joint = by_id[jid]
        access, along = joint['access'], joint['along']
        return dict(geo=f'{sku}-{number}',
                    axes=np.column_stack((np.cross(access,along),access,along)).flatten().tolist(),
                    origin=(joint['point']-.25*along if sku=='5212' and number=='1'
                            else joint['point']).tolist(), delta=delta)

    data['frame'] = [dict(ref=i) for name,i in refs.items() if name.startswith(('Post-','Beam-'))]
    for part in fixed:
        if part['name'].startswith('RSI-'):
            joint = by_id[part['name'].split('::')[1]]
            data['frame'].append(connector_ref(part['name'], (joint['access']*39).tolist()))
    data['right'] = [dict(ref=i, **({'m':'angle'} if name.startswith('Beam-right-shelf-') else {}))
                     for name,i in refs.items()
                     if name in ('Center-18','Post-966-23','Post-966-470',
                                 'Beam-body-side-966','Beam-top-side-966')
                     or name.startswith(('Beam-right-shelf-','Right-infill-8-','Shelf-Right-'))] + [
        p for p in data['frame'] if p.get('geo','').startswith('5211-') and p['origin'][0]==981]
    # The archived detail meshes already contain their own geometry.
    for key in ('rail','center','corner','side'):
        data[key] = previous[key]
    data['hinge'] = [encode_placed(p, p['left']) for p in detail_parts(fixed,left)]
    data['peg'] = [dict(ref=refs['Left-pegboard-18'])]
    data['slotEnds'] = {top:slot_end(top) for _,top in SECTIONS}
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT/'viewer.html')
    args = parser.parse_args()
    data = base64.b64encode(gzip.compress(json.dumps(payload(),separators=(',',':')).encode())).decode()
    template = (ROOT/'work/viewer-v28-template.html').read_text()
    assert template.count('__MODEL_DATA__') == 1
    result = template.replace('__MODEL_DATA__',data)
    assert len(result.encode()) < 1_000_000
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(result)
    print(args.output, len(result.encode()))


if __name__ == '__main__':
    main()
