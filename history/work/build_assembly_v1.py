from pathlib import Path
import sys, json, math, csv, copy, zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work/vendor'))
import numpy as np
import trimesh as tm
from shapely.geometry import Polygon, box, Point
from shapely.ops import unary_union

OUT=ROOT/'outputs/cabinet-03-04-engineering-v1'
OUT.mkdir(exist_ok=True,parents=True)
WORK=ROOT/'work/assembly-v1'; WORK.mkdir(exist_ok=True)
PLY=18.; HALF=9.; GAP=.3; R=36.
LEVELS=[170.,500.,830.,1160.]
XL,XR=21.,979.
FRONT,REAR=90.,320.
COLORS={'wood':[91,62,43,255],'back':[73,48,34,255], 'graphite':[47,49,48,255], 'node':[45,49,47,255], 'knob':[66,71,68,255], 'metal':[157,163,159,255]}

def cube(lo,hi):
    lo=np.array(lo,float); hi=np.array(hi,float)
    m=tm.creation.box(hi-lo);m.apply_translation((lo+hi)/2);return m
def extrude(poly,height):return tm.creation.extrude_polygon(poly,height,engine='earcut')
def cylinder(axis,center,radius,length,sections=24):
    m=tm.creation.cylinder(radius,length,sections=sections)
    if axis==0:m.apply_transform(tm.transformations.rotation_matrix(math.pi/2,[0,1,0]))
    elif axis==1:m.apply_transform(tm.transformations.rotation_matrix(math.pi/2,[1,0,0]))
    m.apply_translation(center);return m
def hex_prism(axis,center,af,length):
    m=tm.creation.cylinder(af/math.sqrt(3),length,sections=6)
    if axis==0:m.apply_transform(tm.transformations.rotation_matrix(math.pi/2,[0,1,0]))
    elif axis==1:m.apply_transform(tm.transformations.rotation_matrix(math.pi/2,[1,0,0]))
    m.apply_translation(center);return m
def diff(m,cutters):
    if not cutters:return m.copy()
    a=tm.boolean.difference([m,*cutters],engine='manifold');a.remove_unreferenced_vertices();return a
def overlap(a,b,tol=1e-5):return bool(np.all(np.minimum(a.bounds[1],b.bounds[1])-np.maximum(a.bounds[0],b.bounds[0])>tol))
def collision_volume(a,b):
    if not overlap(a,b):return 0.
    q=tm.boolean.intersection([a,b],engine='manifold')
    return abs(float(q.volume)) if len(q.faces) else 0.
def components(mesh):
    parent=list(range(len(mesh.vertices)))
    def root(a):
        while parent[a]!=a:
            parent[a]=parent[parent[a]];a=parent[a]
        return a
    for f in mesh.faces:
        a=root(int(f[0]))
        for b in f[1:]:parent[root(int(b))]=a
    return len({root(i) for i in range(len(parent))})
def world(mesh,center,rear=False):
    m=mesh.copy();T=np.eye(4);T[1,1]=-1 if rear else 1;T[:3,3]=center;m.apply_transform(T);return m

