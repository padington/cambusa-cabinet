"""Select a preserved cabinet design without modifying any snapshot files."""
from pathlib import Path
import json,sys,datetime
ROOT=Path(__file__).resolve().parents[1]
versions=json.loads((ROOT/'versions.json').read_text())
if len(sys.argv)!=2 or sys.argv[1] not in [v['id'] for v in versions]:
    raise SystemExit('Choose one version: '+', '.join(v['id'] for v in versions))
v=next(v for v in versions if v['id']==sys.argv[1])
folder=ROOT/'outputs'/v['folder']
if not folder.is_dir():raise SystemExit('Snapshot folder is missing; nothing changed.')
state={'version':v['id'],'title':v['title'],'artifact_directory':'outputs/'+v['folder'],'dimensions':v['size'],'status':v['status'],'not_released_for_manufacture':True}
before=json.loads((ROOT/'CURRENT.json').read_text())
(ROOT/'CURRENT.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
rel='outputs/'+v['folder']
text='# Выбранная версия\n\n**'+v['id']+' — '+v['title']+'**\n\n'+v['size']+'\n\n'+v['status']+'\n\n[Все файлы]('+rel+'/)'
if v.get('model'):text+=' · [3D-модель]('+rel+'/'+v['model']+')'
preview=(folder/v['preview']).resolve()
if preview.exists():text+='\n\n![Предпросмотр]('+rel+'/'+v['preview']+')'
text+='\n\nЭто выбранный снимок формы. Актуальные требования пользователя хранятся отдельно; возврат не означает разрешения на производство.\n'
(ROOT/'CURRENT.md').write_text(text)
if before['version']!=v['id']:
    with (ROOT/'ACTIVATIONS.jsonl').open('a') as f:
        f.write(json.dumps({'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'from':before['version'],'to':v['id']},ensure_ascii=False)+'\n')
print(v['title']+'\n'+str(folder)+'\nSnapshots preserved. Current requirements were not changed.')
