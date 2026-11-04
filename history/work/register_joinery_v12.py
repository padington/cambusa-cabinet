from pathlib import Path
import hashlib,json,shutil,subprocess,zipfile

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT/'outputs/cabinet-project'
FOLDER='joinery-review-v12'
SRC=ROOT/'outputs'/FOLDER
old=json.loads((REPO/'SHA256SUMS.json').read_text())
historical={k:v for k,v in old.items() if k.startswith(('outputs/','references/','original-packages/','previews/'))}
for rel,digest in historical.items():
    assert hashlib.sha256((REPO/rel).read_bytes()).hexdigest()==digest,rel
assert not subprocess.check_output(['git','status','--short'],cwd=REPO,text=True)
assert not (REPO/'outputs'/FOLDER).exists()

def savejson(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

# Archive only our deliverables and the user-supplied photographs. Technical
# manuals downloaded for research stay outside the shared project snapshots.
shutil.copytree(SRC,REPO/'outputs'/FOLDER)
for name in ['build_joinery_v12.py','register_joinery_v12.py']:
    shutil.copy2(ROOT/'work'/name,REPO/'work'/name)
package=ROOT/'outputs'/f'{FOLDER}.zip'
with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(SRC.rglob('*')):
        if p.is_file():z.write(p,Path(FOLDER)/p.relative_to(SRC))
shutil.copy2(package,REPO/'original-packages'/package.name)
with zipfile.ZipFile(package) as z:assert z.testzip() is None

ref=dict(id=FOLDER,title='Пазы и отверстия контрольного ящика; новые фотографии дверей',
    folder=f'outputs/{FOLDER}',document='ПРИСАДКА.md',geometry_base='cambusa-v08',
    status='Отдельный прототип ящика; полного комплекта присадки нет. Новые рамочные двери — направление, петля не выбрана.')
for filename in ['CURRENT.json','versions.json']:
    p=REPO/filename;data=json.loads(p.read_text())
    target=data if filename=='CURRENT.json' else next(v for v in data if v['id']=='cambusa-v08')
    target.setdefault('supporting_documents',[]).append(ref);savejson(p,data)

index=(REPO/'ПРОЕКТ.md').read_text()
anchor='| [Методология подготовки и сборки]'
rows='''| [Пазы и отверстия контрольного ящика](outputs/joinery-review-v12/Пазы-и-отверстия-ящика-v12.pdf) | Шесть типов деталей с координатами обработки; отдельный прототип | joinery-review-v12 |
| [3D ящик с обработкой](outputs/joinery-review-v12/drawer-drilled.glb) · [разнесённый вид](outputs/joinery-review-v12/drawer-exploded.glb) | Отверстия, пазы и номинальные сопряжения; без реальных направляющих и замков | joinery-review-v12 |
| [Новые фотографии Cambusa Fly](outputs/joinery-review-v12/РЕФЕРЕНСЫ.md) | Двери с деревянным обрамлением и врезные петли; отдельное направление доработки | joinery-review-v12 |
'''
index=index.replace(anchor,rows+anchor,1)
index=index.replace('## Что требуется до изготовления\n','''## Что добавлено в v12

Для контрольного ящика построены отверстия стяжек, каналы штоков, отверстия шкантов, три паза дна, отверстия задних зацепов и крепление фасада. Проверено совпадение 12 пар осей и отсутствие пересечений шести деревянных деталей в собранном номинальном положении. Монтаж реальной фурнитуры и физическая сборка ещё не проверены.

В этом образце задние стенки W40/W46 уменьшены до высоты 97 мм, днища W41/W47 — до 436,6 × 318,6 мм. Наклонные пилоты замков остаются операцией по подлинному шаблону. Старые карты v10 сохранены без изменений; это пока отдельный контрольный узел.

Новые фотографии показывают двери с обрамлением и врезными торцевыми петлями. Этот вариант требует выбора петель по массе нагруженной двери и нового чертежа дверных деталей. Прежние чашечные петли нельзя автоматически переносить в него. Дополнительная пара ящиков и подсветка остаются опциями. Пять листов и смета v10 относятся к прежней конструкции и требуют пересчёта при смене дверей.

## Что требуется до изготовления
''',1)
index=index.replace('cabinet-project-history-v11.zip','cabinet-project-history-v12.zip')
(REPO/'ПРОЕКТ.md').write_text(index)

readme=(REPO/'README.md').read_text().replace('Последний пакет документов — v11','Последний пакет документов — v12')
readme=readme.replace('[Открыть наглядный каталог]',
    '**Присадка `joinery-review-v12`:** [контрольный ящик — PDF](outputs/joinery-review-v12/Пазы-и-отверстия-ящика-v12.pdf) · [3D](outputs/joinery-review-v12/drawer-drilled.glb) · [новые фото и дверное направление](outputs/joinery-review-v12/РЕФЕРЕНСЫ.md). Это отдельный узел, полный выпуск шкафа ещё не готов.\n\n[Открыть наглядный каталог]',1)
(REPO/'README.md').write_text(readme)
catalog=(REPO/'CATALOG.html').read_text()
card='''<article><small>joinery-review-v12 · контрольный узел и новые референсы</small><h2>Реальные пазы и отверстия ящика</h2><p>Шесть типов деревянных деталей с обработкой. Проверены номинальные сопряжения. Пилоты замков требуют шаблона; присадка корпуса и нового дверного варианта ещё не выпущена.</p><a href="outputs/joinery-review-v12/Пазы-и-отверстия-ящика-v12.pdf">Чертежи PDF</a><a href="outputs/joinery-review-v12/drawer-drilled.glb">3D ящика</a><a href="outputs/joinery-review-v12/РЕФЕРЕНСЫ.md">Новые фотографии и петли</a></article>'''
(REPO/'CATALOG.html').write_text(catalog.replace('<main>','<main>'+card,1))
with (REPO/'CURRENT.md').open('a') as f:
    f.write('\n[Присадка контрольного ящика v12](outputs/joinery-review-v12/ПРИСАДКА.md) · [новые фото и направление дверей](outputs/joinery-review-v12/РЕФЕРЕНСЫ.md). Выбранная общая форма остаётся v08; новые двери ещё не выпущены.\n')

for rel,digest in historical.items():
    assert hashlib.sha256((REPO/rel).read_bytes()).hexdigest()==digest,rel
checksums={}
for p in sorted(REPO.rglob('*')):
    rel=p.relative_to(REPO)
    if p.is_file() and '.git' not in rel.parts and p.name not in {'SHA256SUMS.json','.DS_Store'}:
        checksums[str(rel)]=hashlib.sha256(p.read_bytes()).hexdigest()
savejson(REPO/'SHA256SUMS.json',checksums)
git=['git','-c','core.hooksPath=/dev/null','-c','user.name=Cabinet archive','-c','user.email=cabinet-archive@localhost']
subprocess.run(git+['add','--all'],cwd=REPO,check=True)
subprocess.run(git+['commit','-m','v12: drilled control drawer and new framed-door reference study'],cwd=REPO,check=True,capture_output=True)
subprocess.run(git+['tag',FOLDER],cwd=REPO,check=True)
assert not subprocess.check_output(['git','status','--short'],cwd=REPO,text=True)

archive=ROOT/'outputs/cabinet-project-history-v12.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
    for p in sorted(REPO.rglob('*')):
        if p.is_file() and p.name!='.DS_Store':z.write(p,Path('cabinet-project')/p.relative_to(REPO))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert f'cabinet-project/.git/refs/tags/{FOLDER}' in z.namelist()
    for name in ['Cambusa_fly_0.7.jpg','Cambusa_fly_0.6.jpg','Cambusa_fly_0.9.jpg']:
        assert f'cabinet-project/outputs/{FOLDER}/references/{name}' in z.namelist()
        original=Path('./input-materials')/name
        assert hashlib.sha256(original.read_bytes()).digest()==hashlib.sha256((REPO/'outputs'/FOLDER/'references'/name).read_bytes()).digest()
print(json.dumps(dict(version=FOLDER,commit=subprocess.check_output(['git','rev-parse','--short','HEAD'],cwd=REPO,text=True).strip(),
    current_geometry='cambusa-v08',old_snapshot_files_preserved=len(historical),git_clean=True,
    backup=str(archive),backup_bytes=archive.stat().st_size,archive_verified=True),ensure_ascii=False))