NODE_CACHE={}
def node_model(horizontal_sign,vertical_signs,head_sign=1):
    key=(horizontal_sign,tuple(vertical_signs),head_sign)
    if key in NODE_CACHE:return NODE_CACHE[key]
    s=tm.creation.icosphere(subdivisions=3,radius=R)
    cuts=[cube([-50,-60,-50],[50,-30,50]),cube([-9.3,-23,-50],[9.3,50,50]),cube([-50,-23,-9.3],[50,50,9.3])]
    ports=[dict(axis=2,p=[horizontal_sign*20.,-7.,0.],tag='shelf',head_sign=head_sign)]
    ports += [dict(axis=0,p=[0.,7.,v*20.],tag='partition-'+str(v)) for v in vertical_signs]
    hardware=[]; holes=[]
    for k,p in enumerate(ports):
        ax=p['axis'];c=np.array(p['p']);hs=p.get('head_sign',1);holes.append(cylinder(ax,c,2.9,110))
        cuts.append(holes[-1])
        cb=c.copy();cb[ax]=hs*33.5;cuts.append(cylinder(ax,cb,5.6,33.)) # compression seat at +/-17
        nc=c.copy();nc[ax]=-hs*33.15;cuts.append(hex_prism(ax,nc,8.6,33.7)) # nut shoulder at -/+16.3
        nc[ax]=-hs*18.5;nut=diff(hex_prism(ax,nc,8.,4.4),[cylinder(ax,nc,2.55,8)])
        sc=c.copy();sc[ax]=hs*5.;shaft=cylinder(ax,sc,2.5,60)
        hc=c.copy();hc[ax]=hs*37.;head=hex_prism(ax,hc,8.,4.)
        shaft=tm.boolean.union([shaft,head],engine='manifold')
        # Raised grip clears the spherical body and the other knob: fingers pinch
        # at +/- y, above the compression stem. Steel M5x60 carries tension.
        kc=c.copy();kc[ax]=hs*41.;grip=cylinder(ax,kc,9.,12,32)
        stemc=c.copy();stemc[ax]=hs*26.;stem=cylinder(ax,stemc,5.,18.,32)
        knob=tm.boolean.union([grip,stem],engine='manifold')
        head_entry=c.copy();head_entry[ax]=hs*42.5
        knob=diff(knob,[cylinder(ax,c,2.7,110),hex_prism(ax,head_entry,8.6,15.)])
        hardware += [(f'{k}-nut',nut,'metal'),(f'{k}-stud',shaft,'metal'),(f'{k}-knob',knob,'knob')]
    body=diff(s,cuts)
    info={'watertight':bool(body.is_watertight),'components':components(body),'volume_cm3':round(body.volume/1000,2),'port_count':len(ports)}
    assert body.is_volume and info['components']==1,info
    NODE_CACHE[key]=(body,hardware,holes,ports,info)
    return NODE_CACHE[key]

def yz_mesh(poly,x0,thickness):
    m=extrude(poly,thickness)
    T=np.array([[0,0,1,x0],[1,0,0,0],[0,1,0,0],[0,0,0,1]],float);m.apply_transform(T);return m
def xz_mesh(poly,y0,thickness):
    m=extrude(poly,thickness)
    T=np.array([[1,0,0,0],[0,0,1,y0],[0,1,0,0],[0,0,0,1]],float);m.apply_transform(T);return m

