"""v31: carrier-free axles screwed into flush inserts in both plywood sides.

The axle supports seat on the wood faces. Six stock DIN 7965 M5x10 inserts
are represented by nominal thread envelopes, not by manufacturer CAD.
Six custom turned/slotted axles need a machining quote and a physical sample.
"""
import argparse
import base64
import csv
import gzip
import hashlib
import json
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
import trimesh as tm

import blum_inset as blum
import build_reviewed_cabinet as previous
from audit_assembly import load_parts
from build_aluminum_corner import cube, cut, cylinder, overlap_volume
from build_concealed_cabinet import audit_contacts
from build_frame_joinery import bore
from build_pegboard_cabinet import right_parts, right_leaf, slot_end
from build_right_lift import COLORS, SECTIONS, audit_leaf, export
from review_custom_parts_v30 import connected_bodies, normalize

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'outputs/cambusa-v30-review-fixes'
OUT=ROOT/'outputs/cambusa-v31-direct-axes'
COST=ROOT/'outputs/cambusa-v31-costs-rf'
DY=19.0
PIVOT_Y=70.0
REMOVED={f'Pin-carrier-{side}-{i}' for side in ('L','R') for i in (1,2,3)}
INSERT_URL='https://oniks-krep.ru/catalog/mufta_mebelnaya_latunnaya/din_7965_mufta_mebelnaya_rezbovaya_latunnaya_m5x10_vneshnij_10/'
COLORS['insert']=[182,141,67,255]


