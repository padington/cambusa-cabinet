from pathlib import Path
import json, math, random, collections, html
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/layout-cost-v10';OUT.mkdir(parents=True,exist_ok=True)
raw=json.loads((ROOT/'outputs/parts-spec-v09/wood-parts-proposal.json').read_text())
SHEET=1525; MARGIN=10; GAP=8
FONT='/System/Library/Fonts/Supplemental/'
pdfmetrics.registerFont(TTFont('Arial',FONT+'Arial.ttf'))
pdfmetrics.registerFont(TTFont('ArialB',FONT+'Arial Bold.ttf'))
colors={18:'#bbd0bf',12:'#e2d5bb',9:'#c9d8e6'}
names={'B00-bottom':'Дно корпуса','B01-top':'Верх корпуса','B02-left-side':'Левая боковина','B03-right-pegboard':'Правая перфопанель','B04-back':'Задняя стенка','B05-divider':'Перегородка'}
parts=[]
for i,p in enumerate(raw):
    q=dict(p); q['number']=i+1;q['code']=f'W{i+1:02d}'
    ident=p['id'];name=names.get(ident)
    if name is None:
        if 'shelf' in ident:name='Полка'
        elif 'door' in ident:name='Дверца'
        elif ident.startswith('T'):name='Лоток: '+('дно' if 'bottom' in ident else 'передний борт' if 'lip' in ident else 'боковина')
        else:name='Ящик: '+('дно' if 'bottom' in ident else 'фасад' if 'face' in ident else 'передняя стенка' if 'front' in ident else 'задняя стенка' if 'rear' in ident else 'боковина')
    q['name']=name
    q['grain_axis']='Y' if ident in names and ident not in ['B00-bottom','B01-top'] or 'door' in ident else 'X'
    # Rotation is fixed by the outer veneer grain, never optimized away.
    q['rotated_90']=q['grain_axis']=='X'
    q['packed_w_mm']=p['blank_h_mm'] if q['rotated_90'] else p['blank_w_mm']
    q['packed_h_mm']=p['blank_w_mm'] if q['rotated_90'] else p['blank_h_mm']
    parts.append(q)

def inside(a,b):
    return a[0]>=b[0] and a[1]>=b[1] and a[0]+a[2]<=b[0]+b[2] and a[1]+a[3]<=b[1]+b[3]
def split(f,u):
    x,y,w,h=f; X,Y,W,H=u
    if X>=x+w or X+W<=x or Y>=y+h or Y+H<=y:return [f]
    res=[]
    if X>x:res.append((x,y,X-x,h))
    if X+W<x+w:res.append((X+W,y,x+w-X-W,h))
    if Y>y:res.append((x,y,w,Y-y))
    if Y+H<y+h:res.append((x,Y+H,w,y+h-Y-H))
    return res
def pack(order):
    bins=[]
    for p in order:
        w=p['packed_w_mm']+GAP;h=p['packed_h_mm']+GAP
        choices=[]
        for k,b in enumerate(bins):
            for f in b['free']:
                if w<=f[2] and h<=f[3]:choices.append((min(f[2]-w,f[3]-h),max(f[2]-w,f[3]-h),k,f))
        if choices:
            _,_,k,f=min(choices)
        else:
            k=len(bins);f=(MARGIN,MARGIN,SHEET-2*MARGIN+GAP,SHEET-2*MARGIN+GAP);bins.append({'free':[f],'parts':[]})
        u=(f[0],f[1],w,h);new=[g for r in bins[k]['free'] for g in split(r,u)]
        new=list(dict.fromkeys(new));bins[k]['free']=[r for j,r in enumerate(new) if not any(j!=l and inside(r,s) for l,s in enumerate(new))]
        bins[k]['parts'].append({**p,'x_mm':f[0],'y_mm':f[1]})
    return bins

sheets=[]
for t in [18,12,9]:
    group=[p for p in parts if p['thickness_mm']==t]
    # Deterministic heuristic. A layout is checked below, not advertised as an optimum.
    orders=[sorted(group,key=lambda p:-p['packed_w_mm']*p['packed_h_mm']),sorted(group,key=lambda p:(-p['packed_h_mm'],-p['packed_w_mm']))]
    rng=random.Random(t)
    for _ in range(80):
        o=group.copy();rng.shuffle(o);orders.append(o)
    candidates=[pack(o) for o in orders]
    best=min(candidates,key=lambda bs:(len(bs),sum(max((p['y_mm']+p['packed_h_mm'] for p in b['parts']),default=0) for b in bs)))
    for n,b in enumerate(best,1):
        b.update(id=f'S{t}-{n}',thickness_mm=t,material='ФК берёза Ш2, сорт 1/2',width_mm=SHEET,height_mm=SHEET,grain_axis='Y')
        b.pop('free');b['parts'].sort(key=lambda p:p['number']);sheets.append(b)