def build(kind):
    parts=[]; cutters={}; joints=[]; motion=[]; profiles={}; doors=[]
    def add(name,mesh,material,group,**meta):
        p=dict(name=name,mesh=mesh,material=material,group=group,**meta);parts.append(p);cutters[name]=[];return p
    heights={'left':1200 if kind==3 else 870,'right':1200}
    for side,x in [('left',XL),('right',XR)]:
        H=heights[side]
        poly=Polygon([(0,0),(45,0),(70,145),(300,145),(315,0),(350,0),(350,H),(85,H),(25,170)])
        poly=poly.buffer(-6,join_style='round').buffer(6,join_style='round')
        name=f'frame-{side}';add(name,yz_mesh(poly,x-9,18),'wood','wood',axis=0,thickness=18)
        profiles[name]=(poly,18,'yz')
        for z in LEVELS:
            if z>H:continue
            xx=[x+2.7,x+9.3] if side=='left' else [x-9.3,x-2.7]
            cutters[name].append(cube([xx[0],FRONT-.3,z-9.3],[xx[1],REAR+.3,z+9.3]))
        xx=[x+2.7,x+9.3] if side=='left' else [x-9.3,x-2.7]
        # The rear groove is open at the top: back is installed AFTER rear nodes.
        cutters[name].append(cube([xx[0],331.7,153.7],[xx[1],338.3,H+2]))
    for k,z in enumerate(LEVELS):
        x0=24. if kind==3 or k<3 else 603.
        name=f'shelf-{k}';poly=box(x0,FRONT,976.,REAR)
        add(name,extrude(poly,18).apply_translation([0,0,z-9]),'wood','wood',axis=2,thickness=18)
        profiles[name]=(poly,18,'xy')
    divs=[600.,350.,700.] if kind==3 else [600.,600.,600.]
    for row,x in enumerate(divs):
        lo,hi=LEVELS[row:row+2];name=f'partition-{row}'
        poly=box(FRONT,lo+3,REAR,hi-3)
        add(name,yz_mesh(poly,x-9,18),'wood','wood',axis=0,thickness=18)
        profiles[name]=(poly,18,'yz')
        cutters[f'shelf-{row}'].append(cube([x-9.3,FRONT-.3,lo+2.7],[x+9.3,REAR+.3,lo+10]))
        cutters[f'shelf-{row+1}'].append(cube([x-9.3,FRONT-.3,hi-10],[x+9.3,REAR+.3,hi-2.7]))
    # Interior spherical joints, one shared node at an X intersection.
    junctions={}
    for row,x in enumerate(divs):
        for level,v in [(row,1),(row+1,-1)]:junctions.setdefault((x,level),[]).append(v)
    for (x,k),vsigns in junctions.items():
        hs=1
        body,hw,holes,ports,info=node_model(hs,sorted(vsigns),-1 if k==3 else 1)
        for rear in [False,True]:
            loc=np.array([x,300 if rear else 110,LEVELS[k]])
            tag=f'node-x{int(x)}-l{k}-'+('rear' if rear else 'front')
            add(tag,world(body,loc,rear),'node','node',center=loc.tolist(),rear=rear,template=f'h{hs}-v'+''.join('u' if v>0 else 'd' for v in sorted(vsigns)))
            for hn,hm,mat in hw:
                port=ports[int(hn.split('-')[0])]
                add(tag+'-'+hn,world(hm,loc,rear),mat,'hardware',owner=tag,port_axis=port['axis'],head_sign=port.get('head_sign',1),port_index=int(hn.split('-')[0]))
            for hole,port in zip(holes,ports):
                target=f'shelf-{k}' if port['axis']==2 else f'partition-{k if port["p"][2]>0 else k-1}'
                cutters[target].append(world(hole,loc,rear))
            joints.append(dict(name=tag,ports=ports,**info))
    # Outer frames retain shelves with M6 finger knobs and metal cross dowels.
    # Nominal barrel geometry is a design envelope; supplier must match actual hardware.
    for k,z in enumerate(LEVELS):
        for side,x,sign in [('left',XL,1),('right',XR,-1)]:
            if kind==4 and k==3 and side=='left':continue
            for y in [130.,280.]:
                tag=f'frame-fastener-{side}-l{k}-y{int(y)}'
                seat=x-sign*9.; barrelx=seat+sign*37.
                holecenter=[(seat+barrelx+sign*16)/2,y,z]
                hole=cylinder(0,holecenter,3.4,abs(barrelx+sign*16-seat))
                cutters[f'frame-{side}'].append(hole);cutters[f'shelf-{k}'].append(hole)
                # A blind bore from below, leaving 3 mm of plywood above the barrel.
                bore=cylinder(2,[barrelx,y,z-2],5.3,16)
                cutters[f'shelf-{k}'].append(bore)
                barrel=diff(cylinder(2,[barrelx,y,z],5,12),[cylinder(0,[barrelx,y,z],3.05,14)])
                stud=cylinder(0,[seat+sign*25,y,z],3,50)
                knob=cylinder(0,[seat-sign*6,y,z],12,12,32)
                add(tag+'-barrel',barrel,'metal','hardware',owner=f'shelf-{k}',prefit=True)
                add(tag+'-stud',stud,'metal','frame-hardware',side=side)
                add(tag+'-knob',knob,'knob','frame-hardware',side=side)
    # Rear panel slides vertically through top-open grooves. Top retaining tabs are
    # a fabrication detail still to be prototyped; panel must not be left loose.
    if kind==3:backpoly=box(24,154,976,1176)
    else:backpoly=Polygon([(24,154),(976,154),(976,1176),(595,1176),(595,854),(24,854)])
    add('back-panel',xz_mesh(backpoly,332,6),'back','back',axis=1,thickness=6)
    profiles['back-panel']=(backpoly,6,'xz')
    # Doors: cup drilling is represented; actual CLIP linkage is not part of the CAD.
    db=[(40,588,185,485,'left','graphite'),(714,960,845,1145,'right','wood')] if kind==3 else [(40,588,185,485,'left','wood'),(614,960,515,815,'right','graphite')]
    for k,(a,b,lo,hi,side,mat) in enumerate(db):
        poly=box(a,lo,b,hi).buffer(-3).buffer(3)
        handlex=b-30 if side=='left' else a+30
        handle=box(handlex-7,(lo+hi)/2-23,handlex+7,(lo+hi)/2+23).buffer(7).buffer(-.01)
        poly=poly.difference(handle)
        name=f'door-{k}';m=xz_mesh(poly,55,18)
        hinges=[]
        cx=a+20.5 if side=='left' else b-20.5
        for zz in [lo+50,hi-50]:
            m=diff(m,[cylinder(1,[cx,67,zz],17.5,14,48)]) # back drill 13 mm to y=60
            hinges.append([cx,zz])
        pivot=[a-3 if side=='left' else b+3,52,0]
        add(name,m,mat,'door',side=side,pivot=pivot,axis=1,thickness=18)
        doors.append(dict(name=name,pivot=pivot,sign=-1 if side=='left' else 1,hinge_centers=hinges))
        profiles[name]=(poly,18,'xz')
    # Execute all CNC pockets / bores.
    for p in parts:
        if cutters[p['name']]:p['mesh']=diff(p['mesh'],cutters[p['name']])
        if not p['mesh'].is_volume:raise RuntimeError('Invalid mesh '+p['name'])
    return dict(kind=kind,parts=parts,profiles=profiles,joints=joints,doors=doors,divs=divs)

