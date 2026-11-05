"""Compare 18/21/24 mm pegboards with the v31 hinge mounting datum fixed.

This is a study, not a promotion of a new cabinet or manufacturing release.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import trimesh as tm

import blum_inset as blum
import build_reviewed_cabinet as reviewed
import plan_v30 as planning
from build_aluminum_corner import cube, cut, overlap_volume
from build_concealed_cabinet import audit_contacts
from build_direct_axes_v31 import direct_assembly, posed_right
from build_frame_joinery import PEGBOARD_PATTERN, bore
from build_pegboard_cabinet import drill_x, drill_z
from build_right_lift import export
from audit_assembly import load_parts

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/pegboard-thickness-study-v31'


def export_candidate(name,parts):
    parts=[dict(p,name='Left-pegboard-24') if p['name']=='Left-pegboard-18' else p for p in parts]
    export(OUT/name,parts)
    actual=load_parts(OUT/name)
    expected={p['name']:p['mesh'] for p in parts if p['group']!='prop'}
    assert set(actual)==set(expected)
    error=max(float(np.abs(actual[n].bounds-m.bounds).max()) for n,m in expected.items())
    assert error<.002
    return dict(part_count=len(actual),maximum_bounds_error_mm=error)


def candidate(thickness,base,with_hinge_pilots=True):
    inner=10+thickness;delta=thickness-18;depth=thickness-8
    fixed=[dict(p,mesh=p['mesh'].copy(),thread_targets=dict(p.get('thread_targets',{}))) for p in base]
    by_name={p['name']:p for p in fixed}
    tools=[bore([10,y,z],[1,0,0],-.1,depth,6) for y,z in PEGBOARD_PATTERN]
    tools += [drill_x(inner,y,z,-10.3,.1,3.03) for z in (1138,1458) for y in (150,400)]
    for z,edge,sign in ((820,800,1),(1749,1769,-1)):
        for y in (97,426):
            tools += [drill_x(inner,y,z,13.4-inner,.1,5.05),
                      drill_z(19,y,edge-sign*.1,z+sign*5,3.3)]
    if with_hinge_pilots:
        for z in blum.CENTERS:
            for y in (64,96):
                tools.append(bore([inner,y,z],[-1,0,0],-.1,inner-15.15,1.25))
    board=cut(cube([10,53.5,800],[inner,469.5,1769]),tools)
    by_name['Left-pegboard-18']['mesh']=board
    for p in fixed:
        if p['name'].startswith('Blum-') and '-spacer-6' in p['name']:
            if thickness==24:
                continue
            p['mesh']=tm.boolean.intersection([p['mesh'],cube([inner,0,0],[35,500,1800])],engine='manifold')
        if p['name'].startswith('Blum-') and '-plate-screw-' in p['name']:
            y=p['mesh'].bounds.mean(axis=0)[1];z=p['mesh'].bounds.mean(axis=0)[2]
            p['thread_targets']['Left-pegboard-18']=bore([inner,y,z],[-1,0,0],-.01,inner-15.2,1.8)
        if p['name'].startswith('Shelf-pin-Left-') and '-pegboard-' in p['name']:
            p['mesh'].apply_translation([delta,0,0])
        if p['name'].startswith('Shelf-Left-'):
            z=p['mesh'].bounds[0,2]
            p['mesh']=tm.boolean.intersection([p['mesh'],cube([inner+1,0,z-.1],[500,500,z+19])],engine='manifold')
            p['mesh']=cut(p['mesh'],[drill_x(inner,y,z,-.1,10.35,3.1) for y in (150,400)])
    if thickness==24:
        fixed=[p for p in fixed if not (p['name'].startswith('Blum-') and '-spacer-6' in p['name'])]
    return fixed,dict(panel_thickness_mm=thickness,panel_blank_mm=[416,969,thickness],
            inner_face_x_mm=inner,plate_mounting_x_mm=34,backer_remaining_mm=24-thickness,
            peg_diameter_mm=12,peg_flat_depth_mm=depth,peg_remaining_skin_mm=8,
            shelf_length_mm=461-delta,hinge_screw_wood_penetration_mm=inner-15.25,
            board_extra_gross_volume_m3=.416*.969*delta/1000,
            board_extra_gross_mass_kg_at_700kg_m3=.416*.969*delta/1000*700)


def main():
    OUT.mkdir(exist_ok=True)
    model=ROOT/'outputs/cambusa-v31-direct-axes/cabinet-0.glb'
    base_hash=hashlib.sha256(model.read_bytes()).hexdigest()
    base,left,*_=direct_assembly()
    base_board=next(p['mesh'] for p in base if p['name']=='Left-pegboard-18')
    report=dict(status='comparison only; v31 unchanged',fabrication_release=False,cases={})
    for thickness in (18,21,24):
        fixed,case=candidate(thickness,base)
        board=next(p['mesh'] for p in fixed if p['name']=='Left-pegboard-18')
        case['board_net_mass_delta_kg_at_700kg_m3']=float((board.volume-base_board.volume)/1e9*700)
        case['poses']={}
        for angle in (0,55,90,110):
            bad,threads=audit_contacts(fixed+posed_right(0)+blum.posed(left,angle,reviewed.CUP_SPACER))
            case['poses'][angle]=dict(unexpected=bad,thread_contacts=len(threads))
            print(thickness,angle,bad,flush=True)
            assert not bad,(thickness,angle,bad)
        case['door_sweep']=reviewed.door_sweep(fixed,left,right=posed_right(0))
        assert case['door_sweep']['lower_bound_mm']>0
        if thickness==24:
            case['hinge_sample_step_degrees']=1
            case['hinge_sample_collisions']=reviewed.hinge_samples(fixed,left)
            assert not case['hinge_sample_collisions'],case['hinge_sample_collisions'][:4]
            case['export_readback']={}
            for label,angle in [('closed',0),('open',110)]:
                case['export_readback'][label]=export_candidate(f'candidate-24mm-{label}.glb',fixed+posed_right(0)+blum.posed(left,angle,reviewed.CUP_SPACER))
            names={'Left-pegboard-18','Left-door-face-18','Post-4-23'}
            detail=[]
            for p in fixed+left:
                if p['name'] in names:
                    detail.append(dict(p,mesh=tm.boolean.intersection([p['mesh'],cube([3,14,848],[106,116,938])],engine='manifold')))
                elif p['name'].startswith('Blum-1-'):
                    detail.append(p)
            case['export_readback']['hinge']=export_candidate('candidate-24mm-hinge.glb',detail)
            # Verify all 152 flat bottoms and their remaining 8 mm skins.
            board=next(p['mesh'] for p in fixed if p['name']=='Left-pegboard-18')
            blind=[]
            for y,z in PEGBOARD_PATTERN:
                empty=bore([10,y,z],[1,0,0],.01,15.99,5.99)
                skin=bore([26,y,z],[1,0,0],.01,7.99,5.99)
                blind.append(overlap_volume(board,empty)<.01 and abs(overlap_volume(board,skin)-skin.volume)<.01)
            case['verified_blind_holes']=int(sum(blind));assert all(blind)
        report['cases'][thickness]=case
    plan=json.loads((ROOT/'outputs/cambusa-v31-costs-rf/plan.json').read_text())
    wood=plan['wood']
    revised=[]
    for row in wood:
        r=dict(row)
        if r['part']=='Left-pegboard-18':r.update(part='Left-pegboard-24',stock_mm=24)
        if r['part'].startswith('Shelf-Left-'):r['a_mm']-=6
        r['area_m2']=r['a_mm']*r['b_mm']/1e6
        revised.append(r)
    layouts=planning.sheets(revised)
    from collections import Counter
    report['sheet_counts_24mm_candidate']=dict(Counter(int(l['thickness_mm']) for l in layouts))
    report['layouts_24mm_candidate']=layouts
    report['additional_backer_plate_count_removed']=3
    report['cup_spacer_1_5mm_count_retained']=3
    report['cup_spacer_scope']='Door-side cup spacer; increasing pegboard thickness replaces the body-side 6 mm backers only.'
    assert base_hash==hashlib.sha256(model.read_bytes()).hexdigest()
    report['base_model_sha256']=base_hash
    (OUT/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('case comparison complete; sheet counts',report['sheet_counts_24mm_candidate'],flush=True)


if __name__=='__main__':main()
