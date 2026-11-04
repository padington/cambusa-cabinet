from pathlib import Path, PurePosixPath
import json, shutil, subprocess, hashlib, zipfile, html, sys

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'outputs/cabinet-project'
VIS=Path('./previews')
VERSIONS=[
 dict(id='round-v01',title='Узкая тумба с круглыми соединителями',folder='round-cabinet',size='400 × 1200 × 350 мм',status='Исходный эскиз и образцы посадки',preview='../../work/cabinet-closed.png',model='cabinet-concept.glb'),
 dict(id='visual-sketches-v01',title='Ранние скосы и сферические узлы',folder='early-visual-sketches',size='По параметрам ранних эскизов',status='Иллюстрации формы, без производственной геометрии',preview='sloped-cabinet-concept-v01.png',model=None),
 dict(id='six-concepts-v01',title='Шесть вариантов формы',folder='cabinet-six-concepts',size='Ширина 1000 мм; варианты пропорций',status='Изображения для выбора направления',preview='03-offset.png',model=None),
 dict(id='engineering-v01',title='Смещённые ячейки и ступень — узлы с винтами',folder='cabinet-03-04-engineering-v1',size='1000 × 1200 × 350 мм',status='Исследование конструкции и пробного узла',preview='assembled.png',model='models/variant-03-assembled.glb'),
 dict(id='bayonet-v02',title='Шаровой узел с поворотным ключом',folder='sphere-bayonet-v02',size='Отдельный узел',status='Геометрический прототип, физически не испытан',preview='mechanism-overview.png',model='assembled.glb'),
 dict(id='boltfree-v03',title='Шаровые узлы без металлических стяжек корпуса',folder='boltfree-cabinet-v03',size='1000 × 1200 × 350 мм',status='Архив отвергнутого направления с крупными шарами',preview='assembled.png',model=None),
 dict(id='mobile-v04',title='Колёса: скосы, алюминий или клинья',folder='mobile-cabinet-options-v04',size='1000 × 1200 × 350 мм',status='Три эскизных варианта; прежние допущения о сборке не действуют',preview='comparison.png',model='aluminium.glb'),
 dict(id='cambusa-v05',title='Лотки, ящики и полная перфорация боковины',folder='cambusa-pegboard-v05',size='1000 × 1200 × 500 мм',status='Эскиз; схема предварительной сборки на стороне отменена',preview='comparison.png',model='inside-open.glb'),
 dict(id='order-v06',title='Комплект отдельных деталей для расчёта',folder='order-preparation-v06',size='1000 × 1200 × 500 мм',status='Сметные контуры; присадка не выпущена',preview='open.png',model='open.glb'),
 dict(id='cambusa-v07',title='Высокая Cambusa: закрытый корпус и две дверцы',folder='cambusa-direction-v07',size='1000 × 1800 × 500 мм',status='Текущий эскиз; ключ или отвёртка разрешены',preview='open.png',model='open.glb'),
]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def git(*args):
    return subprocess.run(['git','-c','core.hooksPath=/dev/null','-c','user.name=Cabinet archive','-c','user.email=cabinet-archive@localhost',*args],cwd=PROJECT,check=True,capture_output=True,text=True).stdout.strip()
def commit(message):git('add','--all');git('commit','-m',message)
def current(v):
    return {'version':v['id'],'title':v['title'],'artifact_directory':'outputs/'+v['folder'],'dimensions':v['size'],'status':v['status'],'not_released_for_manufacture':True}

