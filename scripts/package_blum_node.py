"""Bundle the reviewed hinge candidate without marking it as a production release."""
import csv
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/cambusa-v32-hinge-node'
CAD = ROOT / 'outputs/wide-hinge-verification'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    exact = json.loads((CAD / 'exact-fit.json').read_text())
    assert exact['external_nominal_fit_passed'] and exact['sample_count'] == 681
    assert not exact['unexpected']
    rows = [
        ['71T6650', 'Blum CLIP top 170 degree screw-on hinge', 3, 1128.96,
         'https://blum-market.ru/clip-top-polunakladnaya-petlya-170-71t6650'],
        ['175H7190', 'Blum CLIP mounting plate 9 mm screw-on', 3, 387.07,
         'https://blum-market.ru/montazhnaya-planka-clip-9mm-samorez-175h7190'],
        ['609.1500', 'Blum countersunk screw 3.5x15 PZ2', 12, 9.17,
         'https://blum-rus.ru/samorez-35-h-15mm'],
    ]
    with (OUT / 'hinge-bom.csv').open('w', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['sku', 'description', 'installed_qty', 'unit_rub', 'line_rub',
                    'price_observed_date', 'supplier_url', 'status'])
        for sku, name, qty, price, url in rows:
            w.writerow([sku, name, qty, f'{price:.2f}', f'{qty * price:.2f}',
                        '2026-11-05', url, 'review candidate; stock not reserved'])
    assert round(sum(q * p for _, _, q, p, _ in rows), 2) == 4658.13
    readiness = dict(
        version='cambusa-v32-hinge-node', status='candidate_for_review',
        external_nominal_cad_fit_passed=True, exact_sample_count=681,
        internal_mechanism_independently_verified=False,
        internal_overlap_origin_independently_confirmed=False,
        physical_fit_and_load_test_performed=False,
        machining_tolerances_and_final_material_confirmed=False,
        release_for_full_cabinet_manufacture=False,
        next_acceptance='One purchased hinge + plate and a machined sample corner in final material, or independently validated native CAD; agree final material and machining tolerances before full cutting.',
        tested_assembly='71T6650 + 175H7190 without cup or plate spacers; nominal adjustment only',
        hardware_installed_cost_rub=4658.13,
        exclusions=['delivery', 'wood', 'machining', 'optional damper 973A6000'],
    )
    (OUT / 'readiness.json').write_text(json.dumps(readiness, indent=2) + '\n')
    old = json.loads((ROOT / 'inputs/blum-wide-hinge-sources.json').read_text())
    source_files = [dict(row) for row in old['sources']]
    planning = ROOT / 'inputs/supplier-cad/blum-170-planning.pdf'
    source_files.append(dict(file=str(planning.relative_to(ROOT)), sha256=sha(planning),
        bytes=planning.stat().st_size,
        source_url='https://publications.blum.com/2026/catalogue/en/83/',
        retrieved_date='2026-11-05', description='Official downloaded single-page planning PDF; printed page 83'))
    for row in source_files:
        assert sha(ROOT / row['file']) == row['sha256']
    generated = sorted(CAD.glob('*.step')) + [CAD / 'explicit-conversion.json',
        CAD / 'exact-fit.json', CAD / 'screw-seats.json', OUT / 'model-checks.json',
        OUT / 'viewer-checks.json', OUT / 'hinge-bom.csv', OUT / 'readiness.json']
    sources = dict(
        prepared_date='2026-11-06', source_files=source_files,
        manufacturer_pages=old['manufacturer_catalogue'] + [
            'https://publications.blum.com/2026/catalogue/en/154/',
            'https://ea.blum.com/en/number-of-hinges/'],
        supplier_pages=[row[4] for row in rows],
        conversion_engine=dict(project='https://github.com/monozukuri-ai/cq-acis',
            package_version='0.3.12', inspected_source_commit='e05a8f470d2f6799277f7b7df467d2fc35625889',
            local_adapter='scripts/blum_acis208.py', dependencies='requirements-cad.txt'),
        failed_independent_check='ShareCAD remote URL attempt showed the default demo instead of the DXF; no independent validation obtained.',
        generated=[dict(file=str(p.relative_to(ROOT)), sha256=sha(p), bytes=p.stat().st_size)
                   for p in generated],
    )
    (OUT / 'sources.json').write_text(json.dumps(sources, ensure_ascii=False, indent=2) + '\n')
    included = [OUT / name for name in ['README.md', 'hinge-bom.csv', 'readiness.json',
        'sources.json', 'hinge-machining.csv', 'model-checks.json', 'viewer-checks.json',
        'hinge-0.glb', 'hinge-170.glb', 'left-door-machined.glb']]
    included += sorted((OUT / 'machining').glob('*'))
    included += generated[:10]  # Eight supplier solids and two nominal screw envelopes.
    included += [CAD / 'exact-fit.json', CAD / 'screw-seats.json', CAD / 'explicit-conversion.json']
    included += [ROOT / row['file'] for row in source_files]
    target = OUT / 'hinge-review-pack.zip'
    with ZipFile(target, 'w', ZIP_DEFLATED) as z:
        for path in dict.fromkeys(included):
            z.write(path, str(path.relative_to(ROOT)))
    with ZipFile(target) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(set(z.namelist()))
    print(f'Review pack: {target.stat().st_size} bytes; full manufacturing release remains false')


if __name__ == '__main__':
    main()