def scene_for(design,mode='assembled'):
    scene=tm.Scene()
    for p in design['parts']:
        m=p['mesh'].copy()
        if mode=='exploded':
            if p['name']=='frame-left':m.apply_translation([-160,0,0])
            elif p['name']=='frame-right':m.apply_translation([160,0,0])
            elif p['group']=='back':m.apply_translation([0,140,0])
            elif p['group']=='door':m.apply_translation([0,-180,0])
            elif p['group']=='node' or (p['group']=='hardware' and not p.get('prefit')):
                owner=next((q for q in design['parts'] if q['name']==p.get('owner')),p)
                m.apply_translation([0,80 if owner.get('rear') else -80,0])
        m.visual.vertex_colors=COLORS[p['material']]
        scene.add_geometry(m,node_name=p['name'],geom_name=p['name'])
    return scene

def meshchecks(design):
    ps=design['parts'];collisions=[];pairs=0;broad=0
    for i,a in enumerate(ps):
        for b in ps[i+1:]:
            pairs+=1
            if not overlap(a['mesh'],b['mesh']):continue
            broad+=1;v=collision_volume(a['mesh'],b['mesh'])
            if v>.05:collisions.append(dict(a=a['name'],b=b['name'],volume_mm3=round(v,4)))
    return dict(total_parts=len(ps),all_watertight=all(p['mesh'].is_watertight for p in ps),pairs_checked=pairs,exact_boolean_pairs=broad,unintended_overlaps=collisions)

