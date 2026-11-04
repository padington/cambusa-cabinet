from pathlib import Path
import sys,json,math
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'work/vendor'))
import trimesh as tm
from build_boltfree_cabinet import build,OUT,cube,moved,components,collision_volume,COLORS

def pack(folder,parts,origin):
    dst=OUT/'pilot-samples'/folder;dst.mkdir(parents=True,exist_ok=True)
    scene=tm.Scene();report={};placed=[]
    for p in parts:
        m=p['mesh'].copy();m.apply_translation(-np.array(origin));name=p['name'];mat=p['material']
        assert m.is_volume and components(m)==1,(name,components(m))
        m.export(dst/(name+'-assembly-mm.stl'))
        if p['group'] in ['node','key','cap']:
            printable=m.copy();xy=printable.bounds.mean(axis=0);printable.apply_translation([-xy[0],-xy[1],-printable.bounds[0,2]])
            printable.export(dst/(name+'-print-mm.stl'))
        m.visual.vertex_colors=[178,103,51,255] if p['group'] in ['key','cap'] else COLORS[mat]
        scene.add_geometry(m,node_name=name);placed.append((name,m))
        report[name]=dict(material=mat,group=p['group'],bounds_mm=np.round(m.bounds,3).tolist(),watertight=True,components=1)
    overlaps=[]
    for i,(na,a) in enumerate(placed):
        for nb,q in placed[i+1:]:
            v=collision_volume(a,q)
            if v>.05:overlaps.append(dict(a=na,b=nb,volume_mm3=v))
    assert not overlaps,overlaps
    scene.apply_transform(tm.transformations.rotation_matrix(-math.pi/2,[1,0,0]));scene.apply_transform(np.diag([.001,.001,.001,1]));scene.export(dst/'sample-assembled.glb')
    (dst/'parts.json').write_text(json.dumps(dict(parts=report,unintended_overlaps=overlaps,status='physical prototype not tested'),indent=2))

if __name__=='__main__':
    b=build(3);ps={p['name']:p for p in b['parts']}
    # A real corner of the new side frame, including its machined front contour.
    crop=cube([30,15,110],[150,150,240]);out=[]
    for name in ['frame-left','shelf-0','sphere-side-left-0','key-side-left-0-0']:
        p=ps[name].copy()
        if p['group']=='wood':p['mesh']=tm.boolean.intersection([p['mesh'],crop],engine='manifold')
        out.append(p)
    pack('01-side-corner',out,[45,50,170])
    # The top stop and an actual matching section of frame and 6 mm back panel.
    crop=cube([30,300,1150],[105,355,1201]);out=[]
    for name in ['frame-left','back-panel','back-stop-left']:
        p=ps[name].copy()
        if p['group'] in ['wood','back']:p['mesh']=tm.boolean.intersection([p['mesh'],crop],engine='manifold')
        out.append(p)
    pack('02-back-stop',out,[42,335,1200])
    # An internal T joint; use this revised body, whose front clearance is deeper
    # than in the previous stand-alone v02 node.
    crop=cube([500,80,155],[700,310,310]);out=[]
    for name in ['shelf-0','partition-0','sphere-inner-x600-0-front','key-inner-x600-0-front-0']:
        p=ps[name].copy()
        if p['group']=='wood':p['mesh']=tm.boolean.intersection([p['mesh'],crop],engine='manifold')
        out.append(p)
    pack('03-inner-T',out,[600,110,170])
    b=build(4);ps={p['name']:p for p in b['parts']};crop=cube([500,80,350],[700,200,650]);out=[]
    for name in ['shelf-1','partition-0','partition-1','sphere-inner-x600-1-front','key-inner-x600-1-front-0','key-inner-x600-1-front-1']:
        p=ps[name].copy()
        if p['group']=='wood':p['mesh']=tm.boolean.intersection([p['mesh'],crop],engine='manifold')
        out.append(p)
    pack('04-inner-X',out,[600,110,500])
    print('Four separate sample assemblies exported and checked')
