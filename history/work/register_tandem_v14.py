from pathlib import Path
import hashlib, json, shutil, subprocess, zipfile

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT/'outputs/cabinet-project'; FOLDER='tandem-review-v14'; src=ROOT/'outputs'/FOLDER
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def git(*args):return subprocess.check_output(['git','-c','core.hooksPath=/dev/null','-c','user.name=Cabinet archive','-c','user.email=cabinet-archive@localhost',*args],cwd=REPO,text=True).strip()
assert not git('status','--short')
old=json.loads((REPO/'SHA256SUMS.json').read_text())
historic={k:v for k,v in old.items() if k.startswith(('outputs/','references/','original-packages/','previews/'))}
assert all(sha(REPO/k)==v for k,v in historic.items())
report=json.loads((src/'ПРОВЕРКА.json').read_text())
assert sha(src/'ЯЩИК-И-НАПРАВЛЯЮЩИЕ.glb')==report['review_glb_sha256']
assert report['lock_downloads_identical'] and not report['hardware_solid_collision_proved']
assert [x['reserve_mm'] for x in report['v08_geometry_options']]==[1,5]

shutil.copytree(src,REPO/'outputs'/FOLDER)
for name in ['build_tandem_review_v14.py','register_tandem_v14.py']:shutil.copy2(ROOT/'work'/name,REPO/'work'/name)
package=ROOT/'outputs'/f'{FOLDER}.zip'
with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(src.rglob('*')):
        if p.is_file():z.write(p,Path(FOLDER)/p.relative_to(src))
with zipfile.ZipFile(package) as z:assert z.testzip() is None
shutil.copy2(package,REPO/'original-packages'/package.name)
ref=dict(id=FOLDER,title='Проверочная установка направляющих Blum TANDEM',folder=f'outputs/{FOLDER}',document='ПРОЧИТАТЬ-СНАЧАЛА.md',geometry_base='cambusa-v08',status='Контуры двух направляющих из CAD; в проверочном положении есть попадания точек CAD в дерево. Требуется подтверждение монтажной привязки и замков; присадка не выпущена.')
for name in ['CURRENT.json','versions.json']:
    p=REPO/name;d=json.loads(p.read_text());entry=d if name=='CURRENT.json' else next(v for v in d if v['id']=='cambusa-v08')
    entry['supporting_documents'].append(ref);entry['manufacturing_release']['latest_review']=FOLDER;save(p,d)
for name in ['ПРОЕКТ.md','README.md','CURRENT.md']:
    p=REPO/name;s=p.read_text()
    if name=='ПРОЕКТ.md':
        s=s.replace('Новая проверка начинается с [3D-просмотра ящика v13](outputs/drawer-proof-v13/ПРОСМОТР-3D.html). Этот узел ещё не является полным комплектом для заказа.','Актуальная проверка — [ящик с направляющими v14](outputs/tandem-review-v14/ПРОЧИТАТЬ-СНАЧАЛА.md). Присадка ящика пока не выпущена.')
        s=s.replace('| [3D-просмотр и размерные привязки ящика v13]','| [Проверка ящика с направляющими Blum](outputs/tandem-review-v14/ПРОЧИТАТЬ-СНАЧАЛА.md) | CAD обеих направляющих, проверка глубины и места возможных столкновений | tandem-review-v14 |\n| [3D-просмотр и размерные привязки ящика v13]',1)
        s=s.replace('cabinet-project-history-v13.zip','cabinet-project-history-v14.zip')
    else:
        s=s.replace('Последний пакет документов — v13','Последний пакет документов — v14')
        s+='\n[Проверка направляющих TANDEM v14](outputs/tandem-review-v14/ПРОЧИТАТЬ-СНАЧАЛА.md): CAD, глубина и точки возможных столкновений. Монтаж замков и присадка ещё не выпущены.\n'
    p.write_text(s)
p=REPO/'CATALOG.html';s=p.read_text();p.write_text(s.replace('<main>','<main><article><small>tandem-review-v14 · ящик с направляющими</small><h2>Проверка посадки Blum TANDEM</h2><p>Две направляющие из CAD. Выявлены места для проверки; полная присадка ещё не выпущена.</p><a href="outputs/tandem-review-v14/ПРОЧИТАТЬ-СНАЧАЛА.md">Результаты и модель</a></article>',1))
assert all(sha(REPO/k)==v for k,v in historic.items())
sums={str(p.relative_to(REPO)):sha(p) for p in sorted(REPO.rglob('*')) if p.is_file() and '.git' not in p.relative_to(REPO).parts and p.name not in {'SHA256SUMS.json','.DS_Store'}}
save(REPO/'SHA256SUMS.json',sums)
git('add','--all');git('commit','-m','v14: fit check of Blum TANDEM CAD against control drawer');git('tag',FOLDER)
assert not git('status','--short')
archive=ROOT/'outputs/cabinet-project-history-v14.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
    for p in sorted(REPO.rglob('*')):
        if p.is_file() and p.name!='.DS_Store':z.write(p,Path('cabinet-project')/p.relative_to(REPO))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert f'cabinet-project/.git/refs/tags/{FOLDER}' in z.namelist()
print(json.dumps(dict(version=FOLDER,commit=git('rev-parse','--short','HEAD'),preserved_files=len(historic),backup_verified=True,backup_bytes=archive.stat().st_size),ensure_ascii=False))
