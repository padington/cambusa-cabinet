from pathlib import Path
import sys,json,math,collections,shutil
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work/vendor'))
import numpy as np
import trimesh as tm
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3,landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
OUT=ROOT/'outputs/joinery-review-v12';OUT.mkdir(exist_ok=True)
for f in ['Cambusa_fly_0.7.jpg','Cambusa_fly_0.6.jpg','Cambusa_fly_0.9.jpg']:
    dest=OUT/'references';dest.mkdir(exist_ok=True);shutil.copy2(Path('./input-materials')/f,dest/f)

# One parametric control drawer. LW is the approved 18-mm-case bay, not a
# commitment that a future framed-door cabinet will retain this exact bay.
LW=473;SIDE=12;LENGTH=340;H=110;GROOVE=3;CLEAR=.2
IW=LW-42;OW=IW+2*SIDE
BOTTOM_W=IW+2*GROOVE-2*CLEAR
BOTTOM_L=LENGTH-2*SIDE+GROOVE-2*CLEAR
DOCS={
 'rastex':'https://catalog.hettich.com/General/TuI/ru_RU/catalogs/TuI_ru_RU/pdf/save/bk_1265.pdf',
 'twister':'https://catalog.hettich.com/General/TuI/ru_RU/catalogs/TuI_ru_RU/pdf/save/bk_1267.pdf',
 'tandem':'https://d2.blum.com/services/BEC003/me16460573_ep_dok_bau_%24sru_%24aof_%24v4.pdf',
 'template':'https://www.axminstertools.com/media/downloads/505186_manual.pdf',
 'hinge':'https://d1.blum.com/services/BEC003/clp0027-td-091_td_dok_bau_%24sen_%24aof_%24v2.pdf',
 'riva':'https://www.riva1920.it/en/products/living-and-dining-furniture/display-and-storage-units/cambusa-fly',
 'hes70':'https://www.sugatsune.com/content/site-assets/201B_PDF/309.pdf'}
parts={};ops=[]
def part(key,name,w,h,t,origin,u,v,n,codes):
    parts[key]=dict(id=key,name=name,width=w,height=h,thickness=t,origin=origin,u=u,v=v,n=n,codes=codes,operations=[])
def op(p,face,kind,u,v,dia=None,depth=None,size=None,reason='',group=None,source='',status='расчёт для контрольного образца'):
    a=dict(id=f'{p}-{len(parts[p]["operations"])+1:02}',part=p,face=face,kind=kind,u=u,v=v,diameter=dia,depth=depth,size=size,reason=reason,joint=group,source=source,status=status)
    parts[p]['operations'].append(a);ops.append(a);return a
part('left','Левая боковина',340,110,12,[0,0,0],[0,1,0],[0,0,1],[1,0,0],['W37','W43'])
part('right','Правая боковина',340,110,12,[OW-12,0,0],[0,1,0],[0,0,1],[1,0,0],['W38','W44'])
part('front','Передняя стенка короба',IW,110,12,[12,0,0],[1,0,0],[0,0,1],[0,1,0],['W39','W45'])
part('rear','Задняя стенка короба',IW,97,12,[12,328,13],[1,0,0],[0,0,1],[0,1,0],['W40','W46'])
part('bottom','Дно',BOTTOM_W,BOTTOM_L,9,[12-GROOVE+CLEAR,12-GROOVE+CLEAR,13],[1,0,0],[0,1,0],[0,0,1],['W41','W47'])
part('face','Внутренний фасад',465,142,12,[-5,-12,-19],[1,0,0],[0,0,1],[0,1,0],['W42','W48'])

# Flat-bottom pockets: all stated depths are maximum recess depths, no extra
# drill-tip allowance may silently be added to a 12-mm wall.
for key in ['left','right']:
    face='B' if key=='left' else 'A'
    for end,u in [('front',6),('rear',334)]:
        for z in [55,90]:op(key,face,'bore',u,z,5,9,reason='Шток Twister DU319T 48037',group=f'{key}-{end}-{z}',source='twister')
        op(key,face,'bore',u,35,8,8,reason='Шкант 8×30; сопряжение с торцом стенки',group=f'{key}-{end}-dowel')
    op(key,face,'pocket',6,12.9,depth=3,size=[328,9.2],reason='Паз дна; концы R3. При фактической толщине дна ≠9 пересчитать ширину.',group='bottom-groove')
