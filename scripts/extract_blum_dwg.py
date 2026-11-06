"""Extract original binary ACIS streams from the public Demos DWG with LibreDWG.

Do not use dwg2dxf for this input: its SAB-to-SAT serialization is lossy.
"""
from pathlib import Path
import hashlib,json,subprocess,tempfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'inputs/supplier-cad/blum-71t6650-demos.dwg'
OUT=ROOT/'inputs/supplier-cad/demos-71t6650'

def main():
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='blum-dwg-') as tmp:
        decoded=Path(tmp)/'dwg.json'
        run=subprocess.run(['dwgread','-v0','-O','JSON','-o',str(decoded),str(SOURCE)],capture_output=True,text=True)
        assert decoded.exists(),run.stderr[-400:]
        document=json.loads(decoded.read_text())
    solids=[o for o in document['OBJECTS'] if o.get('entity')=='3DSOLID']
    assert len(solids)==7
    records=[]
    for i,o in enumerate(solids):
        fields=o['acis_data'];assert fields[0]=='ACIS BinaryFile'
        data=fields[0].encode()+bytes.fromhex(''.join(fields[1:]))
        path=OUT/f'body-{i}.sab';path.write_bytes(data)
        records.append(dict(body=i,handle=o['handle'],bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),file=str(path.relative_to(ROOT))))
    report=dict(source=str(SOURCE.relative_to(ROOT)),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        source_page='https://www.demos-trade.sk/blum-71t6650-zaves-polonalozeny-skrutka-170/',
        download_url='https://www.demos-trade.sk/product-file/download/33779',retrieved_date='2026-11-06',
        extraction='Original binary acis_data from LibreDWG JSON; no SAT translation or coordinate rounding',
        converter=subprocess.check_output(['dwgread','--version'],text=True).splitlines()[0],bodies=records)
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Extracted original binary streams:',len(records))

if __name__=='__main__':main()