def main():
    if PROJECT.exists():raise SystemExit('Archive already exists. Refusing to overwrite saved history.')
    PROJECT.mkdir(parents=True)
    git('init','-b','main')
    (PROJECT/'.gitignore').write_text('.DS_Store\n__pycache__/\n*.pyc\nwork/vendor/\nrestored/\n')
    (PROJECT/'ARCHIVE-NOTE.txt').write_text('Локальный архив сессии, создан 3 ноября 2026.\nИстория реконструирована из сохранившихся файлов. До этого Git-история проекта не велась.\nТеги фиксируют сохранённые варианты, а не первоначальное время их создания.\nНи один вариант не выпущен в полное производство. Старые документы сохраняются дословно; актуальные требования находятся в CURRENT.json и work/self-assembly-requirements.json.\n')
    commit('Initialize local cabinet archive')
    originals=ROOT/'outputs'
    snapshots=[]
    for v in VERSIONS:
        dest=PROJECT/'outputs'/v['folder']
        if v['folder']=='early-visual-sketches':
            dest.mkdir(parents=True)
            for p in originals.glob('*concept-v01*'):
                if p.is_file():shutil.copy2(p,dest/p.name)
        else:shutil.copytree(originals/v['folder'],dest)
        # Preserve each existing delivered ZIP, including original contents.
        zip_names={'round-v01':['round-cabinet-v01.zip'],'six-concepts-v01':['cabinet-six-concepts-v01.zip'],'engineering-v01':['cabinet-03-04-engineering-v1.zip'],'bayonet-v02':['sphere-bayonet-v02.zip'],'boltfree-v03':['boltfree-cabinet-v03.zip','boltfree-pilot-v03.zip'],'mobile-v04':['mobile-cabinet-options-v04.zip'],'cambusa-v05':['cambusa-pegboard-v05.zip'],'order-v06':['order-preparation-v06.zip']}.get(v['id'],[])
        for name in zip_names:
            target=PROJECT/'original-packages'/name;target.parent.mkdir(exist_ok=True);shutil.copy2(originals/name,target)
        # The small pilot package existed only as a ZIP. Unpack a separate view.
        if v['id']=='boltfree-v03':
            with zipfile.ZipFile(originals/'boltfree-pilot-v03.zip') as z:
                for info in z.infolist():
                    rel=PurePosixPath(info.filename)
                    if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe archive member')
                    if info.is_dir():continue
                    p=PROJECT/'outputs'/Path(*rel.parts);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(info))
        # Pick an actual existing model path; do not leave catalog links guessed.
        if v['model'] and not (dest/v['model']).exists():
            models=sorted(dest.rglob('*.glb'))
            v['model']=str(models[0].relative_to(dest)) if models else None
        snapshots.append(v.copy())
        (PROJECT/'CURRENT.json').write_text(json.dumps(current(v),ensure_ascii=False,indent=2)+'\n')
        commit('Preserve '+v['id']+' — '+v['title'])
        git('tag','-a',v['id'],'-m',v['title']+'; restored snapshot, not a production release')
    # Source and research files are present-day copies, not invented past revisions.
    for p in (ROOT/'work').iterdir():
        if p.is_file() and p.suffix in ['.py','.json','.html','.cjs','.txt','.md','.png']:
            dst=PROJECT/'work'/p.name;dst.parent.mkdir(exist_ok=True);shutil.copy2(p,dst)
    for name in ['assembly-v1','decision-history']:
        p=ROOT/'work'/name
        if p.exists():shutil.copytree(p,PROJECT/'work'/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for p in VIS.glob('*.html'):
        dst=PROJECT/'previews'/p.name;dst.parent.mkdir(exist_ok=True);shutil.copy2(p,dst)
    # Explicit user-supplied image paths only; no sweep of the temporary directory.
    temp=Path('/var/folders/dl/4phcx44j6ts069blpwfnmjj40000gn/T')
    images=[f'IMAGE 2026-11-03 09:44:{n}.jpg' for n in ['29','31','33']]+[f'IMAGE 2026-11-03 09:55:{n}.jpg' for n in ['18','19','21','22','23']]+['codex-clipboard-2a755bb8-1742-4bdf-8124-d317b79aacac.png','codex-clipboard-b188c602-ee95-45a2-b671-dc5546c57465.png']
    refs=[]
    for name in images:
        p=temp/name;row={'original_filename':name,'preserved':p.exists()}
        if p.exists():
            dst=PROJECT/'references/images'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst);row['sha256']=sha(dst)
        refs.append(row)
    (PROJECT/'references/image-manifest.json').write_text(json.dumps(refs,ensure_ascii=False,indent=2)+'\n')
    (PROJECT/'references/links.txt').write_text('Референсы пользователя, без утверждения о доступности всех публикаций:\nhttps://www.instagram.com/reel/DeNH8KUxL0F/\nhttps://www.instagram.com/reel/DQRs9qPiD78/\nhttps://www.instagram.com/p/DdYVaM4irWC/\nhttps://www.instagram.com/reel/DeH7xiDxZNn/\nhttps://www.instagram.com/domj0hnson/\nhttps://www.instagram.com/greg.dean.mann/\nhttps://www.instagram.com/reel/DMUpQAet0EN/\nhttps://www.instagram.com/reel/DMUqrTBt7dS/\nhttps://www.instagram.com/p/DUC9AhtCOgn/\nhttps://www.instagram.com/p/DUDbeApl1VM/\nhttps://www.instagram.com/guillaume_jandin/\nhttps://www.riva1920.it/ru/produkty/mebel-dlya-dnevnoj-zony/mebel-dlya-khraneniya\nhttps://www.riva1920.it/ru/produkty/mebel-dlya-dnevnoj-zony/knizhnye-shkafy\nhttps://www.riva1920.it/it/prodotti/mobili-zona-giorno/mobili-contenitori/cambusa-fly\n')
    (PROJECT/'versions.json').write_text(json.dumps(snapshots,ensure_ascii=False,indent=2)+'\n')
    # The activation utility writes only a pointer and a change log. Snapshots stay intact.
    tools=PROJECT/'tools';tools.mkdir()
    shutil.copy2(ROOT/'work/activate_cabinet_version.py',tools/'activate_version.py')
    rows=[]
    for v in reversed(snapshots):
        d='outputs/'+v['folder']
        model=f' · [3D]({d}/{v["model"]})' if v['model'] else ''
        rows.append(f'| `{v["id"]}` | [{v["title"]}]({d}/) {model} | {v["size"]} | {v["status"]} |')
    (PROJECT/'README.md').write_text('# Шкаф — каталог версий\n\nТекущая версия: **cambusa-v07**, ширина 100, высота с колёсами 180, глубина 50 см. Ключ или отвёртка разрешены; все детали заказываются подготовленными, всю сборку выполняет пользователь.\n\n[Открыть наглядный каталог](CATALOG.html) · [Текущие решения](CURRENT.json) · [Исходные требования](work/self-assembly-requirements.json)\n\n![Текущая Cambusa](outputs/cambusa-direction-v07/open.png)\n\n| Версия / тег | Что сохранено | Ш × В × Г | Статус |\n|---|---|---|---|\n'+'\n'.join(rows)+'\n\n## Как вернуться к варианту\n\nДостаточно написать в этом чате: **«Верни mobile-v04»** или назвать вариант словами. Старые файлы сохранены отдельно; возврат меняет указатель текущей версии, не удаляя другие варианты. Следующие доработки получают новый номер и новый коммит.\n\nДля самостоятельного переключения: `python3 tools/activate_version.py mobile-v04`. Утилита проверяет имя, показывает путь к файлам и меняет CURRENT.json; исходные снимки не редактирует. Само переключение не возвращает старые требования автоматически: актуальная высота и разрешённые инструменты хранятся отдельно. Изменения можно зафиксировать в Git.\n\n## Что есть в архиве\n\nОтдельные модели GLB, STL и OpenSCAD, картинки, контуры DXF/SVG, ведомости CSV, результаты проверок, исходники генераторов, подборки поставщиков СПб и референсов, снимки интерактивных просмотров и оригинальные ZIP, которые выдавались в чате. 3D-модели каждого варианта лежат в соответствующей папке.\n\nЭто восстановленная история сохранившихся файлов сессии: Git создан сейчас, точные прошлые состояния исходников до этого не фиксировались. `work/` содержит исходники в состоянии на момент архивации; в них есть исходные пути рабочей сессии. Старые тексты сохранены без переписывания и могут содержать отменённые решения. Их текущий статус указан в таблице.\n\nНи одна версия не является полным комплектом для заказа в производство. Проверки геометрии не заменяют подбор крепежа, физическую сборку, испытание нагрузки и проверку устойчивости высокой тумбы на колёсах.\n\n## Техническое восстановление\n\nКаждому варианту соответствует отдельный Git-тег. Все операции сохранены локально, удалённых репозиториев нет. Файл `SHA256SUMS.json` содержит контрольные суммы сохранённых файлов; папка `.git` входит в резервный ZIP. Для независимого экспорта снимка можно использовать `git archive <тег> outputs/<папка-версии>`.\n\nИсходники воспроизводят геометрию только при установленном совместимом Python и библиотеках numpy, trimesh, manifold3d, shapely, mapbox-earcut, Pillow. Библиотеки и интерпретатор не включены. Готовые GLB/STL/PNG не требуют этого окружения для просмотра.\n')
    cards=[]
    for v in reversed(snapshots):
        d='outputs/'+v['folder'];preview=(PROJECT/d/v['preview']).resolve()
        image=f'<img loading="lazy" src="{html.escape(d+"/"+v["preview"])}" alt="{html.escape(v["title"])}">' if preview.exists() else ''
        model=f'<a href="{html.escape(d+"/"+v["model"])}">3D-модель GLB</a>' if v['model'] else ''
        cards.append(f'<article>{image}<small>{v["id"]}</small><h2>{v["title"]}</h2><p>{v["size"]}</p><p>{v["status"]}</p>{model} <a href="{d}/">Все файлы</a></article>')
    (PROJECT/'CATALOG.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Шкаф — версии</title><style>body{font:16px/1.5 system-ui,sans-serif;max-width:1200px;margin:40px auto;padding:0 20px;color:#292c29;background:#f6f5f1}h1{font-size:30px}h2{font-size:20px;font-weight:500}a{color:#285a71;margin-right:12px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px}article{background:#fff;padding:20px;border:1px solid #deded8;border-radius:8px}img{width:100%;height:280px;object-fit:contain;background:#f6f5f1}small{color:#656b64}p{margin:8px 0}header{margin-bottom:28px}</style><header><h1>Шкаф — сохранённые версии</h1><p>Текущая: <b>cambusa-v07 · 100 × 180 × 50 см</b>. Ключ или отвёртка допустимы.</p><p>Для возврата напиши название версии в чат. Снимки сохраняются отдельно. Все версии пока дорабатываются перед производством.</p><a href="README.md">Описание архива и восстановления</a></header><main>'+''.join(cards)+'</main></html>')
    files={str(p.relative_to(PROJECT)):sha(p) for p in sorted(PROJECT.rglob('*')) if p.is_file() and '.git' not in p.relative_to(PROJECT).parts and p.name!='SHA256SUMS.json'}
    (PROJECT/'SHA256SUMS.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n')
    commit('Catalog all versions, preserve references and sources; current Cambusa 180 cm')
    git('tag','-a','session-2026-11-03','-m','Complete local archive, current Cambusa v07')
    git('gc','--quiet')
    git('fsck','--full')
    if git('status','--porcelain'):raise AssertionError('Archive worktree is not clean')
    # Actually recover an earlier GLB from a tagged commit and compare its bytes.
    rel='outputs/mobile-cabinet-options-v04/aluminium.glb'
    recovered=subprocess.run(['git','show','mobile-v04:'+rel],cwd=PROJECT,check=True,capture_output=True).stdout
    assert hashlib.sha256(recovered).hexdigest()==sha(originals/'mobile-cabinet-options-v04/aluminium.glb')
    assert all(sha(PROJECT/p)==digest for p,digest in files.items())
    report={'date':'2026-11-03','versions':len(snapshots),'tags':git('tag','--list').splitlines(),'preserved_files':len(files),'preserved_user_images':sum(x['preserved'] for x in refs),'checksums_verified':True,'git_fsck':'passed','tagged_glb_restore_sha256_matches':True,'current_version':'cambusa-v07'}
    (ROOT/'work/cabinet-archive-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    zip_path=ROOT/'outputs/cabinet-project-history.zip'
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(PROJECT.rglob('*')):
            if p.is_file():z.write(p,Path('cabinet-project')/p.relative_to(PROJECT))
    with zipfile.ZipFile(zip_path) as z:assert z.testzip() is None
    print(json.dumps({**report,'zip_bytes':zip_path.stat().st_size},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