# Independent checks of physical rectangles, grain direction, gap and completeness.
seen=[];min_gap=9999
for s in sheets:
    for i,p in enumerate(s['parts']):
        seen.append(p['code']);x,y,w,h=[p[k] for k in ['x_mm','y_mm','packed_w_mm','packed_h_mm']]
        assert x>=MARGIN and y>=MARGIN and x+w<=SHEET-MARGIN and y+h<=SHEET-MARGIN
        assert p['thickness_mm']==s['thickness_mm']
        assert p['rotated_90']==(p['grain_axis']=='X')
        for q in s['parts'][i+1:]:
            dx=max(q['x_mm']-x-w,x-q['x_mm']-q['packed_w_mm'])
            dy=max(q['y_mm']-y-h,y-q['y_mm']-q['packed_h_mm'])
            assert dx>=GAP-1e-6 or dy>=GAP-1e-6,(p['code'],q['code'])
            min_gap=min(min_gap,max(dx,dy))
assert sorted(seen)==sorted(p['code'] for p in parts)
counts=dict(collections.Counter(s['thickness_mm'] for s in sheets));assert counts=={18:3,12:1,9:1},counts
areas={t:sum(p['blank_w_mm']*p['blank_h_mm']/1e6 for p in parts if p['thickness_mm']==t) for t in counts}
perims={t:sum(2*(p['blank_w_mm']+p['blank_h_mm'])/1000 for p in parts if p['thickness_mm']==t) for t in counts}
edge_area=sum(2*(p['blank_w_mm']+p['blank_h_mm'])*p['thickness_mm']/1e6 for p in parts)
finish_area=2*sum(areas.values())+edge_area+171*math.pi*12*18/1e6-2*171*math.pi*6**2/1e6
metrics=dict(sheet_counts=counts,part_count=len(parts),net_area_m2=areas,outer_perimeter_m=perims,finish_area_m2=finish_area,pegboard_holes=171,pegboard_hole_diameter_mm=12,pegboard_cut_m=171*math.pi*.012,margin_mm=MARGIN,contour_gap_mm=GAP,assumed_router_diameter_mm=6,checks='Все 48 деталей размещены один раз; границы, зазоры и направление волокон проверены.',production_status='Контуры для расчёта, не выпуск присадки или управляющей программы.')
(OUT/'layout.json').write_text(json.dumps(dict(metrics=metrics,sheets=sheets),ensure_ascii=False,indent=2)+'\n')
(OUT/'wood-parts.json').write_text(json.dumps(parts,ensure_ascii=False,indent=2)+'\n')

# Single priced item per purchased set. Bracket nuts/screws are not counted twice.
rows=[]
def cost(group,name,qty,unit,price,basis,url='',note='',sku=''):
    rows.append(dict(group=group,name=name,quantity=qty,unit=unit,price=price,basis=basis,url=url,note=note,sku=sku,amount=round(qty*price,2)))
