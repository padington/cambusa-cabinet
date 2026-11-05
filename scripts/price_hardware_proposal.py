"""Calculate the reviewed shopping subset; keep unpriced items explicit."""
import csv
import json
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/hardware-agreement-v1'


def main():
    proposal=json.loads((ROOT/'inputs/hardware-proposal-v1.json').read_text())
    OUT.mkdir(exist_ok=True)
    totals={}
    with (OUT/'hardware.csv').open('w',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n')
        writer.writerow(['id','supplier','sku','description','quantity','unit_price_rub','line_total_rub','url'])
        for p in proposal['items']:
            amount=Decimal(str(p['unit_price']))*p['quantity'];totals[p['id']]=amount
            writer.writerow([p['id'],p['supplier'],p['sku'],p['description'],p['quantity'],p['unit_price'],f'{amount:.2f}',p['url']])
    report=dict(proposal_status=proposal['status'],observed_on=proposal['observed_on'],
        total_priced_subset_rub=str(sum(totals.values())),
        side_panel_fasteners_rub=str(sum(v for k,v in totals.items() if k.startswith('panel-'))),
        frame_and_feet_rub=str(sum(v for k,v in totals.items() if not k.startswith('panel-'))),
        unpriced_custom_parts=proposal['custom_parts_without_price'],
        excluded_groups=proposal['outside_agreement'],
        excluded_costs=['Profile stock','Plywood','Machining','Delivery','Spares','Black coating for2069'],
        complete_cabinet_budget=False)
    (OUT/'price-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k.endswith('_rub')},ensure_ascii=False))


if __name__=='__main__':main()
