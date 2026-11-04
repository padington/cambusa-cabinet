from pathlib import Path
import sys,math,json
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'work/vendor'))
import trimesh as tm
from build_boltfree_cabinet import build,OUT,moved,cube,diff,cap_geometry,COLORS,connector,BASE
from render_assembly_v1 import render
COLORS['key']=[65,69,66,255]
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'
def font(s):return ImageFont.truetype(FONT,s)
BG='#f6f5f1';FG='#25302a';MUTED='#5b665d'
def view(b,mode):
    ps=[]
    for p in b['parts']:
        q=p.copy();q['mesh']=p['mesh'].copy()
        if mode=='exploded':
            if p['name']=='frame-left':q['mesh'].apply_translation([-160,0,0])
            elif p['name']=='frame-right':q['mesh'].apply_translation([160,0,0])
            elif p['group']=='back':q['mesh'].apply_translation([0,150,0])
            elif p['group']=='door':q['mesh'].apply_translation([0,-160,0])
            elif p['group']=='node':q['mesh'].apply_translation([0,95 if p['rear'] else -95,0])
            elif p['group']=='key':
                owner=next(z for z in b['parts'] if z['name']==p['owner']);q['mesh'].apply_translation([0,95 if owner['rear'] else -95,0])
            elif p['group']=='cap':q['mesh'].apply_translation([0,0,60])
        if mode=='open' and p['group']=='door':
            door=next(z for z in b['doors'] if z['name']==p['name'])
            q['mesh'].apply_transform(tm.transformations.rotation_matrix(door['sign']*math.radians(86),[0,0,1],point=door['pivot']))
        ps.append(q)
    return render(ps,width=1000,height=1080,yaw=27,pitch=14)

if __name__=='__main__':
    designs={k:build(k) for k in [3,4]}
    for mode in ['assembled','exploded','open']:
        im=Image.new('RGB',(2000,1380),BG);dr=ImageDraw.Draw(im)
        for i,k in enumerate([3,4]):
            print('Render',k,mode,flush=True)
            b=designs[k];im.paste(view(b,mode),(i*1000,150))
            dr.text((i*1000+35,25),'03  Смещённые ячейки' if k==3 else '04  Ступень',font=font(36),fill=FG)
            dr.text((i*1000+35,79),'Корпус: 0 винтов / 0 болтов',font=font(27),fill=FG)
            n=sum(p['group']=='node' for p in b['parts']);keys=sum(p['group']=='key' for p in b['parts'])
            dr.text((i*1000+35,116),f'{n} шаров + {keys} печатных ключей + 2 стопора задника',font=font(23),fill=MUTED)
        dr.text((35,1230),'Около 1000 × 1200 × 350 мм • фанера 18 мм • шар Ø90 мм • цвет условный',font=font(25),fill=MUTED)
        dr.text((35,1272),'Дверцы — на готовых петлях со скрытыми винтами; петли заранее устанавливает мастер.',font=font(25),fill=MUTED)
        dr.text((35,1314),'Геометрический прототип: прочность и точная кинематика петель ещё требуют проверки.',font=font(25),fill=MUTED)
        im.save(OUT/(mode+'.png'))
    # Detail: full rear stop and the prepared frame/back. A view from the rear.
    b=designs[3];names=['frame-left','back-panel','back-stop-left'];ps=[]
    crop=cube([30,305,1145],[100,355,1201])
    for p in b['parts']:
        if p['name'] not in names:continue
        q=p.copy();q['mesh']=tm.boolean.intersection([p['mesh'],crop],engine='manifold')
        if p['name']=='back-stop-left':q['material']='key'
        ps.append(q)
    COLORS['key']=[180,105,52,255]
    im=Image.new('RGB',(1200,1060),BG);im.paste(render(ps,width=1200,height=830,yaw=150,pitch=35),(0,120));dr=ImageDraw.Draw(im)
    dr.text((35,28),'Задник: два печатных поворотных стопора',font=font(34),fill=FG)
    dr.text((35,78),'Вставить сверху → нажать и повернуть → посадить в стопорный паз',font=font(24),fill=MUTED)
    dr.text((35,980),'Винтов нет. Удержание проверено геометрически; усилие и износ требуют испытания.',font=font(23),fill=MUTED)
    im.save(OUT/'back-stop-detail.png')
    print('Views done',flush=True)