NV='https://neva-torg.ru/tseny/';RS='https://www.rsi-llc.ru';LX='https://raspil78.ru/czeny/'
for t,pr in [(18,3000),(12,2350),(9,1800)]:cost('Фанера',f'ФК берёза 1/2 Ш2, {t} мм, 1525×1525',counts[t],'лист',pr,'Прайс',NV,'Лицевая сторона сорта 1; листы отбирать под видимые поверхности.')
cost('Основание','Чёрный профиль 30×30: три хлыста по 3020 мм',9.06,'м',1130,'Прайс',RS+'/catalog/69/3522/','Учтена оплата целых хлыстов, скидка за объём не применена.','OB-3030-RAL9005')
cost('Основание','Уголок 30×30',18,'шт',65,'Прайс',RS+'/catalog/73/424/','Количество проектное, узлы ещё не проверены.','1037')
cost('Основание','Чёрная покраска уголка',18,'шт',50,'Прайс',RS+'/catalog/73/424/','Опция; при закрытии крышками можно исключить.')
cost('Основание','Комплект: 2 Т-гайки 5006 + 2 винта М6×12',18,'компл',41.4,'Прайс',RS+'/catalog/73/424/','Всего 36 гаек и 36 винтов, уже включены.','5006 + ISO7380')
cost('Основание','Дополнительные Т-гайки M6 для корпуса',10,'шт',13.9,'Прайс',RS+'/catalog/85/193/','8 рабочих + 2 запасных.','5006')
cost('Основание','Запасные винты М6×12',2,'шт',6.8,'Прайс',RS+'/catalog/137/561/','Дополнение к 18 комплектам, не повтор всей партии.','ISO7380 M6×12')
cost('Основание','Чёрные крышки уголков',18,'шт',35.6,'Прайс',RS+'/catalog/158/449/','','1037cap/4050')
cost('Основание','Чёрная лента в пазы, верхний запас',30,'м',80,'Прайс',RS+'/catalog/76/','Расход уточнить после уголков; нарезка поставщиком.','4048')
cost('Основание','Торцевые заглушки 30×30',4,'шт',25,'Прайс',RS+'/catalog/157/214/','','4002')
cost('Основание','Регулируемые опоры М8×50, кандидат',4,'шт',75,'Прайс',RS+'/catalog/117/2178/','На сайте противоречие Ø30/50; установочную высоту и чертёж сверить.','D30M8H50')
cost('Основание','Контргайка опоры M8',4,'шт',1.06,'Прайс','https://tdmtdm.ru/catalog/gayki/din_439_iso_4035_gayka_nizkaya/din439_m8_gayka_nizkaya_tsink/','Фасовка при заказе требует подтверждения.','4398001 / DIN439')
cost('Основание','Потайные винты корпуса M6×25',10,'шт',6.14,'Прайс','https://oniks-krep.ru/catalog/din_7991_a2/din_7991_vint_s_potajnoj_golovkoj_vnutr_shestigr_nerzh_a2_m6x25/','8 рабочих + 2 запасных, длина уточняется под толщину.','00042770 / DIN7991')
cost('Основание','Резка 11 отрезков и снятие заусенцев',1,'заказ',1000,'Оценка',RS+'/catalog/179/','Услуга найдена, тарифа резки на сайте нет.')
cost('Основание','Резьба М8 в нижних торцах стоек',4,'шт',50,'Прайс',RS+'/catalog/179/','Проверить пригодность центрального канала и глубину под опоры.')
spec=json.loads((ROOT/'outputs/parts-spec-v09/parts.json').read_text())['rows']; byid={r['id']:r for r in spec}
for id in ['C01','C02','C04','D01']:
    p=byid[id];cost('Фурнитура',p['name'],p['planned_purchase'],p['unit'],p['published_unit_price_rub'],'Прайс',p['source_url'],p['note'],p['sku'])
# These prices are explicit budget assumptions, never vendor quotes.
for id,price in [('B01',20),('B02',15),('B03',3),('B05',4),('D04',20),('E01',30)]:
    p=byid[id];cost('Фурнитура',p['name'],p['planned_purchase'],p['unit'],price,'Оценка',p['source_url'] or '',p['note'],p['sku'])
cost('Фурнитура','Остальные шурупы, буферы, ключи и отвёртка',1,'набор',1500,'Оценка','','Строки B04, C03, C05, D02, D03, D05, E02, E03, F02 из v09; без дубля основного крепежа.')
cost('Обработка','Наружные контуры 18 мм',perims[18],'м',95,'Прайс',LX,'Сумма периметров, без общих резов и петельных отверстий.')
cost('Обработка','Наружные контуры 12 мм',perims[12],'м',80,'Оценка',LX,'Точный тариф ЧПУ 12 мм не опубликован; это принятая ставка.')
cost('Обработка','Наружные контуры 9 мм',perims[9],'м',65,'Оценка',LX,'Тариф именно для 9 мм не опубликован; это принятая ставка.')
cost('Обработка','Перфорация: 171 круг Ø12',metrics['pegboard_cut_m'],'м',95,'Прайс',LX,'Фрезеровка контуров; технологические заходы включены в подготовку ниже.')
cost('Обработка','Присадка эксцентриков',48,'компл',68,'Прайс',LX,'Проектное число, состав операции уточнить по чертежу.')
cost('Обработка','Присадка шкантов',36,'компл',31,'Прайс',LX,'Проверить, что обе сопряжённые детали включены.')
cost('Обработка','Чашки восьми петель',8,'шт',75,'Прайс',LX,'Прайс присадочных работ; на той же странице фасадная услуга стоит 100, требуется подтверждение.')
cost('Обработка','Остальные пилоты, зенковки и гнёзда',1,'заказ',4000,'Оценка',LX,'Направляющие, замки, задник, корпус к основанию, лотки, крепёж петель.')
cost('Обработка','Пазы днищ, вырезы TANDEM и ручки',1,'заказ',3000,'Оценка',LX,'Вырезы ручек уточнить под выбранную модель.')
cost('Обработка','Подготовка ЧПУ, крепление мелких деталей, пробные посадки',1,'заказ',5000,'Оценка',LX,'Включает технологические заходы, вкладки и подготовку двусторонней обработки; не сборка шкафа.')
cost('Отделка','Шлифовка, тёмная тонировка и защитное покрытие',round(finish_area,3),'м²',1700,'Оценка','https://ooo-mgrad.ru/uslugi/pokraska_mdf/','Обе пласти, торцы и стенки перфорации; точного тарифа этого заказа нет, масло/воск у цеха по запросу.')
cost('Прочее','Упаковка и доставки между поставщиками и домой',1,'заказ',5000,'Оценка','','Плановый лимит, не тариф перевозчика.')
cost('Прочее','Контрольный узел/лоток/ящик и решение устойчивости',1,'резерв',3500,'Оценка','','До полного изготовления; проект высокой тумбы физически не испытан.')
totals={g:round(sum(r['amount'] for r in rows if r['group']==g),2) for g in dict.fromkeys(r['group'] for r in rows)}
total=round(sum(r['amount'] for r in rows),2)
budget=dict(date='2026-11-03',currency='RUB',rows=rows,category_totals=totals,total=total,contingency_rate=.20,total_with_contingency=round(total*1.2,2),published_rate_subtotal=round(sum(r['amount'] for r in rows if r['basis']=='Прайс'),2),estimated_rate_subtotal=round(sum(r['amount'] for r in rows if r['basis']=='Оценка'),2),status='Плановая смета, не коммерческое предложение. Прайсы разных поставщиков; объём и состав обработки требуют подтверждения.')
(OUT/'cost-data.json').write_text(json.dumps(budget,ensure_ascii=False,indent=2)+'\n')

