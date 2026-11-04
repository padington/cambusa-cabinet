from pathlib import Path
import sys,math,json
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'work/vendor'))
import trimesh as tm
from build_assembly_v1 import build, scene_for, COLORS, node_model, cube, diff
OUT=ROOT/'outputs/cabinet-03-04-engineering-v1'
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'
def font(s):return ImageFont.truetype(FONT,s)

def render(parts,width=900,height=1040,yaw=27,pitch=14):
    positions=[];normals=[];colors=[]
    for p in parts:
        mesh=p['mesh'];tri=mesh.triangles;n=mesh.face_normals
        color=np.tile(np.array(COLORS[p['material']][:3])/255.,(len(tri),1))
        if p['material'] in ['wood','back']:
            axis=0 if p['name'].startswith(('frame','partition')) else 2 if p['name'].startswith('shelf') else 1
            edge=np.abs(n[:,axis])<.6
            color[edge]*=1.28
        positions.append(tri.reshape(-1,3));normals.append(np.repeat(n,3,axis=0));colors.append(np.repeat(color,3,axis=0))
    p=np.vstack(positions);n=np.vstack(normals);col=np.vstack(colors)
    yaw=math.radians(yaw);pitch=math.radians(pitch)
    right=np.array([math.cos(yaw),math.sin(yaw),0]);up=np.array([-math.sin(yaw)*math.sin(pitch),math.cos(yaw)*math.sin(pitch),math.cos(pitch)])
    camera=np.array([math.sin(yaw)*math.cos(pitch),-math.cos(yaw)*math.cos(pitch),math.sin(pitch)])
    q=p-(p.min(axis=0)+p.max(axis=0))/2;xy=np.c_[q@right,-q@up];depth=q@camera
    ext=np.ptp(xy,axis=0);scale=min((width-60)/ext[0],(height-50)/ext[1]);xy=(xy-(xy.min(axis=0)+xy.max(axis=0))/2)*scale+[width/2,height/2]
    light=np.array([-.7,-1,1.4]);light/=np.linalg.norm(light);diffuse=np.maximum(0,n@light);colors=col*(.53+.65*diffuse[:,None])
    pixels=np.full((height,width,3),[246,245,241],dtype=np.uint8);zbuf=np.full((height,width),-np.inf)
    for idx in range(len(p)//3):
        pts=xy[idx*3:idx*3+3];zz=depth[idx*3:idx*3+3]
        x0,y0=np.floor(pts.min(axis=0)).astype(int);x1,y1=np.ceil(pts.max(axis=0)).astype(int)
        x0=max(0,x0);x1=min(width-1,x1);y0=max(0,y0);y1=min(height-1,y1)
        if x0>x1 or y0>y1:continue
        a,b,c=pts;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den)<1e-7:continue
        xx,yy=np.meshgrid(np.arange(x0,x1+1)+.5,np.arange(y0,y1+1)+.5)
        u=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/den
        v=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/den;w=1-u-v
        z=u*zz[0]+v*zz[1]+w*zz[2];target=zbuf[y0:y1+1,x0:x1+1];mask=(u>=-1e-6)&(v>=-1e-6)&(w>=-1e-6)&(z>target)
        if not np.any(mask):continue
        target[mask]=z[mask];rgb=u[:,:,None]*colors[idx*3]+v[:,:,None]*colors[idx*3+1]+w[:,:,None]*colors[idx*3+2]
        pixels[y0:y1+1,x0:x1+1][mask]=np.clip(rgb[mask]*255,0,255).astype(np.uint8)
    return Image.fromarray(pixels)

def panel(k,mode):
    d=build(k);ps=[]
    for p in d['parts']:
        q=p.copy();q['mesh']=p['mesh'].copy()
        if mode=='exploded':
            if p['name']=='frame-left':q['mesh'].apply_translation([-150,0,0])
            elif p['name']=='frame-right':q['mesh'].apply_translation([150,0,0])
            elif p['group']=='back':q['mesh'].apply_translation([0,170,0])
            elif p['group']=='door':q['mesh'].apply_translation([0,-180,0])
            elif p['group']=='node' or (p['group']=='hardware' and not p.get('prefit')):
                owner=next((v for v in d['parts'] if v['name']==p.get('owner')),p)
                q['mesh'].apply_translation([0,95 if owner.get('rear') else -95,0])
            elif p['group']=='frame-hardware':q['mesh'].apply_translation([-150 if p['side']=='left' else 150,0,0])
        elif mode=='open' and p['group']=='door':
            door=next(v for v in d['doors'] if v['name']==p['name'])
            q['mesh'].apply_transform(tm.transformations.rotation_matrix(door['sign']*math.radians(95),[0,0,1],point=door['pivot']))
        ps.append(q)
    return render(ps)

if __name__=='__main__':
    for mode in ['assembled','exploded','open']:
        canvas=Image.new('RGB',(1800,1220),'#f6f5f1');dr=ImageDraw.Draw(canvas)
        for i,k in enumerate([3,4]):
            print('Rendering',k,mode,flush=True)
            canvas.paste(panel(k,mode),(i*900,105))
            dr.text((i*900+35,30),('03  Смещённые ячейки' if k==3 else '04  Ступень'),font=font(34),fill='#242c29')
            dr.text((i*900+35,78),'1000 × 1200 × 350 мм  /  фанера 18 мм',font=font(23),fill='#57605a')
        foot={'assembled':'Вид из точной геометрии • цвет условный • фурнитура дверей ещё подбирается','exploded':'Разнесённый вид деталей • порядок сборки — в приложенном описании','open':'Показано открывание вокруг условной оси • механизм выбранных петель не проверен'}[mode]
        dr.text((35,1175),foot,font=font(23),fill='#57605a')
        canvas.save(OUT/(mode+'.png'))

    # A real mesh close-up of the proposed load-bearing dado plus spherical retainer.
    body,hw,holes,ports,info=node_model(1,[1])
    A=cube([-100,-20,-9],[100,120,9]);B=cube([-9,-20,3],[9,120,135])
    A=diff(A,[cube([-9.3,-21,2.7],[9.3,121,10]),holes[0]]);B=diff(B,[holes[1]])
    parts=[dict(name='shelf',mesh=A,material='wood'),dict(name='partition',mesh=B,material='wood'),dict(name='node',mesh=body,material='node')]
    parts += [dict(name=n,mesh=m,material=mat) for n,m,mat in hw]
    im=Image.new('RGB',(1100,1050),'#f6f5f1');im.paste(render(parts,1100,860,yaw=35,pitch=27),(0,110));dr=ImageDraw.Draw(im)
    dr.text((35,25),'Пробный Т-узел • сфера Ø72 мм',font=font(34),fill='#242c29')
    dr.text((35,76),'Паз в фанере несёт полку; винты М5 удерживают соединение',font=font(23),fill='#57605a')
    dr.text((35,1000),'Это образец для испытаний, допустимая нагрузка ещё не установлена',font=font(23),fill='#57605a')
    im.save(OUT/'joint-prototype.png')
    print('All views complete',flush=True)
