from pathlib import Path
import math,sys,json
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'work/vendor'))
from build_bayonet_node import build,pin_transform,cube,diff,d,e,c,OUT
from render_assembly_v1 import render,COLORS
COLORS['key']=[181,104,51,255]
ms=build();BG='#f6f5f1';FG='#252e29';MUTED='#57635b';ACCENT='#ae6638'
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'
def font(s):return ImageFont.truetype(FONT,s)
def parts(mode):
    ps=[]
    for name in ['shelf','divider','body','key']:
        mesh=ms[name].copy()
        if mode=='removed' and name=='key':mesh=pin_transform(mesh,-90,-60)
        if mode=='section' and name!='key':mesh=diff(mesh,[cube([-120,-130,-100],[120,0,170])])
        if name in ['shelf','divider']:mesh=diff(mesh,[cube([-150,65,-100],[150,150,170]),cube([-150,-100,87],[150,150,170])])
        ps.append(dict(name='partition' if name=='divider' else name,mesh=mesh,material='wood' if name in ['shelf','divider'] else 'node' if name=='body' else 'key'))
    return ps
canvas=Image.new('RGB',(1600,1440),BG);dr=ImageDraw.Draw(canvas)
dr.text((40,26),'Шар + поворотный ключ',font=font(42),fill=FG)
dr.text((40,83),'Пробный узел: Ø90 мм / фанера 18 мм / 2 печатные детали / 0 болтов',font=font(26),fill=MUTED)
titles=['1. Панели вставлены в шар','2. Один ключ проходит через обе панели','3. Разрез: ключ соединяет дерево и шар']
for i,mode in enumerate(['assembled','removed','section']):
    x=(i%2)*800;y=140+(i//2)*590
    dr.text((x+35,y),titles[i],font=font(26),fill=FG)
    im=render(parts(mode),width=800,height=480,yaw=47 if mode!='section' else 17,pitch=13 if mode!='section' else 13)
    canvas.paste(im,(x,y+43))
    captions={'assembled':['Печатный корпус задаёт угол 90°.','Пазы в фанере дают деревянную опору.'],
              'removed':['Ключ показан оранжевым для наглядности.','В рабочем узле его можно сделать в цвет шара.'],
              'section':['Ключ удерживает панели через заранее сделанные окна.','Передняя половина корпуса скрыта только на этом виде.']}
    for j,s in enumerate(captions[mode]):dr.text((x+35,y+520+j*29),s,font=font(22),fill=MUTED)

# An unwrapped schematic of one J-shaped bayonet track, separate from the CAD.
x,y=800,730;dr.text((x+35,y),'4. Фиксация руками',font=font(26),fill=FG)
dr.text((x+35,y+45),'Путь выступа ключа в развёртке',font=font(22),fill=MUTED)
path=[(x+145,y+155),(x+145,y+335),(x+585,y+335),(x+585,y+265)]
dr.line(path,fill='#b3b9b1',width=30,joint='curve')
for xx,yy in path:dr.ellipse((xx-15,yy-15,xx+15,yy+15),fill='#b3b9b1')
def arrow(a,b,color=ACCENT):
    dr.line([a,b],fill=color,width=5);v=np.array(b,float)-a;v/=np.linalg.norm(v);p=np.array([-v[1],v[0]]);q=np.array(b)-16*v
    dr.polygon([tuple(b),tuple(q+8*p),tuple(q-8*p)],fill=color)
arrow((x+145,y+185),(x+145,y+300));arrow((x+195,y+335),(x+535,y+335));arrow((x+585,y+325),(x+585,y+275))
dr.ellipse((x+574,y+253,x+596,y+275),fill=ACCENT)
dr.text((x+190,y+205),'Вставить',font=font(24),fill=FG)
dr.text((x+275,y+375),'Повернуть на 90°',font=font(24),fill=FG)
dr.text((x+395,y+165),'Подтянуть в стопорный паз',font=font(22),fill=FG)
dr.text((x+395,y+197),'Обратный поворот требует нажатия',font=font(20),fill=MUTED)
for j,s in enumerate(['Это схема геометрии: автоматической защёлки нет.',
                      'Усилие поворота и удобство пальцами проверим на печати.',
                      'Размер и зазоры можно менять после первого образца.']):
    dr.text((x+35,y+463+j*31),s,font=font(22),fill=MUTED)
dr.line([(40,1340),(1560,1340)],fill='#cbd0c8',width=2)
dr.text((40,1360),'Проверено движение в модели. Прочность, износ и допустимая нагрузка ещё не испытаны.',font=font(23),fill=MUTED)
canvas.save(OUT/'mechanism-overview.png')
for mode in ['assembled','removed','section']:
    render(parts(mode),width=1000,height=900,yaw=47 if mode!='section' else 17,pitch=13).save(OUT/(mode+'.png'))
print('Rendered mechanism sheet and 3 close-ups')