def txt(c,x,y,s,size=10,bold=False,color='#252a27'):
    c.setFillColor(HexColor(color));c.setFont('ArialB' if bold else 'Arial',size);c.drawString(x,y,str(s))
def arrow(c,x1,y1,x2,y2,color='#596a60'):
    c.setStrokeColor(HexColor(color));c.setLineWidth(.7);c.line(x1,y1,x2,y2)
    ang=math.atan2(y2-y1,x2-x1)
    for d in [-.45,.45]:c.line(x2,y2,x2-6*math.cos(ang+d),y2-6*math.sin(ang+d))
def dim(c,x1,y1,x2,y2,label):
    c.setStrokeColor(HexColor('#7b827d'));c.setLineWidth(.5);c.line(x1,y1,x2,y2)
    if abs(y2-y1)<1:
        c.line(x1,y1-4,x1,y1+4);c.line(x2,y2-4,x2,y2+4);c.setFont('Arial',10);c.setFillColor(HexColor('#353c36'));c.drawCentredString((x1+x2)/2,y1+5,str(label))
    else:
        c.line(x1-4,y1,x1+4,y1);c.line(x2-4,y2,x2+4,y2);c.saveState();c.translate(x1-6,(y1+y2)/2);c.rotate(90);c.setFont('Arial',10);c.drawCentredString(0,0,str(label));c.restoreState()
def header(c,title,subtitle='',portrait=False):
    w,h=A3 if portrait else landscape(A3);c.setPageSize((w,h));c.setFillColor(HexColor('#fafaf7'));c.rect(0,0,w,h,fill=1,stroke=0)
    txt(c,40,h-44,title,21,True);txt(c,40,h-69,subtitle,11)
    c.setStrokeColor(HexColor('#c6ccc6'));c.line(40,h-83,w-40,h-83)
    txt(c,40,24,'Cambusa · v10 · 03.11.2026 · мм · предварительные контуры; присадка не выпущена',9)
    txt(c,w-100,24,f'Лист {c.getPageNumber()}',9)
    return w,h
def rectpart(c,p,x,y,boxw,boxh,holes=False):
    a=p['blank_w_mm'];b=p['blank_h_mm'];scale=min((boxw-60)/a,(boxh-85)/b,.56)
    dw=a*scale;dh=b*scale;xx=x+(boxw-dw)/2;yy=y+48+(boxh-85-dh)/2
    c.setFillColor(HexColor(colors[int(p['thickness_mm'])]));c.setStrokeColor(HexColor('#41574b'));c.setLineWidth(.7);c.rect(xx,yy,dw,dh,fill=1,stroke=1)
    if holes:
        c.setFillColor(HexColor('#fafaf7'))
        for i in range(9):
            for j in range(19):c.circle(xx+(30+50*i)*scale,yy+(22+50*j)*scale,6*scale,fill=1,stroke=1)
    if p['grain_axis']=='X':arrow(c,xx+dw*.3,yy+dh*.5,xx+dw*.7,yy+dh*.5)
    else:arrow(c,xx+dw*.5,yy+dh*.3,xx+dw*.5,yy+dh*.7)
    dim(c,xx,yy-16,xx+dw,yy-16,f'{a:g}')
    dim(c,xx-16,yy,xx-16,yy+dh,f'{b:g}')
    labelsize=8 if len(p['draw_label'])>55 else 10 if len(p['draw_label'])>42 else 12
    txt(c,x+8,y+boxh-19,p['draw_label'],labelsize,True)
    txt(c,x+8,y+boxh-37,f'{p["name"]} · толщина {p["thickness_mm"]:g}',10)
    if holes:txt(c,x+8,y+5,'171 × Ø12; шаг 50; начало: X30, Y22 от нижнего левого угла',8)