for key in ['front','rear']:
    face='B' if key=='front' else 'A';offset=0 if key=='front' else 13
    for end,edge,u in [('left','U0',24),('right','U1',IW-24)]:
        for z in [55,90]:
            joint=f'{end}-{key}-{z}'
            op(key,face,'bore',u,z-offset,15,10,reason='Карман Rastex15/12 9116019; центр 24 от торца',group=joint,source='rastex')
            op(key,edge,'edge_bore',0 if edge=='U0' else IW,z-offset,8,24,reason='Канал штока; ось в 6 мм от пласти A',group=joint,source='rastex')
        op(key,edge,'edge_bore',0 if edge=='U0' else IW,35-offset,8,24,reason='Шкант 8×30; ось в 6 мм от пласти A',group=f'{end}-{key}-dowel')
op('front','B','pocket',0,12.9,depth=3,size=[IW,9.2],reason='Сквозной по длине паз дна, выход в оба торца',group='bottom-groove')
for u in [60,IW-60]:
    for z in [40,90]:
        op('front','B','bore',u,z,4,12,reason='Сквозной под шуруп фасада 3,5×20',group=f'face-{u}-{z}')
        op('front','B','countersink',u,z,7,1.5,reason='Зенковка 90°; головка шурупа',group=f'face-{u}-{z}')
        op('face','B','bore',u+17,z+19,2.5,8,reason='Пилот шурупа 3,5×20; размер проверить на образце',group=f'face-{u}-{z}')
for u in [7,IW-7]:op('rear','B','bore',u,11,6,10,reason='Зацеп TANDEM: 7 от внутренней боковой грани, 11 над нижним торцом задней стенки',source='tandem',group=f'rear-hook-{u}')
op('face','B','pocket',182.5,128,depth=6,size=[100,14],reason='Предложенный фрезерованный хват сзади, открыт к верхней кромке; без покупной ручки',group='finger-pull')

holds=[
 dict(part='locking-device-mounting',quantity_per_drawer=4,operation='Наклонные пилоты замков T51.1700.04',method='В цеху по подлинному шаблону T65.1000.02 и реальным левому/правому замкам',reason='Не восстановлены координаты и наклон из однозначного производственного чертежа. Не сверлить по фотографии.',source=DOCS['template']),
 dict(part='case',operation='Пилоты направляющих',reason='Горизонтальные позиции 37/69/261 для NL350 видны в каталоге; вертикальная установка зависит от окончательной посадки ящика и нового дверного варианта.'),
 dict(part='doors',operation='Петли и крепления рамочных дверей',reason='Новые фото показывают другой тип петель и дверной конструкции. Артикул и сечение ещё не выбраны; отверстия Ø35 старого варианта не выпускаются.'),
 dict(part='trays',operation='Пилоты уголков и крепление лотков',reason='Нет согласованного монтажного рисунка конкретного уголка. Габарита 20×20×15 недостаточно для координат отверстий.')]

def base_mesh(p):
    # Axes are permuted Cartesian basis vectors, so this is exact nominal stock.
    T=np.eye(4);T[:3,:3]=np.column_stack([p['u'],p['v'],p['n']]);T[:3,3]=np.array(p['origin'])+np.array(p['u'])*p['width']/2+np.array(p['v'])*p['height']/2+np.array(p['n'])*p['thickness']/2
    return tm.creation.box(extents=[p['width'],p['height'],p['thickness']],transform=T)
