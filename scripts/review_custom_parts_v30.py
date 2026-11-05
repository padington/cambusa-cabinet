"""Extract the 31 custom-part instances from the unchanged v30 for review.

GLB/STL geometry is inspectable, but is not a released manufacturing package.
No threads, fixing holes or radii are silently added during extraction.
"""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
import trimesh as tm

from audit_assembly import load_parts
from build_aluminum_corner import COLORS, cube, overlap_volume
from build_frame_joinery import bore
from build_pegboard_cabinet import right_leaf, slot_end
from build_right_lift import export, pose

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/cambusa-v30-custom-parts-review'
SOURCE=ROOT/'outputs/cambusa-v30-review-fixes/cabinet-0.glb'
COLORS['context']=[135,141,143,255]
GROUPS={
 'hinge-backers':('Проставки петель',3,'51 × 24 × 6 мм; два проходных отверстия Ø3,7',
                  'Есть отверстия и положение в сборке. Материал, допуски и обработка ещё не утверждены.'),
 'runner-backers':('Проставки направляющих',3,'260 × 32 × 6 мм; номинальные гнёзда Ø5',
                   'В модели гнёзда глубиной 5,5 мм, с дном 0,5 мм. Подготовка под настоящую резьбу М5 не определена.'),
 'runners':('Опоры скольжения фасадов',6,'260 × 17 × 8 и 260 × 16 × 8 мм',
            'Прямоугольные тела без крепёжных отверстий. Материал, износ и полный крепёж не определены.'),
 'pin-carriers':('Держатели осей',6,'32 × 18 × 3 и 32 × 18 × 2 мм',
                 'Сплошные пластины без отверстий для оси и крепления к шкафу.'),
 'pivot-pins':('Оси фасадов',6,'Ø6, видимый вылет 7 мм',
               'Модель показывает только выступающий цилиндр. Нет хвостовика, посадки и удержания в держателе. 7 мм не является полной заказной длиной оси.'),
 'display-ledges':('Ручки-полочки',3,'Длина 444 мм, стенка 2 мм',
                   'Есть форма сечения. Крепление к фасаду, материал и производственные радиусы не заданы.'),
 'panel-shims':('Прокладки под панели',4,'18 × 20 × 1 мм, отверстие Ø6,6',
                'Есть проходное отверстие и посадка в сборке. Требуется выбор материала и способа изготовления.')
}


def part(name,mesh,material='angle',**extra):
    return dict(name=name,mesh=mesh,material=material,group='review',**extra)


def clip(mesh,low,high):
    result=tm.boolean.intersection([mesh,cube(low,high)],engine='manifold')
    assert result.is_volume
    return result


def normalize(mesh,group):
    result=mesh.copy()
    if group in ('hinge-backers','runner-backers','pin-carriers','pivot-pins'):
        t=np.eye(4);t[:3,:3]=np.array([[0,1,0],[0,0,1],[1,0,0]])
        result.apply_transform(t)
    elif group=='runners':
        t=np.eye(4);t[:3,:3]=np.array([[0,1,0],[-1,0,0],[0,0,1]])
        result.apply_transform(t)
    result.apply_translation(-result.bounds[0])
    return result


def connected_bodies(mesh):
    """Face-edge connectivity without optional scipy/networkx dependencies."""
    parent=list(range(len(mesh.faces)));edges={}
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,face in enumerate(mesh.faces):
        for a,b in zip(face,np.roll(face,-1)):
            key=tuple(sorted((int(a),int(b))))
            if key in edges:parent[find(i)]=find(edges[key])
            else:edges[key]=i
    return len({find(i) for i in range(len(parent))})


