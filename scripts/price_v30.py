"""Price the reconciled v30 plan, separating catalogue, tariffs and allowances."""
import csv
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/cambusa-v30-costs-rf'


def main():
    plan=json.loads((OUT/'plan.json').read_text())
    source=json.loads((ROOT/'inputs/cost-v30-rf.json').read_text())
    inventory=json.loads((OUT/'model-inventory.json').read_text())
    names={p['name'] for p in inventory}
    def matched(prefix,suffix=''):
        return sorted(n for n in names if n.startswith(prefix) and n.endswith(suffix))
    model_items={
        'panel-cross-dowel':matched('Pegboard-cross-dowel-')+matched('Right-wall-cross-dowel-'),
        'panel-screw':matched('Pegboard-M6x45-')+matched('Right-wall-M6x45-'),
        'panel-washer':matched('Pegboard-washer-')+matched('Right-wall-washer-'),
        'frame-90':matched('RSI-5212::','::1'),
        'frame-straight':matched('RSI-5211::','::1'),
        'upper-cube':matched('Cube-2069-'),
        'cube-screw':matched('Cube-bolt-M8x25-'),
        'foot':matched('Levelling-foot-'),
        'foot-locknut':matched('Foot-locknut-'),
        'hinge':sorted(n for n in names if n.startswith('Blum-') and n.endswith('-cup-envelope')),
        'hinge-plate':sorted(n for n in names if n.startswith('Blum-') and n.endswith('-plate-envelope')),
        'hinge-cup-spacer':sorted(n for n in names if n.endswith('-70T3507.21-envelope'))
    }
    expected=dict(zip(model_items,[8,8,8,14,2,4,12,4,4,3,3,3]))
    assert {k:len(v) for k,v in model_items.items()}==expected
    quantities={k:len(v) for k,v in model_items.items()}
    quantities.update({f'plywood-{t}':q for t,q in plan['plywood_purchase_sheets'].items()})
    quantities.update(profile=round(plan['profile_purchase_m'],3),
                      **{'profile-saw':plan['profile_billable_cuts'],'finish':plan['surface_area_m2']})
    for t in (6,8,12,18):
        quantities[f'cnc-{t}']=sum(r['perimeter_m'] for r in plan['wood'] if r['stock_mm']==t)
    rows=[]
    for p in source['prices']:
        q=quantities.get(p['id'],1)
        amount=Decimal(str(q))*Decimal(str(p['price']))
        rows.append(dict(p,quantity=q,amount_rub=float(amount.quantize(Decimal('.01'))),
                         model_ids=model_items.get(p['id'],[])))
    totals={kind:float(sum(Decimal(str(r['amount_rub'])) for r in rows if r['type']==kind))
            for kind in ('Цена товара','Тариф','Допущение')}
    by_category={category:round(sum(r['amount_rub'] for r in rows if r['category']==category),2)
                 for category in dict.fromkeys(r['category'] for r in rows)}
    subtotal=round(sum(totals.values()),2)
    contingency=round(subtotal*source['contingency_rate'],2)
    unknown=[]
    def unpriced(code,label,ids,allowance,note):
        unknown.append(dict(id=code,description=label,quantity=None if ids is None else len(ids),
                            model_ids=ids or [],price=None,amount_rub=None,covered_by=allowance,note=note))
    unpriced('shelf-pins','Опоры полок, цилиндрические Ø6 × 20',matched('Shelf-pin-'),'allow-fixings','16 шт.; конкретный артикул и допуск ещё не утверждены')
    unpriced('hinge-plate-screws','Шурупы планок петель 3,5 × 20',sorted(n for n in names if '-plate-screw-' in n),'allow-fixings','6 шт., номинальная геометрия')
    unpriced('hinge-cup-screws','Шурупы чашек петель 3,5 × 16',sorted(n for n in names if '-cup-screw-' in n),'allow-fixings','6 шт., не подменять шурупом 3,5 × 15 из готового набора')
    unpriced('runner-screws','Винты правых проставок М5 × 25',matched('Runner-spacer-bolt-'),'allow-fixings','6 винтов; головы не считаются отдельной покупкой')
    unpriced('runner-washers','Шайбы правых проставок М5',matched('Runner-spacer-washer-'),'allow-fixings','6 шт., окончательный тип согласовать')
    unpriced('hinge-backers','Заказные алюминиевые проставки петель 51 × 24 × 6',sorted(n for n in names if n.startswith('Blum-') and n.endswith('-spacer-6')),'allow-custom','3 шт., отверстия в модели')
    unpriced('runner-backers','Заказные алюминиевые проставки 260 × 32 × 6',matched('Right-runner-spacer-'),'allow-custom','3 шт., резьбовые отверстия М5')
    unpriced('runners','Правые направляющие 260 × 8 × 16/17',matched('Runner-L-')+matched('Runner-R-'),'allow-custom','6 шт.; материал/изготовление и окончательный крепёж в работе')
    unpriced('pin-carriers','Держатели осей правых фасадов',matched('Pin-carrier-'),'allow-custom','6 шт.; три пластины толщиной 2 и три толщиной 3 мм')
    unpriced('pivot-pins','Оси правых фасадов Ø6; в модели только вылет 7 мм',matched('Pin-L-')+matched('Pin-R-'),'allow-custom','6 шт.; полная длина оси, заход в держатель и удержание не определены. Модель Ø6 × 7 не является готовой деталью для заказа')
    unpriced('display-ledges','Ручки-полочки длиной 444 мм, стенка 2 мм',matched('Display-ledge-'),'allow-custom','3 шт.; заказной профиль, материал и технология ещё не утверждены')
    unpriced('panel-shims','Прокладки панелей 18 × 20 × 1',matched('Pegboard-top-shim-')+matched('Right-wall-top-shim-'),'allow-custom','4 шт.')
    unpriced('frame-caps','Крышки кубов 2069',matched('Cube-cap-'),'upper-cube','12 шт. уже входят в покупные кубы; дополнительной стоимости нет')
    unpriced('other-fixings','Крепления верха/перегородки, рамок правых дверей и направляющих',None,'allow-fixings','Полный состав и количество ещё не утверждены; не выдавать за готовую закупочную ведомость')
    unpriced('closure-dust-tip','Фиксаторы закрывания, уплотнение и защита от опрокидывания',None,'allow-fixings','Количество зависит от окончательных узлов')
    report=dict(as_of=source['as_of'],base_tag=source['base_tag'],currency='RUB',
                model_sha256=plan['model_sha256'],items=rows,unpriced_hardware=unknown,
                type_totals=totals,category_totals=by_category,subtotal_rub=subtotal,
                contingency_rate=source['contingency_rate'],contingency_rub=contingency,
                planning_budget_rub=round(subtotal+contingency,2),
                supplier_quote_received=False,fabrication_release=False)
    (OUT/'estimate.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    for filename,data,fields in [
        ('estimate.csv',rows,['id','category','description','quantity','unit','price','amount_rub','type','supplier','url','note']),
        ('unpriced-hardware.csv',unknown,['id','description','quantity','price','amount_rub','covered_by','note'])]:
        with (OUT/filename).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');w.writeheader();w.writerows(data)
    print(json.dumps({k:report[k] for k in ('type_totals','category_totals','subtotal_rub','contingency_rub','planning_budget_rub')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