def world(p,uvw):return np.array(p['origin'])+np.column_stack([p['u'],p['v'],p['n']])@np.array(uvw)
def cylinder(p,uvw,vec,r,length):
    axis=np.column_stack([p['u'],p['v'],p['n']])@np.array(vec);center=world(p,uvw)+axis*length/2
    T=tm.geometry.align_vectors([0,0,1],axis);T[:3,3]=center
    return tm.creation.cylinder(radius=r,height=length,sections=32,transform=T)
def cutter(p,a):
    u,v=a['u'],a['v'];dep=a['depth'];face=a['face'];t=p['thickness']
    if face in ['A','B']:
        start=[u,v,-.01 if face=='A' else t+.01];vec=[0,0,1 if face=='A' else -1]
    else:start=[u,v,t/2];vec=[1 if face=='U0' else -1,0,0]
    if a['kind'] in ['bore','edge_bore','countersink']:
        # Countersink is modeled as its limiting cylindrical envelope; the
        # authoritative operation table specifies the 90-degree cone.
        return cylinder(p,start,vec,a['diameter']/2,dep+.02)
    sx,sy=a['size'];localcenter=[u+sx/2,v+sy/2,dep/2 if face=='A' else t-dep/2]
    T=np.eye(4);T[:3,:3]=np.column_stack([p['u'],p['v'],p['n']]);T[:3,3]=world(p,localcenter)
    return tm.creation.box([sx,sy,dep+.02],transform=T)

meshes={}
for k,p in parts.items():
    # Recesses have nominal square-corner envelopes in this inspection mesh.
    # R3/tool compensation remains in the process requirement, not proven here.
    cut=[cutter(p,a) for a in p['operations']]
    m=tm.boolean.difference([base_mesh(p),*cut],engine='manifold') if cut else base_mesh(p)
    assert m.is_watertight and m.volume>0;kcolor=[151,111,76,255] if k!='bottom' else [184,148,107,255]
    m.visual.face_colors=kcolor;meshes[k]=m
# Verify every mating stud/dowel enters at the same world height/depth.
matches=[]
for side in ['left','right']:
    for end in ['front','rear']:
        for suffix in ['55','90','dowel']:
            joint=f'{side}-{end}-{suffix}'
            s=next(a for a in parts[side]['operations'] if a['joint']==joint)
            e=next(a for a in parts[end]['operations'] if a['joint']==joint and a['kind']=='edge_bore')
            sp=world(parts[side],[s['u'],s['v'],12 if side=='left' else 0]);ep=world(parts[end],[e['u'],e['v'],6])
            assert np.linalg.norm(sp-ep)<1e-6,(joint,sp,ep)
            matches.append(joint)
intersections=[]
ks=list(meshes)
for i,k in enumerate(ks):
    for j in ks[i+1:]:
        intersection=tm.boolean.intersection([meshes[k],meshes[j]],engine='manifold')
        if len(intersection.faces) and intersection.volume>1e-3:intersections.append([k,j,float(intersection.volume)])
assert not intersections,intersections
for exploded in [False,True]:
    scene=tm.Scene()
    shifts={'left':[-45,0,0],'right':[45,0,0],'front':[0,-55,0],'rear':[0,55,0],'bottom':[0,0,-50],'face':[0,-110,0]}
    # Export in meters with Y vertical for common GLB viewers.
    T=np.array([[.001,0,0,0],[0,0,.001,0],[0,-.001,0,0],[0,0,0,1]])
    for k,m in meshes.items():
        color=[151,111,76,255] if k!='bottom' else [184,148,107,255]
        q=tm.Trimesh(vertices=m.vertices.copy(),faces=m.faces.copy(),process=False,
                     vertex_colors=np.tile(color,(len(m.vertices),1)))
        if exploded:q.apply_translation(shifts[k])
        q.apply_transform(T);scene.add_geometry(q,node_name=k)
    (OUT/('drawer-exploded.glb' if exploded else 'drawer-drilled.glb')).write_bytes(scene.export(file_type='glb'))