pdf=canvas.Canvas(str(OUT/'Чертежи-и-раскладка-v10.pdf'),pagesize=landscape(A3))
pdf.setTitle('Cambusa v10: деревянные детали и раскладка')
w,h=header(pdf,'Деревянные детали и раскладка','1000 × 1800 × 500 мм · корпус 1000 + основание 800 · без колёс')
# Schematic elevations, indexed to the part register.
x,y,sc=100,135,.29
pdf.setStrokeColor(HexColor('#3b4b41'));pdf.setFillColor(HexColor('#e2d5bb'));pdf.rect(x,y+800*sc,1000*sc,1000*sc,fill=1,stroke=1)
for xx in [40,930]:pdf.setFillColor(HexColor('#303631'));pdf.rect(x+xx*sc,y,30*sc,800*sc,fill=1,stroke=0)
for z in [800,1782]:pdf.setFillColor(HexColor('#b6c8b6'));pdf.rect(x,y+z*sc,1000*sc,18*sc,fill=1,stroke=1)
for xx in [0,491,982]:pdf.rect(x+xx*sc,y+818*sc,18*sc,964*sc,fill=1,stroke=1)
for xx in [18,509]:
    for z in [1160,1460]:pdf.rect(x+xx*sc,y+z*sc,473*sc,18*sc,fill=1,stroke=1)
txt(pdf,x+40,y+1700*sc,'W02 · верх',10);txt(pdf,x+60,y+830*sc,'W01 · дно',10);txt(pdf,x+90,y+1210*sc,'W06',10)
for z in [828,982]:pdf.setFillColor(HexColor('#c9d8e6'));pdf.rect(x+513*sc,y+z*sc,465*sc,142*sc,fill=1,stroke=1)
dim(pdf,x,y-25,x+1000*sc,y-25,'1000');dim(pdf,x-30,y,x-30,y+1800*sc,'1800');dim(pdf,x+1000*sc+30,y,x+1000*sc+30,y+800*sc,'800');dim(pdf,x+1000*sc+30,y+800*sc,x+1000*sc+30,y+1800*sc,'1000')
txt(pdf,90,95,'Вид спереди, дверцы условно сняты',11)
sx,sy=520,135;pdf.setFillColor(HexColor('#bbd0bf'));pdf.rect(sx,sy+818*sc,468*sc,964*sc,fill=1,stroke=1)
for i in range(9):
    for j in range(19):pdf.setFillColor(HexColor('#fafaf7'));pdf.circle(sx+(30+50*i)*sc,sy+(818+22+50*j)*sc,6*sc,fill=1,stroke=0)
pdf.setFillColor(HexColor('#303631'))
for yy in [40,420]:pdf.rect(sx+yy*sc,sy,30*sc,800*sc,fill=1,stroke=0)
dim(pdf,sx,sy-25,sx+500*sc,sy-25,'500, включая дверцу и задник');txt(pdf,510,95,'Вид справа, W04',11)
notes=['В комплекте 48 деревянных деталей.', 'Фанера ФК, берёза, шлифовка с двух сторон.', '18 мм: корпус, двери, полки, перегородка.', '12 мм: задник, стенки и фасады ящиков.', '9 мм: днища ящиков и шесть дверных лотков.', '', 'Стрелки на деталях показывают рисунок шпона.', 'Размеры - заготовки до присадки и отделки.', 'Глубина боковин 468 + 20 спереди + 12 сзади = 500.', '', 'Изменения v09: накладной задник и днища в пазах.', 'Присадка стяжек, петель, направляющих и ручек', 'должна быть выпущена после проверки фурнитуры.', 'Допуски и припуски согласовать с изготовителем.', '', 'Полная ведомость, цены и источники - в смете.', 'Карта раскроя рассчитана под фрезу до 6 мм.', 'Зазор между контурами 8 мм; от края 10 мм.', 'Мелкие детали требуют технологического крепления.']
for n,s in enumerate(notes):txt(pdf,760,h-120-n*25,s,11)
pdf.showPage()

# Group identical rectangular blanks; pegboard is a separate machining type.
groups=collections.OrderedDict()
for p in parts:
    typ='peg' if p['id']=='B03-right-pegboard' else 'Верх и дно корпуса' if p['id'] in ['B00-bottom','B01-top'] else p['name']
    key=(typ,p['blank_w_mm'],p['blank_h_mm'],p['thickness_mm'],p['grain_axis'])
    groups.setdefault(key,[]).append(p)