def motionchecks(design):
    ps={p['name']:p for p in design['parts']};fixed=[];results=[]
    def check(label,names,axis,start,direction):
        moving=[ps[n] for n in names];collisions=[]
        positions=sorted(set([0.,start]+[v for v in [.1,.3,.5,1,2,3,4,5,6,7,8,9,10,15,20,30,40,60,100,200,400,800] if v<start]),reverse=True)
        for distance in positions:
            delta=np.zeros(3);delta[axis]=distance*direction
            for a in moving:
                m=a['mesh'].copy();m.apply_translation(delta)
                for b in fixed:
                    if not overlap(m,b['mesh']):continue
                    v=collision_volume(m,b['mesh'])
                    if v>.05:collisions.append(dict(distance_mm=round(float(distance),2),moving=a['name'],fixed=b['name'],volume_mm3=round(v,3)))
        results.append(dict(step=label,moving=names,samples=len(positions),sample_positions_mm=positions,travel_mm=start,collisions=collisions))
        fixed.extend(moving)
    # Assemble the central grid while laid on its rear edges, before closing sides.
    def shelf_names(k):return [f'shelf-{k}']+[p['name'] for p in design['parts'] if p.get('prefit') and p.get('owner')==f'shelf-{k}']
    check('1. Base on protected flat surface',shelf_names(0),2,0,1)
    for row in range(3):
        check(f'{2+row*2}. Lower partition into bottom dado',[f'partition-{row}'],2,400,1)
        check(f'{3+row*2}. Lower following shelf onto partition',shelf_names(row+1),2,400,1)
    check('8. Left frame slides over shelf ends',['frame-left'],0,1100,-1)
    check('9. Right frame slides over shelf ends',['frame-right'],0,1100,1)
    # Add side screws after both frames are in their final positions.
    for p in design['parts']:
        if p['group']=='frame-hardware' and p['name'].endswith('-knob'):
            check('10. Insert and hand-turn side fastener',[p['name'].replace('-knob','-stud'),p['name']],0,80,-1 if p['side']=='left' else 1)
    for rear in [False,True]:
        for p in design['parts']:
            if p['group']=='node' and p['rear']==rear:
                nuts=[q['name'] for q in design['parts'] if q.get('owner')==p['name'] and q['name'].endswith('-nut')]
                check('11. Slide spherical node with prefit nuts onto panel edges',[p['name'],*nuts],1,400,1 if rear else -1)
                for q in design['parts']:
                    if q.get('owner')==p['name'] and q['name'].endswith('-knob'):
                        check('12. Insert and hand-turn node fastener',[q['name'].replace('-knob','-stud'),q['name']],q['port_axis'],80,q['head_sign'])
    check('13. Slide back down through open-top side grooves',['back-panel'],2,1250,1)
    # Finger-access screening: two 12 mm diameter pads on the protruding grip.
    # This is a geometric allowance, not an ergonomic validation with real hands.
    access=[]
    for p in design['parts']:
        if p['group']=='hardware' and p['name'].endswith('-knob'):
            owner=ps[p['owner']];c=p['mesh'].bounds.mean(axis=0);ax=p['port_axis'];c[ax]=owner['center'][ax]+p['head_sign']*41
            for sign in [-1,1]:
                fc=c.copy();fc[1]+=sign*15;finger=cylinder(ax,fc,6,10,16);hits=[]
                for q in design['parts']:
                    if q['group']=='door' or q['name']==p['name']:continue
                    v=collision_volume(finger,q['mesh'])
                    if v>.05:hits.append(dict(part=q['name'],volume_mm3=round(v,3)))
                access.append(dict(knob=p['name'],pad=sign,collisions=hits))
    # Door motion is an ideal pivot clearance sweep only, not the Blum mechanism.
    sweep=[]
    for d in design['doors']:
        a=ps[d['name']];hits=[]
        for angle in np.linspace(0,110,23):
            m=a['mesh'].copy();m.apply_transform(tm.transformations.rotation_matrix(d['sign']*math.radians(angle),[0,0,1],point=d['pivot']))
            for b in fixed:
                v=collision_volume(m,b['mesh'])
                if v>.05:hits.append(dict(angle_deg=float(angle),fixed=b['name'],volume_mm3=round(v,3)))
        sweep.append(dict(door=d['name'],angle_range_deg=[0,110],samples=23,collisions=hits,scope='ideal pivot only; exact supplier hinge linkage and adjustment NOT validated'))
    return dict(sequence=results,door_sweeps=sweep,finger_access=access,scope='Discrete positions, dense within final 10 mm of travel. Collision-free samples do not constitute continuous-motion, ergonomic or physical validation. Exact commercial hinge and back-panel retention hardware pending.')

