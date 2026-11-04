"""Experimental two-part spherical plywood retainer. No tested load rating."""
from pathlib import Path
import sys,math,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work/vendor'))
import numpy as np
import trimesh as tm
from shapely.geometry import box,Point
from build_assembly_v1 import cube,diff,extrude,components,collision_volume,yz_mesh

OUT=ROOT/'outputs/sphere-bayonet-v02';OUT.mkdir(parents=True,exist_ok=True)
R=45.; X,Z=22.,30.
d=np.array([-X,0,Z]);d/=np.linalg.norm(d)
e=np.array([d[2],0,-d[0]])
dist=X*Z/math.hypot(X,Z);c=e*dist
T=np.eye(4);T[:3,:3]=np.column_stack([e,[0,1,0],d]);T[:3,3]=c

def local_to_world(mesh):
    m=mesh.copy();m.apply_transform(T);return m
def cyl_local(r,t0,t1,xy=(0,0),sections=64):
    m=tm.creation.cylinder(r,t1-t0,sections=sections);m.apply_translation([xy[0],xy[1],(t0+t1)/2]);return m
def union(ms):return tm.boolean.union(ms,engine='manifold')
def pin_transform(mesh,angle=0,push=0):
    m=mesh.copy();m.apply_transform(tm.transformations.rotation_matrix(math.radians(angle),d,point=c));m.apply_translation(push*d);return m

def build():
    sphere=tm.creation.icosphere(subdivisions=4,radius=R)
    slots=[cube([-60,-20.6,-9.3],[60,65,9.3]),cube([-9.3,-20.6,2.7],[9.3,65,65])]
    cuts=[*slots]
    # One angled round shaft is guided by the printed body. The wooden windows
    # are routed perpendicular to each flat panel; no angled drilling is needed.
    cuts += [local_to_world(cyl_local(3.4,-80,70)),local_to_world(cyl_local(8.9,-65,-33.8))]
    # Entry slots, circumferential rotation channel, and two recessed J-pockets.
    cuts += [local_to_world(cube([-1.5,-5.6,-65],[1.5,5.6,-30.1])),
             local_to_world(cyl_local(5.6,-31.9,-30.1)),
             local_to_world(cube([-5.6,-1.5,-32.8],[5.6,1.5,-30.8]))]
    # Opposed finger recesses beside the flush head, accessible from underneath.
    for y in [-14.,14.]:cuts.append(local_to_world(cyl_local(5.8,-65,-33.8,xy=(0,y))))
    body=diff(sphere,cuts)
    # Key at final 90-degree locked orientation, already pulled into J-pockets.
    shaft=local_to_world(cyl_local(3.,-35.5,30.))
    lugs=[local_to_world(cube([2.6,-1.,-32.5],[5.,1.,-31.1])),local_to_world(cube([-5.,-1.,-32.5],[-2.6,1.,-31.1]))]
    cap=tm.boolean.intersection([sphere,local_to_world(cyl_local(8.5,-65,-35.))],engine='manifold')
    key=union([shaft,cap,*lugs])
    # An 18 mm shelf and upright, with a 6 mm wooden seat below the upright.
    shelf=cube([-95,-20,-9],[95,105,9]);divider=cube([-9,-20,3],[9,105,135])
    groove=cube([-9.3,-21,2.7],[9.3,106,10])
    # Rounded through-windows 21.2x8 and 26.2x8 mm, using a 4 mm cutter.
    hp=box(11.4,-4,32.6,4).buffer(-2).buffer(2)
    hcut=extrude(hp,22);hcut.apply_translation([0,0,-11])
    vp=box(-4,12.3,4,38.5).buffer(-2).buffer(2)
    vcut=yz_mesh(vp,-11,22)
    shelf=diff(shelf,[groove,hcut]);divider=diff(divider,[vcut])
    return dict(body=body,key=key,shelf=shelf,divider=divider,sphere=sphere)