def dump(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def shaft(side,z):
    # Ø6 plain bearing surface, M5x0.8 stem of length 7, slotted outer end.
    shoulder=(509,519) if side=='L' else (957,972)
    stem=(502,509) if side=='L' else (972,979)
    blank=tm.boolean.union([cylinder(0,*shoulder,PIVOT_Y,z,3),
                            cylinder(0,*stem,PIVOT_Y,z,2.5)],engine='manifold')
    end=519 if side=='L' else 957
    lo,hi=(end-1.2,end+.1) if side=='L' else (end-.1,end+1.2)
    return cut(blank,[cube([lo,PIVOT_Y-.5,z-3.2],[hi,PIVOT_Y+.5,z+3.2])])


def direct_assembly():
    fixed,left,rows,joints,seats,mounts,machining=previous.assembly()
    assert {p['name'] for p in fixed if p['name'].startswith('Pin-carrier-')}==REMOVED
    fixed=[p for p in fixed if p['name'] not in REMOVED]
    for p in fixed:
        if p['name'].startswith(('Runner-L-','Runner-R-','Right-runner-spacer-',
                                 'Runner-spacer-bolt-','Runner-spacer-head-','Runner-spacer-washer-')):
            p['mesh']=p['mesh'].copy().apply_translation([0,DY,0])
    by_name={p['name']:p for p in fixed}
    # Restore the old six runner-bolt through holes before cutting their new
    # positions. Other right-panel bores and edge connections stay intact.
    wall=by_name['Right-wall-18']['mesh']
    filled=[cylinder(0,972,990,y,top-58,2.7)
            for _,top in SECTIONS for y in (140,330)]
    wall=tm.boolean.union([wall,*filled],engine='manifold')
    relocated=[cylinder(0,971.9,990.1,y+DY,top-58,2.7)
               for _,top in SECTIONS for y in (140,330)]
    by_name['Right-wall-18']['mesh']=cut(wall,relocated)
    cuts={'Center-18':[],'Right-wall-18':[]}
    interfaces=[]
    for i,(_,top) in enumerate(SECTIONS,1):
        z=top-52
        for side,wall,face,direction in [('L','Center-18',509,-1),('R','Right-wall-18',972,1)]:
            name=f'Pin-{side}-{i}'
            by_name[name]['mesh']=shaft(side,z)
            # Furniture insert: L10, outer thread major diameter 10, root 7.5.
            # Ø8 is a preliminary pilot for a sample; release requires a test.
            low,high=sorted((face,face+direction*10))
            outer=cylinder(0,low,high,PIVOT_Y,z,5)
            insert=cut(outer,[cylinder(0,low-.1,high+.1,PIVOT_Y,z,2.5)])
            insert_name=f'Axle-insert-{side}-{i}-M5x10'
            pilot=bore([face,PIVOT_Y,z],[direction,0,0],-.05,10.5,4)
            cuts[wall].append(pilot)
            fixed.append(dict(name=insert_name,mesh=insert,material='insert',group='hardware',
                              thread_targets={wall:outer}))
            by_name[name]['thread_targets']={}
            surface=by_name[wall]['mesh'].bounds[1 if side=='L' else 0,0]
            assert abs(surface-face)<.001
            vertices=by_name[name]['mesh'].vertices
            radius=np.linalg.norm(vertices[:,1:]-[PIVOT_Y,z],axis=1)
            bearing=vertices[radius>2.51]
            shoulder_face=bearing[:,0].min() if side=='L' else bearing[:,0].max()
            support_gap=abs(float(shoulder_face-surface))
            assert support_gap<.002
            interfaces.append(dict(axis=name,insert=insert_name,side_panel=wall,
                x_face_mm=face,pivot_y_mm=PIVOT_Y,pivot_z_mm=z,
                support_face_gap_mm=round(support_gap,6),plain_diameter_mm=6,
                plain_projection_mm=10 if side=='L' else 15,
                threaded_stem='M5x0.8',threaded_stem_length_mm=7,
                insert_length_mm=10,pilot_candidate_diameter_mm=8,pilot_depth_mm=10.5,
                pilot_needs_sample=True,panel_rear_skin_mm=7.5,
                u_from_panel_front_mm=PIVOT_Y-by_name[wall]['mesh'].bounds[0,1],
                v_from_panel_bottom_mm=z-by_name[wall]['mesh'].bounds[0,2]))
    for wall,holes in cuts.items():
        by_name[wall]['mesh']=cut(by_name[wall]['mesh'],holes)
    return fixed,left,rows,joints,interfaces,machining


def posed_right(progress):
    return [dict(p,mesh=p['mesh'].copy().apply_translation([0,DY,0])) for p in right_parts(progress)]


def axis_detail(fixed,side,section=False):
    names={f'Pin-{side}-1',f'Axle-insert-{side}-1-M5x10',
           'Center-18' if side=='L' else 'Right-wall-18'}
    low,high=([491,53.5,1057],[526,91,1093]) if side=='L' else ([950,53.5,1057],[990,91,1093])
    result=[]
    for p in fixed:
        if p['name'] not in names:
            continue
        mesh=p['mesh']
        if p['name'] in ('Center-18','Right-wall-18'):
            mesh=tm.boolean.intersection([mesh,cube(low,high)],engine='manifold')
        if section:
            # Remove the front half, exposing the stem, insert and blind pilot.
            mesh=tm.boolean.intersection([mesh,cube([low[0],70,low[2]],high)],engine='manifold')
        assert mesh.is_volume
        result.append(dict(p,mesh=mesh,material='handle' if p['name'].startswith('Axle-insert') else p['material']))
    return result


def extract_custom(fixed):
    folder=OUT/'custom-parts';folder.mkdir(exist_ok=True)
    old=json.loads((ROOT/'outputs/cambusa-v30-custom-parts-review/parts-manifest.json').read_text())
    by_name={p['name']:p for p in fixed}
    ledge=next(p['mesh'] for p in right_leaf(1127) if p['name']=='Display-ledge')
    manifest=[]
    for row in old:
        name=row['id']
        if name in REMOVED:
            continue
        group=row['group']
        mesh=normalize(ledge if group=='display-ledges' else by_name[name]['mesh'],group)
        assert mesh.is_volume and connected_bodies(mesh)==1,name
        export(folder/f'{name}.glb',[dict(name=name,mesh=mesh,material='handle',group='custom')])
        mesh.export(folder/f'{name}.stl')
        read=load_parts(folder/f'{name}.glb')[name]
        assert np.allclose(read.bounds,mesh.bounds,atol=.002)
        assert np.allclose(tm.load(folder/f'{name}.stl',force='mesh').bounds,mesh.bounds,atol=.002)
        row={**row,'dimensions_mm':mesh.extents.round(4).tolist(),
             'glb':f'custom-parts/{name}.glb','stl':f'custom-parts/{name}.stl'}
        if group=='pivot-pins':
            row['unfinished']='Заказная ось: гладкая часть Ø6, вылет 10 мм слева / 15 мм справа, хвостовик М5x0,8 длиной 7 мм, торцевой шлиц 1 × 1,2. Резьба показана номинальным цилиндром. Нужны допуски, фаски, технологический выход резьбы и испытание образца.'
        manifest.append(row)
    assert len(manifest)==25
    dump(OUT/'parts-manifest.json',manifest)
    with ZipFile(OUT/'custom-parts-v31.zip','w',ZIP_DEFLATED) as archive:
        for row in manifest:
            for key in ('glb','stl'):
                archive.write(OUT/row[key],row[key])
        archive.write(OUT/'parts-manifest.json','parts-manifest.json')
    return manifest


def planning(fixed,left,interfaces):
    COST.mkdir(exist_ok=True)
    before=ROOT/'outputs/cambusa-v30-costs-rf'
    for name in ('wood-parts.csv','profile-parts.csv','profile-cut-plan.csv','estimate.csv'):
        shutil.copyfile(before/name,COST/name)
    (COST/'cut-plan.svg').write_text((before/'cut-plan.svg').read_text().replace('v30','v31'))
    plan=json.loads((before/'plan.json').read_text())
    plan.update(version='cambusa-v31',model_sha256=hashlib.sha256((OUT/'cabinet-0.glb').read_bytes()).hexdigest())
    # Only bores change wood geometry. Every blank dimension remains identical.
    model=load_parts(OUT/'cabinet-0.glb');old_model=load_parts(BASE/'cabinet-0.glb')
    for row in plan['wood']+plan['profile_parts']:
        assert np.allclose(model[row['part']].extents,old_model[row['part']].extents,atol=.002)
    dump(COST/'plan.json',plan)
    dump(COST/'model-inventory.json',[dict(name=n,bounds_mm=m.bounds.tolist()) for n,m in model.items()])
    cost=json.loads((before/'estimate.json').read_text())
    cost['unpriced_hardware']=[r for r in cost['unpriced_hardware'] if r['id']!='pin-carriers']
    for row in cost['unpriced_hardware']:
        if row['id']=='pivot-pins':
            row.update(description='Оси Ø6 с хвостовиком М5 × 7; вылет 10 / 15 мм',
                       note='6 заказных точёных осей, торцевой шлиц; прямое крепление в мебельные муфты. Допуски и изготовление требуют согласования.')
    # Keep unquoted allowance unchanged. No unsupported saving is claimed.
    cost['unpriced_hardware'].append(dict(id='axle-inserts',description='Муфта DIN 7965 М5 × 10, наружный Ø10',
         quantity=6,model_ids=[r['insert'] for r in interfaces],price=None,amount_rub=None,covered_by='allow-fixings',
         note=f'Оникс 00053119; карточка 107,10 ₽/шт., региональный склад. Цена и количество заказа не подтверждены. {INSERT_URL}'))
    cost.update(base_tag='cambusa-v31-direct-axes',model_sha256=plan['model_sha256'],
                change_from_v30='Removed six carrier plates; added six flush M5 inserts; moved right mechanism 19 mm rearwards. Existing allowances unchanged pending quotes.')
    dump(COST/'estimate.json',cost)
    fields=['id','description','quantity','price','amount_rub','covered_by','note']
    with (COST/'unpriced-hardware.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');w.writeheader();w.writerows(cost['unpriced_hardware'])
    with (OUT/'axis-machining.csv').open('w',newline='') as f:
        fields=['side_panel','axis','u_from_panel_front_mm','v_from_panel_bottom_mm','pilot_candidate_diameter_mm','pilot_depth_mm','pilot_needs_sample']
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');w.writeheader();w.writerows(interfaces)
    with (OUT/'runner-machining.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n')
        w.writerow(['part','u_from_front_mm','v_from_bottom_mm','diameter_mm','type'])
        w.writerows(['Right-wall-18',y+DY-53.5,top-58-800,5.4,'through']
                    for _,top in SECTIONS for y in (140,330))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);args=parser.parse_args()
    OUT.mkdir(exist_ok=True)
    old_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in BASE.iterdir() if p.is_file()}
    fixed,left,rows,joints,interfaces,machining=direct_assembly()
    details=previous.details(fixed,left)
    for side in ('L','R'):
        details[f'axis-{side.lower()}']=axis_detail(fixed,side,section=True)
        export(OUT/f'axis-{side.lower()}.glb',axis_detail(fixed,side))
        export(OUT/f'axis-{side.lower()}-section.glb',details[f'axis-{side.lower()}'])
    checks=dict(version='cambusa-v31-direct-axes',removed_parts=sorted(REMOVED),
        mechanism_shift_y_mm=DY,interfaces=interfaces,fabrication_release=False,poses={})
    for angle in (0,110):
        parts=fixed+posed_right(0)+blum.posed(left,angle,previous.CUP_SPACER)
        bad,threads=audit_contacts(parts)
        checks['poses'][angle]=dict(unexpected=bad,thread_contacts=len(threads))
        print('pose',angle,bad,flush=True);assert not bad,bad
        export(OUT/f'cabinet-{angle}.glb',parts)
        actual=load_parts(OUT/f'cabinet-{angle}.glb')
        assert not REMOVED.intersection(actual)
        expected={p['name']:p['mesh'] for p in parts if p['group']!='prop'}
        assert set(actual)==set(expected)
        error=max(float(np.abs(actual[n].bounds-m.bounds).max()) for n,m in expected.items())
        assert error<.002
        checks['poses'][angle].update(part_count=len(actual),maximum_bounds_error_mm=error)
    # Translate obstacles back to use the existing certified motion sampler.
    relative=[dict(p,mesh=p['mesh'].copy().apply_translation([0,-DY,0])) for p in fixed+left]
    checks['right_sweeps']=[audit_leaf(right_leaf(top),relative,top,slot_end(top)) for _,top in SECTIONS]
    print('right sweeps',checks['right_sweeps'],flush=True)
    assert min(r[1] for r in checks['right_sweeps'])>0
    checks['left_door_sweep']=previous.door_sweep(fixed,left,right=posed_right(0))
    assert checks['left_door_sweep']['lower_bound_mm']>0
    # Verify actual cylindrical pin/slot clearance throughout both phases.
    pin_contacts=[]
    for i,(_,top) in enumerate(SECTIONS,1):
        pins=[p for p in fixed if p['name'] in (f'Pin-L-{i}',f'Pin-R-{i}')]
        for t in np.linspace(0,2,81):
            leaves=[p for p in posed_right(float(t)) if p['name'] in (f'Stile-L-{i}',f'Stile-R-{i}')]
            for pin,leaf in zip(sorted(pins,key=lambda p:p['name']),sorted(leaves,key=lambda p:p['name'])):
                v=overlap_volume(pin['mesh'],leaf['mesh'])
                if v>.02:pin_contacts.append([float(t),pin['name'],leaf['name'],v])
    assert not pin_contacts,pin_contacts[:5]
    checks['pin_slot_sampled_collisions']=pin_contacts
    checks['pin_slot_progress_step']=.025
    checks['pin_slot_nominal_diametral_clearance_mm']=1.3
    checks['thread_geometry']='Nominal diameters, no helical surfaces; insert outer threads overlap wood only inside declared thread regions.'
    data=previous.make_payload(fixed,left,joints,details);data['pivotY']=PIVOT_Y
    # The standard viewer receives the new cropped axle sections as extra views.
    for key in ('axis-l','axis-r'):
        assert key in data and len(data[key])==3
    packed=base64.b64encode(gzip.compress(json.dumps(data,separators=(',',':')).encode())).decode()
    html=(ROOT/'work/viewer-v31-template.html').read_text().replace('__MODEL_DATA__',packed)
    assert len(html.encode())<1_000_000
    (OUT/'viewer.html').write_text(html)
    if args.output:args.output.write_text(html)
    manifest=extract_custom(fixed)
    checks['custom_parts_count']=len(manifest)
    checks['purchased_axle_inserts_count']=6
    checks['source_v30_unchanged']=old_hashes=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in BASE.iterdir() if p.is_file()}
    assert checks['source_v30_unchanged']
    checks['remaining_qualification']='Thread envelopes are nominal. Pilot needs a sample; shaft end chamfers, thread relief and tolerances require manufacturing drawing. No physical load or wear test performed.'
    dump(OUT/'checks.json',checks)
    planning(fixed,left,interfaces)
    print('v31 built',len(html.encode()),'bytes; custom parts',len(manifest),flush=True)


if __name__=='__main__':main()
