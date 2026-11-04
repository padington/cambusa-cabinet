import json, math
import numpy as np
from PIL import Image, ImageDraw
meshes=json.load(open('work/reference-design-meshes.json'))
def render(name):
    m=meshes[name]; p=np.array(m['position']).reshape(-1,3); n=np.array(m['normal']).reshape(-1,3); col=np.array(m['color']).reshape(-1,3); mat=np.array(m['material'])
    yaw=math.radians(27); pitch=math.radians(13)
    right=np.array([math.cos(yaw),math.sin(yaw),0]);up=np.array([-math.sin(yaw)*math.sin(pitch),math.cos(yaw)*math.sin(pitch),math.cos(pitch)]);camera=np.array([math.sin(yaw)*math.cos(pitch),-math.cos(yaw)*math.cos(pitch),math.sin(pitch)])
    q=p-np.array([500,0 if name.endswith('open') else 175,600]);xy=np.c_[q@right,-q@up];depth=q@camera
    width,height=500,610; ext=np.ptp(xy,axis=0);scale=min((width-40)/ext[0],(height-40)/ext[1]); xy=(xy-(xy.min(axis=0)+xy.max(axis=0))/2)*scale+[width/2,height/2]
    light=np.array([-.65,-.85,1.2]);light/=np.linalg.norm(light);diff=np.maximum(0,n@light); colors=col*(.48+.55*diff[:,None])
    pixels=np.full((height,width,3),[250,249,246],dtype=np.uint8);zbuf=np.full((height,width),-np.inf)
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
for opened in [False,True]:
    canvas=Image.new('RGB',(1500,610),'#faf9f6')
    for i,k in enumerate(['cassette','gallery','workshop']):canvas.paste(render(k+('-open' if opened else '')),(i*500,0))
    canvas.save('work/reference-designs'+('-open' if opened else '')+'.png')
print('Rendered 3 closed and 3 open concepts')