def verify(ms):
    result={'status':'geometry prototype only; no strength or physical operation validation','units':'mm','sphere_diameter_mm':2*R,'plywood_thickness_mm':18,'shaft_diameter_mm':6,'key_push_to_unlock_mm':.8,'parts':{},'assembled_intersections':[],'movement_tests':{},'negative_tests':{}}
    for n,m in ms.items():
        if n=='sphere':continue
        result['parts'][n]={'watertight':bool(m.is_watertight),'components':components(m),'volume_cm3':round(m.volume/1000,3)}
        assert m.is_volume and components(m)==1,(n,result['parts'][n])
    names=['body','key','shelf','divider']
    for i,a in enumerate(names):
        for b in names[i+1:]:
            v=collision_volume(ms[a],ms[b]);
            if v>.03:result['assembled_intersections'].append(dict(a=a,b=b,volume_mm3=v))
    # Install the sphere from the front, with no key in it.
    hits=[];n=0
    for travel in [200,100,60,40,30,20,15,10,8,6,4,3,2,1,.5,.2,0]:
        body=ms['body'].copy();body.apply_translation([0,-travel,0]);n+=1
        for target in ['shelf','divider']:
            v=collision_volume(body,ms[target])
            if v>.03:hits.append(dict(travel_mm=travel,target=target,volume_mm3=v))
    result['movement_tests']['body_insertion']={'samples':n,'collisions':hits}
    # Insert the key with lugs aligned with entry slots.
    hits=[];n=0
    for push in [-100,-70,-50,-40,-30,-20,-10,-5,-2,-1,0,.2,.4,.6,.8]:
        key=pin_transform(ms['key'],-90,push);n+=1
        for target in ['body','shelf','divider']:
            v=collision_volume(key,ms[target])
            if v>.03:hits.append(dict(push_mm=push,target=target,volume_mm3=v))
    result['movement_tests']['key_insertion']={'samples':n,'collisions':hits}
    hits=[];n=0
    for angle in np.arange(-90,1,2):
        key=pin_transform(ms['key'],float(angle),.8);n+=1
        for target in ['body','shelf','divider']:
            v=collision_volume(key,ms[target])
            if v>.03:hits.append(dict(angle_deg=float(angle),target=target,volume_mm3=v))
    result['movement_tests']['quarter_turn_while_pressed']={'samples':n,'collisions':hits}
    hits=[]
    for push in np.arange(0,.81,.1):
        key=pin_transform(ms['key'],0,float(push))
        for target in ['body','shelf','divider']:
            v=collision_volume(key,ms[target])
            if v>.03:hits.append(dict(push_mm=float(push),target=target,volume_mm3=v))
    result['movement_tests']['settle_into_j_pockets']={'samples':9,'collisions':hits}
    # The locked pin should geometrically obstruct withdrawal and rotation.
    result['negative_tests']['withdraw_key_without_unlock_mm3']=round(collision_volume(pin_transform(ms['key'],0,-2),ms['body']),4)
    result['negative_tests']['rotate_key_without_pressing_30deg_mm3']=round(collision_volume(pin_transform(ms['key'],-30,0),ms['body']),4)
    for name,delta in [('divider',[0,0,4]),('shelf',[4,0,0])]:
        m=ms[name].copy();m.apply_translation(delta)
        result['negative_tests'][name+'_withdraw_4mm_key_overlap_mm3']=round(collision_volume(m,ms['key']),4)
    result['backlash_screening_mm']={}
    for name,axis in [('divider',2),('shelf',0)]:
        for delta in np.arange(.1,4.01,.1):
            v=np.zeros(3);v[axis]=delta;m=ms[name].copy();m.apply_translation(v)
            if collision_volume(m,ms['key'])>.03:
                result['backlash_screening_mm'][name+'_first_key_obstruction']=round(float(delta),2);break
    return result

COL={'body':[55,59,57,255],'key':[176,102,50,255],'shelf':[104,72,49,255],'divider':[104,72,49,255]}
def export_scene(ms,name,explode=False,cutaway=False):
    sc=tm.Scene()
    for n in ['shelf','divider','body','key']:
        m=ms[n].copy()
        if explode and n=='key':m=pin_transform(m,-90,-70)
        if cutaway:m=diff(m,[cube([-120,-130,-100],[120,0,170])])
        m.visual.vertex_colors=COL[n];sc.add_geometry(m,node_name=n)
    sc.apply_transform(tm.transformations.rotation_matrix(-math.pi/2,[1,0,0]));sc.apply_transform(np.diag([.001,.001,.001,1]));sc.export(OUT/name)

if __name__=='__main__':
    ms=build();checks=verify(ms)
    for n in ['body','key','shelf','divider']:ms[n].export(OUT/(n+'-prototype-mm.stl'))
    for name,exp,cut in [('assembled.glb',False,False),('key-removed.glb',True,False),('section.glb',False,True)]:export_scene(ms,name,exp,cut)
    (OUT/'geometry-checks.json').write_text(json.dumps(checks,indent=2))
    (ROOT/'work/bayonet-meshes.json').write_text(json.dumps({n:{'v':np.round(m.vertices,5).tolist(),'f':m.faces.tolist()} for n,m in ms.items() if n!='sphere'},separators=(',',':')))
    print(json.dumps(checks,indent=2))