def main():
    arg=argparse.ArgumentParser();arg.add_argument('--output',type=Path);args=arg.parse_args()
    (OUT/'parts').mkdir(parents=True,exist_ok=True)
    source=load_parts(SOURCE)
    priced=json.loads((ROOT/'outputs/cambusa-v30-costs-rf/estimate.json').read_text())
    rows=[r for r in priced['unpriced_hardware'] if r['id'] in GROUPS]
    names=[n for r in rows for n in r['model_ids']]
    assert len(names)==len(set(names))==31 and set(names)<=set(source)
    local={};manifest=[];rechecks=[]
    ledge=next(p['mesh'] for p in right_leaf(1127) if p['name']=='Display-ledge')
    for row in rows:
        group=row['id'];title,count,dimensions,unfinished=GROUPS[group]
        assert len(row['model_ids'])==count
        for name in row['model_ids']:
            mesh=normalize(ledge if group=='display-ledges' else source[name],group)
            assert mesh.is_volume and connected_bodies(mesh)==1,name
            local[name]=mesh
            export(OUT/'parts'/f'{name}.glb',[part(name,mesh)])
            mesh.export(OUT/'parts'/f'{name}.stl')
            read=load_parts(OUT/'parts'/f'{name}.glb')[name]
            error=float(np.abs(mesh.bounds-read.bounds).max())
            assert error<.002,(name,error)
            stl=tm.load(OUT/'parts'/f'{name}.stl',force='mesh')
            assert np.allclose(stl.bounds,mesh.bounds,atol=.002)
            manifest.append(dict(id=name,group=group,title=title,dimensions_mm=mesh.extents.round(4).tolist(),
                supplier_cad=False,model_kind='project triangle mesh',native_units='mm',glb_units='m',
                stl_units_convention='mm',glb=f'parts/{name}.glb',stl=f'parts/{name}.stl',
                manufacturer_drawing=False,fabrication_release=False,unfinished=unfinished))
            rechecks.append(dict(id=name,maximum_bounds_error_mm=error))
    # Check the two spacer geometries directly, beyond their bounding boxes.
    hinge=local['Blum-1-spacer-6']
    for u in (8.5,40.5):
        assert overlap_volume(hinge,bore([u,12,0],[0,0,1],-.05,6.05,1.7))<.01
    runner=local['Right-runner-spacer-6-1']
    for u in (35,225):
        assert overlap_volume(runner,bore([u,16,0],[0,0,1],.6,5.9,2.4))<.01
        probe=bore([u,16,0],[0,0,1],.01,.49,2.4)
        assert abs(overlap_volume(runner,probe)-probe.volume)<.01
    contacts=[]
    for i in (1,2,3):
        for side in ('L','R'):
            carrier=source[f'Pin-carrier-{side}-{i}'];pin=source[f'Pin-{side}-{i}']
            gap=max(carrier.bounds[0,0],pin.bounds[0,0])-min(carrier.bounds[1,0],pin.bounds[1,0])
            assert abs(gap)<.002
            assert abs(carrier.volume-np.prod(carrier.extents))<.05
            contacts.append(dict(carrier=f'Pin-carrier-{side}-{i}',axis=f'Pin-{side}-{i}',
                                 modeled_axial_engagement_mm=0))
    views={}
    views['hinge-spacer']=[part('Blum-1-spacer-6',hinge)]
    views['runner-spacer']=[part('Right-runner-spacer-6-1',runner)]
    views['runner-cut']=[part('Right-runner-spacer-section',clip(runner,[20,16,-1],[50,33,7]))]
    guides=[]
    for name,dy in [('Runner-L-1',0),('Runner-R-1',42)]:
        guides.append(part(name,local[name].copy().apply_translation([0,dy,0])))
    views['guides']=guides
    for side in ('L','R'):
        meshes=[source[f'Pin-carrier-{side}-1'],source[f'Pin-{side}-1']]
        shift=-np.min([m.bounds[0] for m in meshes],axis=0)
        views[f'axis-{side.lower()}']=[part(n,m.copy().apply_translation(shift),'pin' if j else 'angle')
            for j,(n,m) in enumerate(zip([f'Pin-carrier-{side}-1',f'Pin-{side}-1'],meshes))]
    views['ledge']=[part('Display-ledge-1',local['Display-ledge-1'],'handle')]
    views['ledge-cut']=[part('Display-ledge-section',clip(local['Display-ledge-1'],[220,-1,-1],[226,50,50]),'handle')]
    views['shim']=[part('Pegboard-top-shim-97',local['Pegboard-top-shim-97'])]
    hinge_context=load_parts(ROOT/'outputs/cambusa-v30-review-fixes/hinge-detail.glb')
    views['hinge-context']=[part(n,m,'angle' if n=='Blum-1-spacer-6' else 'context') for n,m in hinge_context.items()]
    # Actual first-section geometry; neighbours are cropped for inspection.
    mechanism=[]
    for n,m in source.items():
        if n in names and n.endswith('-1') and not n.startswith('Blum-'):
            if n=='Display-ledge-1':continue
            mechanism.append(part(n,m,'pin' if n.startswith('Pin-') and not n.startswith('Pin-carrier') else 'angle'))
    context_names=['Right-wall-18','Center-18','Floor-Right-8','Shelf-Right-1',
                   'Beam-body-center','Beam-body-side-966','Beam-body-front','Beam-body-rear']
    context_names += [n for n in source if n.startswith(('Shelf-pin-Right-1-',
                      'Runner-spacer-bolt-M5x25-1-','Runner-spacer-head-M5-1-','Runner-spacer-washer-1-'))]
    for n in context_names:
        m=source[n]
        mechanism.append(part(n,clip(m,[490,22,769],[1000,501,1140]),'context',context=True))
    for p in right_leaf(1127):
        mechanism.append(part(p['name'],p['mesh'],'handle' if p['name']=='Display-ledge' else 'wood',moving=True))
    views['mechanism']=mechanism
    for key,parts in views.items():
        static=[dict(p,mesh=pose(p,1127,1,slot_end(1127))['mesh']) if p.get('moving') else p for p in parts]
        export(OUT/f'{key}.glb',static)
    data=dict(views={},geo={},tilt=6,pivotY=51,pivotZ=1075,slotStart=46,slotEnd=300)
    cache={};max_error=0
    for key,parts in views.items():
        data['views'][key]=[]
        for p in parts:
            mesh=p['mesh'];origin=mesh.bounds.mean(axis=0)
            v=np.rint((mesh.vertices-origin)*32).astype('<i2');f=mesh.faces.astype('<u2')
            assert len(mesh.vertices)<65536 and abs((mesh.vertices-origin)*32).max()<32767
            max_error=max(max_error,float(np.abs(v/32+origin-mesh.vertices).max()))
            digest=hashlib.sha256(v.tobytes()+f.tobytes()).hexdigest()
            if digest not in cache:
                cache[digest]=f'g{len(cache)}'
                data['geo'][cache[digest]]=dict(v=base64.b64encode(v.tobytes()).decode(),f=base64.b64encode(f.tobytes()).decode())
            data['views'][key].append(dict(geo=cache[digest],name=p['name'],origin=origin.tolist(),
                                           color=p['material'],moving=p.get('moving',False),context=p.get('context',False)))
    assert max_error<=1/64+.00001
    report=dict(base_model_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                part_instances=31,groups=[dict(id=k,title=v[0],quantity=v[1],dimensions=v[2],unfinished=v[3]) for k,v in GROUPS.items()],
                parts=manifest,export_readback=rechecks,viewer_maximum_vertex_error_mm=max_error,
                hinge_through_bores_verified=2,runner_blind_bores_verified=2,runner_remaining_skin_mm=.5,
                unretained_axes=contacts,factory_cubes_2069=dict(quantity=4,supplier_cad='inputs/supplier-cad/rsi-2069.step',custom_manufacturing=False),
                source_version_unchanged=True,fabrication_release=False)
    (OUT/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (OUT/'parts-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    packed=base64.b64encode(gzip.compress(json.dumps(data,separators=(',',':')).encode())).decode()
    html=(ROOT/'work/custom-parts-v30-template.html').read_text().replace('__MODEL_DATA__',packed)
    assert len(html.encode())<1_000_000
    (OUT/'viewer.html').write_text(html)
    if args.output:args.output.write_text(html)
    with ZipFile(OUT/'custom-parts-v30.zip','w',ZIP_DEFLATED) as z:
        for p in sorted((OUT/'parts').iterdir()):z.write(p,p.relative_to(OUT))
        z.write(OUT/'parts-manifest.json','parts-manifest.json')
        z.write(OUT/'review.json','review.json')
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==priced['model_sha256']
    print(json.dumps(dict(instances=31,groups=7,views=len(views),maximum_export_bounds_error_mm=max(r['maximum_bounds_error_mm'] for r in rechecks),viewer_bytes=len(html.encode()),fabrication_release=False),indent=2))


if __name__=='__main__':main()
