"""Package the independently reviewed node; preserve explicit release boundaries."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import csv,hashlib,json,shutil
import blum_node_v33_spec as spec

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/f'outputs/{spec.VERSION}'
CAD=ROOT/'outputs/blum-independent-v33'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    fit=json.loads((OUT/'exact-fit.json').read_text())
    assert fit['sample_count']==681 and fit['external_nominal_fit_passed'] and fit['sampled_clearance_target_passed']
    source=json.loads((CAD/'source-ray-check.json').read_text());assert source['passed']
    coarse=json.loads((CAD/'source-ray-check-coarse.json').read_text())
    assert len(source['witnesses'])==len(coarse['witnesses'])==9
    for a,b in zip(source['witnesses'],coarse['witnesses']):
        assert a['point']==b['point']
        for key,row in a['bodies'].items():
            other=b['bodies'][key]
            assert row['inside']==other['inside'] and row['curved_possible']==other['curved_possible']==[]
            assert [h[1] for h in row['hits']]==[h[1] for h in other['hits']]
            assert max(abs(h[2]-g[2]) for h,g in zip(row['hits'],other['hits']))<1e-6
    assert json.loads((OUT/'viewer-checks.json').read_text())['passed']
    rows=list(csv.reader((ROOT/'outputs/cambusa-v32-hinge-node/hinge-bom.csv').open()))
    for row in rows[1:]:row[5]='2026-11-06';row[7]='specified for order; price and stock not reserved'
    with (OUT/'hinge-bom.csv').open('w',newline='') as f:csv.writer(f,lineterminator='\n').writerows(rows)
    readiness=dict(version=spec.VERSION,hardware_skus_and_quantities_complete=True,
        independent_source_found=True,source_overlap_independently_confirmed_for_pairs=[[2,4]],
        all_internal_overlap_pairs_independently_classified=False,
        external_nominal_fit_passed=True,angular_samples=681,sampled_moving_link_clearance_target_mm=.5,
        minimum_sampled_moving_link_to_wood_mm=min(x['mm'] for x in fit['minimum_moving_link_clearance'].values()),
        wood_machining_files_complete=True,order_request_package_ready=True,
        supplier_material_and_tolerance_acceptance_received=False,unconditional_manufacturing_release=False,
        physical_test_performed=False,complete_cabinet_release=False,
        remaining_before_CNC_start=['Confirm finished stock thicknesses and surface finish','Manufacturer accepts ORDER-SPEC.md machining tolerances and correct datum faces'],
        scope='Purchased complete Blum hinge node; nominal CAD fit using previous factory-derived pivot graph. No independent factory animated assembly, full adjustment-envelope certificate, or physical qualification.')
    (OUT/'readiness.json').write_text(json.dumps(readiness,indent=2)+'\n')
    with (OUT/'machining/operations.csv').open() as f:operations=list(csv.DictReader(f))
    relief=[r for r in operations if r['operation'].startswith('RELIEF')]
    assert len(relief)==3
    assert all(float(r['diameter_or_width_mm'])==spec.RELIEF_WIDTH and float(r['depth_mm'])==spec.RELIEF_DEPTH for r in relief)
    manifest=json.loads((OUT/'machining/manifest.json').read_text())
    for name,digest in manifest['files'].items():assert sha(OUT/'machining'/name)==digest
    extraction=json.loads((ROOT/'inputs/supplier-cad/demos-71t6650/manifest.json').read_text())
    for row in extraction['bodies']:assert sha(ROOT/row['file'])==row['sha256']
    inputs=[ROOT/extraction['source'],ROOT/'inputs/supplier-cad/demos-71t6650/manifest.json']
    inputs += [ROOT/row['file'] for row in extraction['bodies']]
    inputs += [ROOT/'inputs/blum-wide-hinge-sources.json',ROOT/'inputs/supplier-cad/blum-175h7190.dxf',
        ROOT/'inputs/supplier-cad/blum-175h7190-technical.pdf',ROOT/'inputs/supplier-cad/blum-170-planning.pdf',
        ROOT/'inputs/supplier-cad/blum-71t6650.dxf',ROOT/'outputs/wide-hinge-study/linkage.json']
    outputs=[CAD/'explicit-conversion.json',CAD/'source-ray-check.json',CAD/'source-ray-check-coarse.json',
        CAD/'canonical/alignment.json',CAD/'canonical/screw-seats.json',OUT/'exact-fit.json',OUT/'model-checks.json',OUT/'viewer-checks.json']
    outputs+=sorted((CAD/'canonical').glob('*.step'))
    report=dict(version=spec.VERSION,retrieved_date='2026-11-06',source_page=extraction['source_page'],download_url=extraction['download_url'],
        source_files=[dict(file=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in inputs],
        inspected_cq_acis_source_commit='e05a8f470d2f6799277f7b7df467d2fc35625889',
        direct_Blum_STEP='Official product database requires an E-SERVICES login; no direct authenticated STEP obtained.',
        supplier_price_pages=[r[6] for r in rows[1:]],
        checks_and_models=[dict(file=str(p.relative_to(ROOT)),sha256=sha(p)) for p in outputs])
    (OUT/'sources.json').write_text(json.dumps(report,indent=2)+'\n')
    files=inputs+outputs+[OUT/n for n in ('README.md','ORDER-SPEC.md','readiness.json','sources.json','hinge-bom.csv','hinge-machining.csv',
        'hinge-0.glb','hinge-170.glb','left-door-machined.glb')]+sorted((OUT/'machining').glob('*'))
    path=OUT/'hinge-order-pack.zip'
    with ZipFile(path,'w',ZIP_DEFLATED) as z:
        for p in dict.fromkeys(files):z.write(p,str(p.relative_to(ROOT)))
    with ZipFile(path) as z:assert z.testzip() is None
    print('Order request ready:',path.stat().st_size,'bytes; maker acceptance remains explicit')

if __name__=='__main__':main()