checks=dict(status='Геометрический прототип, не полный производственный выпуск',case_clear_width_mm=LW,drawer_outer_mm=[OW,LENGTH,H],mating_axes_checked=len(matches),panel_intersection_count=len(intersections),watertight_parts=6,scope='Реальные отверстия и пазы в номинальной геометрии; зенковки и R3 показаны огибающими, замки и тело направляющих не моделировались.',holds=holds)
data=dict(version='joinery-review-v12',parts=list(parts.values()),operations=ops,checks=checks,sources=DOCS,copy_quantity=2)
(OUT/'operations.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
(OUT/'ПРОВЕРКИ.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')

pdfmetrics.registerFont(TTFont('Arial','/System/Library/Fonts/Supplemental/Arial.ttf'));pdfmetrics.registerFont(TTFont('ArialB','/System/Library/Fonts/Supplemental/Arial Bold.ttf'))
c=canvas.Canvas(str(OUT/'Пазы-и-отверстия-ящика-v12.pdf'),pagesize=landscape(A3));W,PH=landscape(A3)
COL={'bore':'#35688b','edge_bore':'#986033','pocket':'#56845d','countersink':'#7d5b8e'}
def text(x,y,s,size=11,bold=False,color='#2c352e'):
    c.setFont('ArialB' if bold else 'Arial',size);c.setFillColor(HexColor(color));c.drawString(x,y,str(s))
def head(title,sub):
    c.setFillColor(HexColor('#fafbf8'));c.rect(0,0,W,PH,fill=1,stroke=0);text(35,PH-40,title,20,True);text(35,PH-64,sub,11);c.setStrokeColor(HexColor('#b9c4b9'));c.line(35,PH-78,W-35,PH-78)
    text(35,22,'v12 · контрольный ящик для LW473 · 03.11.2026 · размеры мм · не полный комплект шкафа',9)
    text(W-85,22,f'Лист {c.getPageNumber()}',9)
def dimension(x1,y1,x2,y2,label):
    c.setStrokeColor(HexColor('#737e74'));c.setFillColor(HexColor('#435146'));c.setLineWidth(.6);c.line(x1,y1,x2,y2)
    if abs(y2-y1)<1:
        c.line(x1,y1-4,x1,y1+4);c.line(x2,y2-4,x2,y2+4);c.setFont('Arial',10);c.drawCentredString((x1+x2)/2,y1+5,str(label))
    else:
        c.line(x1-4,y1,x1+4,y1);c.line(x2-4,y2,x2+4,y2);c.saveState();c.translate(x1-6,(y1+y2)/2);c.rotate(90);c.setFont('Arial',10);c.drawCentredString(0,0,str(label));c.restoreState()
head('Пазы и отверстия контрольного ящика','Размер ящика 455 × 340; боковины 12; дно 9; внутренний фасад 465 × 142 × 12')
intro=[
 'Это первый узел с заданными координатами обработки. Он не заменяет присадку всего шкафа.',
 'LW473 - ширина отсека текущей версии. Если дверная конструкция изменит отсек, ящик пересчитывается.',
 'Одинаковый образец применён к двум ящикам: W37-W42 и W43-W48.',
 '',
 'Ключевые размеры',
 'Внутренняя ширина: 473 - 42 = 431. Наружная: 431 + 2 × 12 = 455.',
 'Длина боковин: NL350 - 10 = 340. Высота боковин и передней стенки: 110.',
 'Нижний просвет: 13. Задняя стенка укорочена снизу на 13: высота 97.',
 'Дно: 436,6 × 318,6. Зазор по краям 0,2; входит в два боковых и передний паз.',
 'Задняя стенка без паза. Дно заканчивается перед ней с зазором, освобождая зацепы.',
 '',
 'Как читать координаты',
 'Пласть A = w0, пласть B = w толщины. Все U,V в таблицах заданы в одной системе A.',
 'На чертеже B показана без зеркалирования: это координатная схема, не вид с обратной стороны.',
 'U0/U1 - левый/правый торец. Торцевые отверстия идут на середине толщины, w6.',
 'Глубина кармана - до плоского дна. Не добавлять длину острия сверла сверх глубины.',
 'Синие окружности - отверстия; зелёные области - пазы; фиолетовые - зенковки.',
 '',
 'Что остаётся открытым',
 'Четыре наклонных пилота замков на ящик - в цеху по T65.1000.02 и реальным замкам.',
 'Крепление направляющих в корпусе и новый тип дверных петель ещё не выпущены.',
 'Фактическая толщина фанеры и посадки должны быть проверены на одном образце.']
for n,line in enumerate(intro):text(42,PH-112-n*27,line,12,n in [4,11,18])
c.showPage()

for key,p in parts.items():
    head(', '.join(p['codes'])+' · '+p['name'],f'{p["width"]:g} × {p["height"]:g} × {p["thickness"]:g} · две одинаковые детали · U вправо, V вверх')
    scale=min(1.14,480/p['width'],220/p['height']);dw=p['width']*scale;dh=p['height']*scale
    for index,face in enumerate(['A','B']):
        x=80+index*560;y=PH-150-dh
        text(x,y+dh+22,'Пласть '+face,13,True)
        c.setFillColor(HexColor('#eadcc7'));c.setStrokeColor(HexColor('#4e5a4f'));c.rect(x,y,dw,dh,fill=1,stroke=1)
        locations=collections.defaultdict(list)
        for a in p['operations']:
            if a['face']==face:locations[(a['u'],a['v'])].append(a['id'].split('-')[-1])
        labeled=set()
        for a in p['operations']:
            if a['face']!=face:continue
            xx=x+a['u']*scale;yy=y+a['v']*scale;color=COL.get(a['kind'],'#333');c.setStrokeColor(HexColor(color));c.setFillColor(HexColor(color));c.setLineWidth(.8)
            if a['size']:
                sx,sy=a['size'];c.setFillAlpha(.25);c.rect(xx,yy,sx*scale,sy*scale,fill=1,stroke=1);c.setFillAlpha(1)
            else:c.circle(xx,yy,a['diameter']/2*scale,fill=0,stroke=1)
            loc=(a['u'],a['v'])
            if loc not in labeled:
                text(xx+4,yy+4,'/'.join(locations[loc]),8,color=color);labeled.add(loc)
        # Project the end-drilled bores on the face opposite the cam pockets.
        # This is a hidden-line plan projection; the table fixes w=6.
        if key in ['front','rear'] and face==('A' if key=='front' else 'B'):
            for a in p['operations']:
                if a['kind']!='edge_bore':continue
                xx=x+a['u']*scale;yy=y+a['v']*scale
                endx=xx+(1 if a['face']=='U0' else -1)*a['depth']*scale
                c.setStrokeColor(HexColor(COL['edge_bore']));c.setDash(3,2)
                c.rect(min(xx,endx),yy-a['diameter']*scale/2,abs(endx-xx),a['diameter']*scale,fill=0,stroke=1);c.setDash()
                text(min(xx,endx)+3,yy+7,a['id'].split('-')[-1],8,color=COL['edge_bore'])
            text(x,y+dh+7,'Торцевое сверление: проекция, ось w6',8)
        text(x+3,y+3,'0',7)
        dimension(x,y-17,x+dw,y-17,f'{p["width"]:g}');dimension(x-18,y,x-18,y+dh,f'{p["height"]:g}')
    y=PH-435
    text(42,y,'Операции · номера на схеме',12,True);y-=24
    header=['№','Сторона','U','V','Диаметр / размер','Глубина','Назначение'];xs=[42,85,155,215,280,420,505]
    for x,s in zip(xs,header):text(x,y,s,10,True)
    y-=19
    for a in p['operations']:
        size=f'{a["diameter"]:g}' if a['diameter'] is not None else ' × '.join(f'{n:g}' for n in a['size'])
        row=[a['id'].split('-')[-1],a['face'],f'{a["u"]:g}',f'{a["v"]:g}',size,f'{a["depth"]:g}',a['reason']]
        for x,s in zip(xs,row):text(x,y,s,9)
        y-=14
    if key=='front':text(42,59,'Пилоты замков: отдельно по шаблону T65.1000.02. Их координаты в этой карте не придуманы.',10,True,color='#8a522d')
    elif key=='bottom':text(42,59,'У дна нет отдельных сверлений. Контур уменьшен относительно v10; паз в задней стенке отменён.',10)
    elif key=='rear':text(42,59,'Снизу просвет 13 по всей ширине. Центры зацепов V11 относительно нового нижнего торца.',10)
    c.showPage()
c.save()

readme='''# Присадка и новые референсы

В v10 были только заготовки и перфорация. В этом выпуске появился отдельный контрольный ящик с отверстиями Rastex, каналами штоков, отверстиями шкантов, пазами дна, отверстиями задних зацепов и креплением внутреннего фасада. Это отдельный узел, а не производственный комплект шкафа.

## Что открыть

- [Пазы и отверстия ящика](Пазы-и-отверстия-ящика-v12.pdf).
- [3D ящик с обработкой](drawer-drilled.glb) и [разнесённые детали](drawer-exploded.glb).
- [Все координаты и стороны обработки](operations.json).
- [Проверки геометрии и открытые операции](ПРОВЕРКИ.json).
- [Разбор новых фотографий](РЕФЕРЕНСЫ.md).

## Изменения относительно v10

Задние стенки W40 и W46 имеют высоту 97 вместо 110 мм; их нижние торцы подняты на 13 мм. Днища W41 и W47: 436,6 × 318,6 вместо 437 × 322 мм. Дно удерживается тремя пазами; задняя стенка без паза и не мешает задним зацепам. Существующая закупка материала пока не увеличивается: новые контуры меньше прежних, но окончательная раскладка требует синхронизации.

Принятый для образца паз 9,2 × 3 мм рассчитан на фактическое дно 9 мм. Это наша посадка с зазором, её нужно проверить на образце после отделки. Хват внутреннего фасада предлагается фрезеровать сзади у верхнего края, 100 × 14 × 6 мм; покупная ручка для него не требуется.

Ширина отсека LW473 относится к текущему корпусу с фанерой 18 мм. Новый вариант рамочных дверей может изменить ширину отсека; тогда ширина ящика, днища и фасада пересчитывается. Старые файлы не исправляются задним числом.

## Что ещё не выпущено

Четыре наклонных пилота замков на ящик предусмотрены как операция по подлинному шаблону Blum T65.1000.02 и реальным замкам в цеху. Их числовых координат здесь нет. Не выпущены присадка направляющих в корпусе, новые дверные петли и конкретные крепления лотков. Нельзя передавать этот файл как полный комплект для изготовления шкафа.

## Основания размеров

Rastex 15/12: Ø15, глубина 10; канал штока Ø8; ось в 6 от пласти. Для Twister DU319T 20 центр эксцентрика находится в 24 от торца; отверстие под резьбу Ø5 глубиной 9. Это подтверждено отдельными листами Hettich. Привязки по высоте и расстояния между соединениями — наша компоновка.

TANDEM 560H: длина короба NL−10, внутренняя ширина LW−42; утопление дна 12–15. Для задних зацепов Ø6 глубиной 10, 7 от внутренней боковой грани и 11 над нижним торцом укороченного задника. Раскладка стенок и крепление дна в трёх пазах — наша конструкция контрольного образца.

Источники: [Hettich Rastex](https://catalog.hettich.com/General/TuI/ru_RU/catalogs/TuI_ru_RU/pdf/save/bk_1265.pdf), [Hettich Twister](https://catalog.hettich.com/General/TuI/ru_RU/catalogs/TuI_ru_RU/pdf/save/bk_1267.pdf), [Blum TANDEM](https://d2.blum.com/services/BEC003/me16460573_ep_dok_bau_%24sru_%24aof_%24v4.pdf), [инструкция к шаблону Blum](https://www.axminstertools.com/media/downloads/505186_manual.pdf).

Геометрическая проверка подтвердила совпадение 12 пар осей соединений и отсутствие пересечений шести деревянных деталей в номинальном собранном положении. Она не проверяла материал, прочность, физическую посадку, реальные замки, корпус направляющих, монтаж с инструментом или кинематику дверей. В GLB зенковки и окончания пазов показаны цилиндрическими и прямоугольными огибающими; радиусы и углы берутся из технологической карты.
'''
(OUT/'ПРИСАДКА.md').write_text(readme)
refs='''# Новые фотографии Cambusa Fly

## Что видно на фотографиях

Двери имеют деревянное обрамление и глубину для хранения. Петли утоплены в торцы деревянных деталей и отличаются от накладных чашечных Blum 71B7550, выбранных в прежнем эскизе. Точный изготовитель и артикул по фотографии не установлены.

В показанном интерьере две стопки ящиков, по два с каждой стороны. Есть сплошная задняя стенка и вертикальная центральная перегородка. На освещённом общем виде видна вертикальная полоса света. Полки дверей и держатели бокалов закреплены в деревянной рамочной конструкции. По снимкам нельзя снять размеры пазов или толщину деталей без масштаба.

![Петли и внутренние детали](references/Cambusa_fly_0.7.jpg)

![Общий вид с освещением](references/Cambusa_fly_0.6.jpg)

![Общий вид без освещения](references/Cambusa_fly_0.9.jpg)

## Что это меняет для нашего проекта

Следующий дверной вариант следует разрабатывать с рамочными дверями и врезными петлями, сохраняя выбранные внешние пропорции. Это рабочее направление по референсам, не утверждённый артикул. Форма v08 остаётся сохранённой. Старые чашечные петли и планки больше нельзя автоматически переносить в новую присадку.

Сначала выбираем совместимую с толщиной дерева и полной массой нагруженной двери петлю, затем проектируем её карманы, рамку и соединения. Фотография не даёт оснований назначать скрытой петле отверстие Ø35: такие отверстия относятся к прежним чашечным петлям.

Как пример этого класса проверена Sugatsune HES3D-70: минимальная толщина двери 19 мм; у нас в старом варианте 18 мм. Поэтому это не прямая замена. Нужны другой артикул или новое сечение рамки; грузоподъёмность выбирается с учётом двери и содержимого. Точная модель петель Riva неизвестна.

Дополнительная пара ящиков, подсветка и держатели бокалов записаны как возможные опции. Они пока не добавлены к нашей закупке автоматически. Старые пять листов и смета относятся к варианту v10 и требуют пересчёта при смене конструкции дверей.

## Проверка описания оригинала

Фабрика Riva 1920 указывает для Cambusa Fly корпус из столярной плиты blockboard, ящики из массива с соединением «ласточкин хвост», железное основание, двери с хранением и автоматическую LED-подсветку. Берёзовая фанера и разборный алюминий — наши способы изготовления комплекта для самостоятельной сборки. Столярная плита не равна берёзовой фанере.

Размеры фабрики указаны как 90/180,6 × 52,2 × 180 см; наша выбранная ширина 100 см и глубина 50 см — адаптация. Точная марка петель и их присадка на странице фабрики не опубликованы. Угол 180° нельзя подтверждать одним общим описанием другой модели Cambusa.

Источники: [Riva 1920](https://www.riva1920.it/en/products/living-and-dining-furniture/display-and-storage-units/cambusa-fly), [технический лист Sugatsune HES3D-70](https://www.sugatsune.com/content/site-assets/201B_PDF/309.pdf). Фотографии предоставлены пользователем и сохранены без изменений.
'''
(OUT/'РЕФЕРЕНСЫ.md').write_text(refs)
print(json.dumps({'sample_parts':len(parts),'operations_per_drawer':len(ops),'mating_axes_checked':len(matches),'intersections':intersections,'bottom_size':[BOTTOM_W,BOTTOM_L],'status':'prototype; locking-device pilots and cabinet/door machining still open'},ensure_ascii=False))