for t in [18,12,9]:
    gs=[v for k,v in groups.items() if k[3]==t]
    w,h=header(pdf,f'Детали из фанеры {t} мм','Прямоугольные контуры и направление рисунка · размеры в мм · номера соответствуют раскладке')
    cols=3;cw=(w-90)/3;ch=310
    for n,g in enumerate(gs):
        p=dict(g[0]);p['draw_label']=', '.join(a['code'] for a in g)+f' · {len(g)} шт.'
        if len(g)>1 and p['id']=='B00-bottom':p['name']='Верх и дно корпуса'
        rectpart(pdf,p,35+(n%cols)*cw,100+(1-n//cols)*ch,cw-12,ch-12,p['id']=='B03-right-pegboard')
    txt(pdf,45,66,'Для W04: вид снаружи, нижний левый угол - база. Отверстия Ø12 сквозные. Петли и стяжки проверить на конфликт с сеткой.',10)
    pdf.showPage()

for s in sheets:
    t=s['thickness_mm'];area=sum(p['blank_w_mm']*p['blank_h_mm']/1e6 for p in s['parts']);util=area/(SHEET*SHEET/1e6)
    w,h=header(pdf,f'Раскладка {s["id"]}: фанера {t} мм',f'Лист 1525 × 1525 · {len(s["parts"])} деталей · заполнение заготовками {util:.1%}',True)
    x,y=85,430;side=670;sc=side/SHEET
    pdf.setFillColor(HexColor('#eeeae1'));pdf.setStrokeColor(HexColor('#707d72'));pdf.rect(x,y,side,side,fill=1,stroke=1)
    pdf.setDash(3,3);pdf.rect(x+MARGIN*sc,y+MARGIN*sc,(SHEET-2*MARGIN)*sc,(SHEET-2*MARGIN)*sc,fill=0,stroke=1);pdf.setDash()
    for p in s['parts']:
        xx=x+p['x_mm']*sc;yy=y+p['y_mm']*sc;ww=p['packed_w_mm']*sc;hh=p['packed_h_mm']*sc
        pdf.setFillColor(HexColor(colors[t]));pdf.setStrokeColor(HexColor('#52695c'));pdf.rect(xx,yy,ww,hh,fill=1,stroke=1)
        pdf.saveState();pdf.translate(xx+ww/2,yy+hh/2)
        if ww<60:pdf.rotate(90)
        pdf.setFont('ArialB',10);pdf.setFillColor(HexColor('#22372a'));pdf.drawCentredString(0,2,p['code']);pdf.setFont('Arial',8);pdf.drawCentredString(0,-11,f'{p["blank_w_mm"]:g}×{p["blank_h_mm"]:g}');pdf.restoreState()
    dim(pdf,x,y-22,x+side,y-22,'1525');dim(pdf,x-22,y,x-22,y+side,'1525');arrow(pdf,780,y+70,780,y+200);txt(pdf,610,405,'Рисунок шпона вдоль стрелки',10)
    txt(pdf,45,366,'Код / деталь / исходный размер / положение нижнего левого угла X,Y',11,True)
    for n,p in enumerate(s['parts']):
        col=n//13;line=n%13
        label=f'{p["code"]}  {p["name"]}  {p["blank_w_mm"]:g}×{p["blank_h_mm"]:g}  ({p["x_mm"]:g}; {p["y_mm"]:g})'
        txt(pdf,45+col*395,342-line*20,label,9)
    txt(pdf,45,61,'Зазоры 8 мм; край 10 мм. При смене фрезы, припусков, волокон или размеров нужен новый расчёт.',10)
    pdf.showPage()
    # Exact-scale SVG: mm units, bottom-left coordinate convention exported as a Y-flip.
    esc=html.escape
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1525mm" height="1525mm" viewBox="0 0 1525 1525"><title>{s["id"]} - предварительная раскладка</title><rect width="1525" height="1525" fill="#eeeae1" stroke="#666"/><g transform="translate(0 1525) scale(1 -1)">']
    for p in s['parts']:
        svg.append(f'<rect x="{p["x_mm"]}" y="{p["y_mm"]}" width="{p["packed_w_mm"]}" height="{p["packed_h_mm"]}" fill="{colors[t]}" stroke="#41574b" stroke-width="1"/>')
    svg.append('</g>')
    for p in s['parts']:
        xx=p['x_mm']+p['packed_w_mm']/2;yy=SHEET-p['y_mm']-p['packed_h_mm']/2
        rotation=f' transform="rotate(-90 {xx} {yy})"' if p['packed_w_mm']<100 else ''
        svg.append(f'<text x="{xx}" y="{yy}" text-anchor="middle" font-family="Arial" font-size="18"{rotation}>{esc(p["code"])} {p["blank_w_mm"]:g}×{p["blank_h_mm"]:g}</text>')
    svg.append('</svg>');(OUT/(s['id']+'.svg')).write_text(''.join(svg))

w,h=header(pdf,'Основание: схема отрезков','Чёрный алюминий 30 × 30, серия 30, паз 8 · схема для расчёта, узлы не выпущены')
x,y,sc=100,210,.6
pdf.setFillColor(HexColor('#313833'));pdf.setStrokeColor(HexColor('#313833'))
for xx in [0,890]:pdf.rect(x+xx*sc,y,30*sc,750*sc,fill=1,stroke=0)
pdf.rect(x,y+750*sc,920*sc,30*sc,fill=1,stroke=0);pdf.rect(x+30*sc,y,860*sc,30*sc,fill=1,stroke=0)
dim(pdf,x,y-30,x+920*sc,y-30,'920');dim(pdf,x-30,y-20*sc,x-30,y+780*sc,'800 с опорами');txt(pdf,x,160,'Вид сзади: нижняя связь сзади; спереди проход открыт.',11)
notes=['Отрезки:', '4 стойки: L = 770 - h опоры.', '3 поперечины по 860 мм.', '2 верхние продольные детали по 410 мм.', '2 нижние продольные детали по 350 мм.', '', 'h - высота от пола до торца профиля.', 'При условном h = 20 стойки 750 мм.', 'Эту длину нельзя отправлять в резку', 'до сверки опоры и контргайки.', '', 'В плане верхняя рама 920 × 410 мм.', 'Покупка для сметы: 3 хлыста × 3020 мм.', 'Запас хлыстов не требует сборки на заводе.', '', '18 уголков; 18 комплектов крепежа.', '18 крышек; 4 заглушки; 4 опоры.', '8 винтов M6×25 + 8 Т-гаек к корпусу.', '', 'Резьбу М8 в стойках делает поставщик.', 'Сборка и регулировка дома ключами.', 'Жёсткость и устойчивость ещё не испытаны.']
for n,s in enumerate(notes):txt(pdf,760,h-120-n*26,s,11,n==0)
pdf.save()

text=['# Раскладка и стоимость v10', '', '**Габариты: 100 × 180 × 50 см. Основа формы v08, размеры деревянных заготовок из предложения v09.**', '', '## Листы фанеры', '', '| Толщина | Формат | Листов | Чистая площадь деталей | Цена листа | Всего |','|---|---|---:|---:|---:|---:|']
for t,pr in [(18,3000),(12,2350),(9,1800)]:text.append(f'| {t} мм | 1525 × 1525 | {counts[t]} | {areas[t]:.3f} м² | {pr:,.0f} ₽ | {counts[t]*pr:,.0f} ₽ |')
text+=['',f'Материал: **13 150 ₽**, берёзовая ФК 1/2 Ш2 по [прайсу НеваТорг]({NV}). Сорт 1/2 выбран для более чистой видимой пласти; с обратной стороны возможны дефекты сорта 2. Визуальный отбор листов и фактическая толщина требуют подтверждения.', '', 'Три листа 18 мм нужны при заданном направлении рисунка. Семь крупных деталей длиннее половины полезной стороны листа; их ширины поперёк волокон суммарно 3248 мм против 3010 мм на двух листах. Это нижняя граница для этой ориентации, а не доказательство оптимальности для любых размеров и поворотов.', '', 'Раскладка: отступ 10 мм, зазор между контурами 8 мм, фреза до 6 мм. Проверены все 48 деталей, отсутствие наложений, зазоры, границы и направление рисунка. Карта рассчитана для ЧПУ, а не как последовательность гильотинных резов. Припуски на дополнительное шлифование или подрезку здесь не добавлены; изменение припусков требует пересчёта.', '', '## Стоимость всего комплекта', '', '| Раздел | Плановая сумма |', '|---|---:|']
for g,a in totals.items():text.append(f'| {g} | {a:,.0f} ₽ |')
text += [f'| **Итого до резерва** | **{total:,.0f} ₽** |',f'| **С резервом 20%** | **{total*1.2:,.0f} ₽** |', '', f'Из суммы до резерва {budget["published_rate_subtotal"]:,.0f} ₽ рассчитано по опубликованным ставкам, {budget["estimated_rate_subtotal"]:,.0f} ₽ - по явно помеченным допущениям. Это не подтверждённая цена заказа: количество фурнитуры и состав обработки ещё проектные. Прайсы взяты у разных поставщиков. Оплата, поставка и включение НДС проверяются в коммерческом предложении; отдельный налог сверху автоматически не добавлен.', '', f'Покрытие посчитано по обеим пластям, торцам и стенкам перфорации: около {finish_area:.2f} м² × 1700 ₽/м². Ставка отделки - наша оценка, не предложение цеха. Точный цвет подбирать на пробе рядом со столом.', '', 'В смету входят материал, обработка отдельных деталей, фурнитура, подготовка профиля, отделка, упаковка, доставка и небольшой контрольный комплект. Сборка на стороне не заложена. Не включён второй полный шкаф или масштабная переработка конструкции после испытаний.', '', '## Что есть в чертеже', '', 'Общий вид, размеры каждой группы деревянных заготовок, нумерация всех деталей, перфорация W04, пять карт раскладки и схема отрезков основания. Это чертёж контуров для обсуждения и расчёта. Присадки петель, Rastex, направляющих, крепления лотков, пазов днищ и ручек пока не выпущены, модель с ними не проверена. По одному этому PDF заказывать готовый к сборке комплект нельзя.', '', '## Основание: комплектующие', '', 'Точный список со ссылками и составом упаковок - в ОСНОВАНИЕ.md. Опоры D30M8H50 оставлены кандидатами: на сайте конфликт диаметра 30/50 мм и не подтверждена установочная высота. Длина стойки 770 минус высота опоры. 750 мм на схеме - только пример при h=20, не размер для резки.', '', '## Версии', '', 'v08 - выбранная форма; parts-v09 - подбор; layout-cost-v10 - этот расчёт раскладки и стоимости. Старые модели и документы сохранены без изменений.']
(OUT/'РАСЧЁТ.md').write_text('\n'.join(text)+'\n')
base=['# Основание: детали, крепёж и подготовка', '', 'Чёрный профиль 30 × 30, паз 8, серия 30. Размер рамы в плане 920 × 410 мм, общая высота с опорами 800 мм. Все количества проектные до проверки узлов.', '', '| Деталь / операция | Артикул | Количество к покупке | Сумма по строке | Источник |', '|---|---|---:|---:|---|']
for r in rows:
    if r['group']=='Основание':base.append(f'| {r["name"]} | {r["sku"]} | {r["quantity"]:g} {r["unit"]} | {r["amount"]:.2f} ₽ ({r["basis"]}) | [Страница]({r["url"]}) |')
base += ['', '## Не задвоить крепёж', '', '18 комплектов уголков содержат 36 винтов M6×12 и 36 Т-гаек. Дополнительно учтены только 2 запасных винта и 10 Т-гаек для 8 креплений корпуса и двух запасных. Винтов корпуса M6×25 покупаем 10: восемь рабочих и два запасных.', '', '## Отрезки', '', '- 4 стойки: 770 минус установленная высота опоры, мм.', '- 3 поперечины по 860 мм.', '- 2 верхних продольных профиля по 410 мм.', '- 2 нижних продольных профиля по 350 мм.', '', 'Под смету куплены условно три целых хлыста по 3020 мм. Покупки не выполнялись. Для примера h=20 (стойки 750): хлыст 1 - 860+860+860; хлыст 2 - 750+750+750; хлыст 3 - 750+410+410+350+350. Даже с 3 мм на каждый из 11 резов всё помещается. Реальная карта резки пересчитывается после выбора опоры.', '', '## Подготовка у поставщика', '', 'Порезать профили в согласованный размер, убрать заусенцы, подготовить резьбу М8 в четырёх нижних торцах и нарезать ленту пазов по свободным участкам. Центральный канал профиля, глубина резьбы и вкручивание опоры требуют сверки. Внутренние винты корпуса заводятся сверху через подготовленные отверстия в фанере в Т-гайки.', '', '## Открытые вопросы', '', '- D30M8H50: несогласованный диаметр на сайте и не проверенная установочная высота. Не выпускать длины стоек.', '- 18 уголков: совместимые изделия найдены, но размещение в трёхсторонних углах, доступ ключа, жёсткость и нагрузка не проверены.', '- 30 м ленты - верхний запас, не измеренный расход. Требуется нарезка поставщиком.', '- Гайки DIN439: на странице есть цена поштучно, минимальную фасовку подтвердить.', '- Крепление высокого шкафа от опрокидывания не спроектировано; резерв в смете не заменяет решения.', '', 'RSI отгружает из Челябинска, винты и контргайки найдены у продавцов СПб. Согласование поставщикам и покупка не выполнялись.']
(OUT/'ОСНОВАНИЕ.md').write_text('\n'.join(base)+'\n')
print(json.dumps(dict(sheets=counts,parts=len(parts),net_area=areas,finish_area=round(finish_area,3),cost=totals,total=total,with_reserve=round(total*1.2,2)),ensure_ascii=False))
