"""Geometry helpers from the cabinet model."""
import math
import numpy as np
from PIL import Image
import trimesh as tm

COLORS = {}

def cube(lo,hi):
    lo=np.array(lo,float); hi=np.array(hi,float)
    m=tm.creation.box(hi-lo);m.apply_translation((lo+hi)/2);return m

def panel(poly,axis,lo,t):
    m=tm.creation.extrude_polygon(poly,t,engine='earcut')
    if axis==0:m.vertices=m.vertices[:,[2,0,1]]
    elif axis==1:m.vertices=m.vertices[:,[0,2,1]];m.invert()
    tr=np.zeros(3);tr[axis]=lo;m.apply_translation(tr)
    return m

def add(ps,name,m,mat='wood',group='body',**kw):
    ps.append(dict(name=name,mesh=m,material=mat,group=group,**kw))

def scene(ps):
    s=tm.Scene()
    for p in ps:
        if p['group']=='prop':continue
        m=p['mesh'].copy();m.visual=tm.visual.ColorVisuals(m,vertex_colors=COLORS[p['material']])
        m.apply_transform(tm.transformations.rotation_matrix(-math.pi/2,[1,0,0]));m.apply_scale(.001)
        s.add_geometry(m,geom_name=p['name'],node_name=p['name'])
    return s

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
