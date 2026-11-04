from pathlib import Path
import json,hashlib,shutil,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT/'outputs/cabinet-project';FOLDER='drawer-proof-v13'
old=json.loads((REPO/'SHA256SUMS.json').read_text())
historical={k:v for k,v in old.items() if k.startswith(('outputs/','references/','original-packages/','previews/'))}
for rel,digest in historical.items():assert hashlib.sha256((REPO/rel).read_bytes()).hexdigest()==digest,rel
assert not subprocess.check_output(['git','status','--short'],cwd=REPO,text=True)
assert not (REPO/'outputs'/FOLDER).exists()
def savejson(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
src=ROOT/'outputs'/FOLDER;shutil.copytree(src,REPO/'outputs'/FOLDER)
for name in ['build_drawer_proof_v13.py','drawer-v13-viewer.html','register_drawer_v13.py']:shutil.copy2(ROOT/'work'/name,REPO/'work'/name)
package=ROOT/'outputs'/f'{FOLDER}.zip'
with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(src.rglob('*')):
        if p.is_file():z.write(p,Path(FOLDER)/p.relative_to(src))
shutil.copy2(package,REPO/'original-packages'/package.name)
ref=dict(id=FOLDER,title='3D-проверка деревянного ящика и размерные привязки',folder=f'outputs/{FOLDER}',document='ПРОЧИТАТЬ-СНАЧАЛА.md',geometry_base='cambusa-v08',status='50 операций и геометрия дерева проверены; реальная фурнитура и полный выпуск не готовы. Заменяет v12 как предмет проверки.')
for filename in ['CURRENT.json','versions.json']:
    p=REPO/filename;data=json.loads(p.read_text());target=data if filename=='CURRENT.json' else next(v for v in data if v['id']=='cambusa-v08')
    for r in target['supporting_documents']:
        if r['id']=='joinery-review-v12':r['status']='Отозван для изготовления после замечания владельца: недостаточны размерные привязки и проверка присадки. Сохранён только как история.'
    target['supporting_documents'].append(ref)
    target['manufacturing_release']=dict(released=False,latest_review=FOLDER,rejected_for_manufacture=['joinery-review-v12'],door_direction='Объёмные двери с хранением и врезные торцевые петли одобрены владельцем; артикул ещё не выбран')
    savejson(p,data)
reqp=REPO/'work/self-assembly-requirements.json';req=json.loads(reqp.read_text());req['updated']='2026-11-04'
req['door_direction_approved']=dict(framed_storage_doors=True,recessed_edge_hinges=True,source='Ответ владельца: Follow these doors and hinges (recommended)',exact_hinge_selected=False)
req['machining_quality_requirement']='Все отверстия и пазы сначала строятся и проверяются в 3D-сборке с фурнитурой; чертежи содержат отступы от обозначенных кромок, глубины, стороны обработки и допуски. Таблица координат и проверка только деревянных панелей недостаточны для производственного выпуска.'
savejson(reqp,req)
index=(REPO/'ПРОЕКТ.md').read_text();index=index.replace('# Проект шкафа Cambusa\n','# Проект шкафа Cambusa\n\n**Присадка v12 отозвана для изготовления.** Новая проверка начинается с [3D-просмотра ящика v13](outputs/drawer-proof-v13/ПРОСМОТР-3D.html). Этот узел ещё не является полным комплектом для заказа.\n',1)
row='| [3D-просмотр и размерные привязки ящика v13](outputs/drawer-proof-v13/ПРОЧИТАТЬ-СНАЧАЛА.md) | Выбор операции в модели; 50 вырезов, 12 пар осей, 4 оси фасада; реальная фурнитура не проверена | drawer-proof-v13 |\n'
index=index.replace('| [Пазы и отверстия контрольного ящика]',row+'| [Исторический черновик v12: не использовать для изготовления]',1)
index=index.replace('## Что добавлено в v12','## Что было добавлено в v12 (исторический черновик)')
index=index.replace('cabinet-project-history-v12.zip','cabinet-project-history-v13.zip');(REPO/'ПРОЕКТ.md').write_text(index)
readme=(REPO/'README.md').read_text().replace('Последний пакет документов — v12','Последний пакет документов — v13')
readme=readme.replace('[Открыть наглядный каталог]','**Исправление присадки v13:** [3D с выбором отверстий и отступами](outputs/drawer-proof-v13/ПРОСМОТР-3D.html) · [что проверено](outputs/drawer-proof-v13/ПРОЧИТАТЬ-СНАЧАЛА.md). Присадка v12 отозвана для изготовления. Новый узел проверен только по геометрии дерева; полного заказа ещё нет.\n\n[Открыть наглядный каталог]',1);(REPO/'README.md').write_text(readme)
catalog=(REPO/'CATALOG.html').read_text().replace('<h2>Реальные пазы и отверстия ящика</h2>','<h2>Черновик v12: отозван для изготовления</h2>',1)
card='<article><small>drawer-proof-v13 · исправление проверки присадки</small><h2>Выбор отверстия прямо в 3D</h2><p>Шесть деревянных деталей, 50 операций. Отступы, базы, сторона и глубина видны рядом с вырезом. Реальная фурнитура ещё не проверена; не для изготовления.</p><a href="outputs/drawer-proof-v13/ПРОСМОТР-3D.html">Открыть 3D и отступы</a><a href="outputs/drawer-proof-v13/ПРОЧИТАТЬ-СНАЧАЛА.md">Пределы проверки</a><a href="outputs/drawer-proof-v13/Размерные-привязки-v13.pdf">Размерные листы</a></article>'
(REPO/'CATALOG.html').write_text(catalog.replace('<main>','<main>'+card,1))
with (REPO/'CURRENT.md').open('a') as f:f.write('\n**Присадка v12 отозвана для изготовления.** [Новая 3D-проверка ящика v13](outputs/drawer-proof-v13/ПРОЧИТАТЬ-СНАЧАЛА.md). Выбор объёмных дверей с врезными петлями подтверждён владельцем; петля ещё не выбрана.\n')
with (REPO/'AGENTS.md').open('a') as f:f.write('''
## Обязательная проверка присадки после замечания владельца

- v12 отозван для изготовления: не выдавать его PDF за готовую присадку.
- Все вырезы сначала строить в общей 3D-сборке. PDF и таблицы получают те же идентификаторы операций и размеры; показывать размерные отступы от обозначенных кромок, сторону, глубину, радиусы и допуски.
- Проверка совпадения осей и отсутствия пересечений дерева не заменяет проверку реальной фурнитуры, доступа инструмента, последовательности монтажа, допусков и физического образца.
- drawer-proof-v13 содержит только деревянный контрольный ящик; замки, направляющие и их пилоты ещё не выпущены. Не называть его проверкой сборки всего шкафа.
- Владелец подтвердил объёмные двери с хранением и врезные торцевые петли по фотографиям. Точный артикул петли ещё не выбран; не переносить чашечную присадку из старого варианта.
''')
for rel,digest in historical.items():assert hashlib.sha256((REPO/rel).read_bytes()).hexdigest()==digest,rel
sums={}
for p in sorted(REPO.rglob('*')):
    rel=p.relative_to(REPO)
    if p.is_file() and '.git' not in rel.parts and p.name not in {'SHA256SUMS.json','.DS_Store'}:sums[str(rel)]=hashlib.sha256(p.read_bytes()).hexdigest()
savejson(REPO/'SHA256SUMS.json',sums)
git=['git','-c','core.hooksPath=/dev/null','-c','user.name=Cabinet archive','-c','user.email=cabinet-archive@localhost']
subprocess.run(git+['add','--all'],cwd=REPO,check=True);subprocess.run(git+['commit','-m','v13: model-linked drawer machining review; retire v12 production use'],cwd=REPO,check=True,capture_output=True);subprocess.run(git+['tag',FOLDER],cwd=REPO,check=True)
assert not subprocess.check_output(['git','status','--short'],cwd=REPO,text=True)
archive=ROOT/'outputs/cabinet-project-history-v13.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
    for p in sorted(REPO.rglob('*')):
        if p.is_file() and p.name!='.DS_Store':z.write(p,Path('cabinet-project')/p.relative_to(REPO))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None;assert f'cabinet-project/.git/refs/tags/{FOLDER}' in z.namelist()
print(json.dumps(dict(version=FOLDER,commit=subprocess.check_output(['git','rev-parse','--short','HEAD'],cwd=REPO,text=True).strip(),historical_files_unchanged=len(historical),backup_bytes=archive.stat().st_size,archive_verified=True),ensure_ascii=False))