def write_outputs(d):
    k=d['kind'];folder=OUT/f'variant-{k:02d}';folder.mkdir(exist_ok=True)
    for mode in ['assembled','exploded']:
        scene=scene_for(d,mode);scene.apply_transform(tm.transformations.rotation_matrix(-math.pi/2,[1,0,0]));scene.apply_transform(np.diag([.001,.001,.001,1]));scene.export(folder/f'{mode}.glb')
    # Authoritative part geometry (millimetres), including all holes / grooves.
    for p in d['parts']:
        if p['group'] in ['wood','back','door','node']:p['mesh'].export(folder/(p['name']+'.stl'))
    rows=[]
    for p in d['parts']:
        if p['group'] in ['wood','back','door']:
            rows.append(dict(part=p['name'],material=p['material'],thickness_mm=p['thickness'],x_mm=round(p['mesh'].extents[0],2),y_mm=round(p['mesh'].extents[1],2),z_mm=round(p['mesh'].extents[2],2)))
    with (folder/'parts.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    # A small JSON mesh bundle for the engineering renderer and independent QA.
    data=[dict(name=p['name'],group=p['group'],material=p['material'],v=np.round(p['mesh'].vertices,5).tolist(),f=p['mesh'].faces.tolist()) for p in d['parts']]
    (WORK/f'variant-{k:02d}-meshes.json').write_text(json.dumps(data,separators=(',',':')))
    (folder/'parameters.json').write_text(json.dumps(dict(width_mm=1000,height_mm=1200,depth_mm=350,plywood_mm=18,back_mm=6,shelf_depth_mm=230,node_diameter_mm=72,levels_mm=LEVELS,divider_positions_mm=d['divs'],node_count=len(d['joints']),frame_bolts=16 if k==3 else 14,spherical_node_bolts=sum(j['ports'].__len__() for j in d['joints']),door_hinges='Supplier CLIP inset hinges, preinstalled; exact linkage pending',status='engineering study / NOT a fabrication release'),indent=2))

if __name__=='__main__':
    reports={}
    for k in [3,4]:
        print('Building variant',k,flush=True);d=build(k);write_outputs(d)
        print('Checking static intersections',k,len(d['parts']),flush=True);static=meshchecks(d)
        print('Static overlaps',len(static['unintended_overlaps']),flush=True)
        print('Checking sampled assembly motions',k,flush=True);moves=motionchecks(d)
        reports[str(k)]=dict(static=static,motion=moves)
        (OUT/f'variant-{k:02d}/verification.json').write_text(json.dumps(reports[str(k)],indent=2))
        print('Motion collisions',sum(len(s['collisions']) for s in moves['sequence']),'door',sum(len(s['collisions']) for s in moves['door_sweeps']),flush=True)
    (OUT/'verification-summary.json').write_text(json.dumps(reports,indent=2))
    prototypes=OUT/'joint-prototype';prototypes.mkdir(exist_ok=True)
    body,hw,holes,ports,info=node_model(1,[1]);body.export(prototypes/'sphere-T-up-18mm-gap06.stl')
    grip=next(m.copy() for n,m,mat in hw if n=='0-knob');grip.apply_translation([-20,7,-17]);grip.export(prototypes/'finger-grip-for-M5x60.stl')
    fit=cube([0,0,0],[115,35,12]);fitcuts=[]
    for x,g in [(20,.2),(57.5,.6),(95,1.0)]:fitcuts.append(cube([x-(18+g)/2,-1,3],[x+(18+g)/2,30,13]))
    diff(fit,fitcuts).export(prototypes/'fit-coupon-slots-18p2-18p6-19p0.stl')
    A=cube([-90,-20,-9],[90,210,9]);B=cube([-9,-20,3],[9,210,180])
    A=diff(A,[cube([-9.3,-21,2.7],[9.3,211,10]),holes[0]])
    B=diff(B,[holes[1]])
    A.export(prototypes/'plywood-shelf-coupon.stl');B.export(prototypes/'plywood-divider-coupon.stl')
    sc=tm.Scene()
    for name,m,mat in [('shelf',A,'wood'),('divider',B,'wood'),('sphere',body,'node'),*hw]:
        m=m.copy();m.visual.vertex_colors=COLORS[mat];sc.add_geometry(m,node_name=name)
    sc.apply_transform(tm.transformations.rotation_matrix(-math.pi/2,[1,0,0]));sc.apply_transform(np.diag([.001,.001,.001,1]));sc.export(prototypes/'test-joint.glb')
    (prototypes/'geometry.json').write_text(json.dumps(info,indent=2))
    print('DONE',flush=True)
