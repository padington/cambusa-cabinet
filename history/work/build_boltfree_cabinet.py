"""Bolt-free carcass study; exact hinge installation and loads remain unvalidated."""
from pathlib import Path
import sys,math,json,csv,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'work/vendor'))
import numpy as np
import trimesh as tm
from shapely.geometry import box,Polygon,Point
from shapely.affinity import rotate
from shapely.ops import unary_union
from build_assembly_v1 import cube,diff,extrude,components,collision_volume,overlap,yz_mesh,xz_mesh,COLORS
from build_bayonet_node import build as prototype,local_to_world,cyl_local,pin_transform,d as PIN_AXIS,c as PIN_CENTER

OUT=ROOT/'outputs/boltfree-cabinet-v03';OUT.mkdir(exist_ok=True,parents=True)
WORK=ROOT/'work/boltfree-v03';WORK.mkdir(exist_ok=True)
R=45.;XL,XR=45.,955.;LEVELS=[170.,500.,830.,1155.];REAR=305.
COLORS['key']=[65,69,66,255]
BASE=prototype(); SPHERE=BASE['sphere']
HP=box(11.4,-4,32.6,4).buffer(-2).buffer(2)
VC=box(-4,12.3,4,38.5).buffer(-2).buffer(2)
H_WINDOW=extrude(HP,22).apply_translation([0,0,-11])
V_WINDOW=yz_mesh(VC,-11,22)

def moved(m,M):
    x=m.copy();x.apply_transform(M);return x
def mirror(x=1,y=1,z=1,center=(0,0,0)):
    M=np.diag([x,y,z,1.]);M[:3,3]=center;return M
def sector_wood_cuts():
    return [local_to_world(cyl_local(3.4,-80,70)),local_to_world(cyl_local(8.9,-65,-33.8)),
            local_to_world(cube([-1.5,-5.6,-65],[1.5,5.6,-30.1])),local_to_world(cyl_local(5.6,-31.9,-30.1)),
            local_to_world(cube([-5.6,-1.5,-32.8],[5.6,1.5,-30.8])),
            *[local_to_world(cyl_local(5.8,-65,-33.8,xy=(0,y))) for y in [-14.,14.]]]
CUTS=sector_wood_cuts();CACHE={}
def connector(kind):
    if kind in CACHE:return CACHE[kind]
    # All slots open at the rear; the deeper start clears sloping frame edges.
    cuts=[cube([-60,-25.6,-9.3],[60,65,9.3])]
    cuts.append(cube([-9.3,-25.6,-65 if kind in ['side','X'] else 2.7],[9.3,65,65]))
    configs=[np.eye(4)]
    if kind=='X':configs.append(mirror(-1,1,-1))
    for cfg in configs:cuts.extend(moved(q,cfg) for q in CUTS)
    body=diff(SPHERE,cuts)
    assert body.is_volume and components(body)==1,(kind,components(body))
    CACHE[kind]=(body,configs)
    return CACHE[kind]

def cap_geometry(H,back_top):
    # Local u points inward from the side frame, v points rearward, z is height.
    foot0=back_top-H+3.0
    stem=cyl_local(3.,-20,-3.8)
    # cyl_local uses the third coordinate directly; these cap meshes stay in u,v,z.
    head=cube([-4,-4,-4],[20,4,0])
    foot=cube([14,-4,foot0],[20,4,-3.8])
    lugs=[cube([2.6,-1,-15.5],[5,1,-14.1]),cube([-5,-1,-15.5],[-2.6,1,-14.1])]
    cap=tm.boolean.union([stem,head,foot,*lugs],engine='manifold')
    bore=cyl_local(3.4,-22,2)
    # A capsule is used directly because the negative buffer of a 3 mm slot
    # collapses at exactly its radius.
    entryp=box(-1.5,-4.3,1.5,4.3).union(Point(0,-4.3).buffer(1.5)).union(Point(0,4.3).buffer(1.5))
    entry=extrude(entryp,22);entry.apply_translation([0,0,-20])
    # These rectangular windows are through-milled from the broad frame faces.
    rotation=yz_mesh(box(-5.8,-20,5.8,-15.4).buffer(-2).buffer(2),-8,22)
    stopp=box(-1.5,-17.5,1.5,-15).union(Point(0,-17.5).buffer(1.5)).union(Point(0,-15).buffer(1.5))
    stop=yz_mesh(stopp,-8,22)
    head_clear=cyl_local(21.5,-6.5,2)
    arc=unary_union([rotate(box(13.5,-4.5,20.5,4.5),a,origin=(0,0)) for a in np.arange(0,90.1,3)]).buffer(.3)
    sweep=extrude(arc,-3.5-(foot0-2.4));sweep.apply_translation([0,0,foot0-2.4])
    return cap,[bore,entry,rotation,stop,head_clear,sweep]

def build(kind):
    ps=[];cutters={};node_defs=[];caps=[];shelf_fore={};profiles={}
    def add(name,m,mat,group,**meta):
        ps.append(dict(name=name,mesh=m,material=mat,group=group,**meta));cutters[name]=[]
    heights={'left':1200 if kind==3 else 875,'right':1200}
    for side,x in [('left',XL),('right',XR)]:
        H=heights[side]
        poly=Polygon([(0,0),(45,0),(70,145),(280,145),(300,0),(350,0),(350,H),(85,H),(30,170),(30,110)])
        poly=poly.buffer(-5).buffer(5)
        profiles[side]=poly
        add('frame-'+side,yz_mesh(poly,x-9,18),'wood','wood',thickness=18)
        for k,z in enumerate(LEVELS):
            if z>H:continue
            # Minimum front coordinate over the entire sphere's z span.
            fore=poly.intersection(box(-20,z-R,200,z+R)).bounds[0]
            shelf_fore[side,k]=fore
            xx=(x+2.7,x+9.3) if side=='left' else (x-9.3,x-2.7)
            # Extra travel beyond the shelf's rear edge permits a 4 mm cutter's
            # rounded closed corners without touching the rectangular shelf.
            pocket=box(fore-3,z-9.3,REAR+3,z+9.3).buffer(-2).buffer(2)
            cutters['frame-'+side].append(yz_mesh(pocket,xx[0],xx[1]-xx[0]))
        xx=(x+2.7,x+9.3) if side=='left' else (x-9.3,x-2.7)
        back_groove=box(331.7,153.7,338.3,H+2).buffer(-2).buffer(2)
        cutters['frame-'+side].append(yz_mesh(back_groove,xx[0],xx[1]-xx[0]))
    for k,z in enumerate(LEVELS):
        right=shelf_fore['right',k]
        if kind==4 and k==3:front=[(603,90),(855,90),(915,right),(952,right)]
        else:
            left=shelf_fore['left',k]
            front=[(48,left),(85,left),(145,90),(855,90),(915,right),(952,right)]
        poly=Polygon([*front,(952,REAR),(front[0][0],REAR)])
        add(f'shelf-{k}',extrude(poly,18).apply_translation([0,0,z-9]),'wood','wood',thickness=18)
    divs=[600.,350.,700.] if kind==3 else [600.]*3
    for row,x in enumerate(divs):
        lo,hi=LEVELS[row:row+2]
        add(f'partition-{row}',cube([x-9,90,lo+3],[x+9,REAR,hi-3]),'wood','wood',thickness=18)
        cutters[f'shelf-{row}'].append(cube([x-9.3,89.7,lo+2.7],[x+9.3,REAR+.3,lo+10]))
        cutters[f'shelf-{row+1}'].append(cube([x-9.3,89.7,hi-10],[x+9.3,REAR+.3,hi-2.7]))
    # Each definition names the exact wooden parts captured by each pin.
    for side,x,sx in [('left',XL,1),('right',XR,-1)]:
        for k,z in enumerate(LEVELS):
            if ('left',k) not in shelf_fore and side=='left':continue
            fore=shelf_fore[side,k]
            node_defs.append(dict(name=f'side-{side}-{k}',kind='side',T=mirror(sx,1,1,(x,fore+20,z)),connections=[(f'shelf-{k}','frame-'+side)],rear=False))
    junctions={}
    for row,x in enumerate(divs):
        junctions.setdefault((x,row),[]).append((1,row))
        junctions.setdefault((x,row+1),[]).append((-1,row))
    for (x,k),branches in junctions.items():
        for rear in [False,True]:
            yy=REAR-20 if rear else 110
            if len(branches)==2:
                ntype='X';sx=1;sz=1
                # +/+ key captures upright above, -/- key captures upright below.
                connections=[(f'shelf-{k}',f'partition-{k}'),(f'shelf-{k}',f'partition-{k-1}')]
            else:
                ntype='T';v,row=branches[0];sz=v
                sx=1 # top-right-only shelf must retain material on its right.
                connections=[(f'shelf-{k}',f'partition-{row}')]
            node_defs.append(dict(name=f'inner-x{int(x)}-{k}-'+('rear' if rear else 'front'),kind=ntype,T=mirror(sx,-1 if rear else 1,sz,(x,yy,LEVELS[k])),connections=connections,rear=rear))
    for nd in node_defs:
        body,cfgs=connector(nd['kind']);name='sphere-'+nd['name']
        add(name,moved(body,nd['T']),'node','node',owner=nd['name'],rear=nd['rear'],T=nd['T'].tolist())
        for j,cfg in enumerate(cfgs):
            M=nd['T']@cfg
            add('key-'+nd['name']+f'-{j}',moved(BASE['key'],M),'key','key',owner=name,T=M.tolist())
            hn,vn=nd['connections'][j]
            cutters[hn].append(moved(H_WINDOW,M));cutters[vn].append(moved(V_WINDOW,M))
    # One captured plywood back and two positive quarter-turn top stops.
    if kind==3:poly=box(48,154,952,1176)
    else:poly=Polygon([(48,154),(952,154),(952,1176),(595,1176),(595,854),(48,854)])
    back=xz_mesh(poly,332,6)
    # Factory-machined 1.5 mm lower-edge chamfers clear the rounded ends of the
    # top-open side grooves while leaving a flat supporting lower edge.
    bevels=[Polygon([(331.9,153.9),(333.6,153.9),(331.9,155.6)]),Polygon([(338.1,153.9),(336.4,153.9),(338.1,155.6)])]
    back=diff(back,[yz_mesh(q,47,906) for q in bevels])
    add('back-panel',back,'back','back',thickness=6)
    for side,xx,sx in [('left',42,1),('right',958,-1)]:
        H=heights[side];bt=1176 if side=='right' or kind==3 else 854
        cap,holes=cap_geometry(H,bt);M=mirror(sx,1,1,(xx,335,H))
        add('back-stop-'+side,moved(cap,M),'key','cap',side=side,T=M.tolist())
        cutters['frame-'+side].extend(moved(q,M) for q in holes)
        caps.append(dict(name='back-stop-'+side,T=M.tolist(),back_top=bt))
    # Optional factory-prepared clip-on hinges; hardware is not modelled as a
    # validated commercial linkage. The wood is kept separate from corpus joints.
    ds=[(57,588,182,488,'left','graphite'),(712,943,842,1143,'right','wood')] if kind==3 else [(57,588,182,488,'left','wood'),(612,943,512,818,'right','graphite')]
    door_defs=[]
    for i,(a,b,lo,hi,side,mat) in enumerate(ds):
        # Each front is set at the relevant sloping frame's forward contour,
        # rather than floating 50 mm in front of the upper side panel.
        front_y=round(profiles[side].intersection(box(-20,hi-.01,200,hi+.01)).bounds[0])
        rear_y=front_y+18
        poly=box(a,lo,b,hi).buffer(-3).buffer(3)
        hx=b-28 if side=='left' else a+28
        poly=poly.difference(box(hx-6,(lo+hi)/2-22,hx+6,(lo+hi)/2+22).buffer(6))
        pivot=[a-3 if side=='left' else b+3,front_y-3,0]
        sign=-1 if side=='left' else 1
        # Conservative round reliefs account for the sphere throughout the
        # proposed 86-degree sweep, not only when the front is closed.
        reliefs=[]
        for nd in node_defs:
            if nd['rear']:continue
            for angle in np.arange(0,86.1,1):
                inv=tm.transformations.rotation_matrix(-sign*math.radians(angle),[0,0,1],point=pivot)
                cc=(inv@np.r_[nd['T'][:3,3],1])[:3]
                distance=max(0,cc[1]-rear_y,front_y-cc[1])
                if distance<R:
                    radius=math.sqrt(R*R-distance*distance)+1.5
                    if cc[0]+radius<a or cc[0]-radius>b or cc[2]+radius<lo or cc[2]-radius>hi:continue
                    reliefs.append(Point(cc[0],cc[2]).buffer(radius,quad_segs=32))
        if reliefs:poly=poly.difference(unary_union(reliefs))
        m=xz_mesh(poly,front_y,18)
        cx=a+20.5 if side=='left' else b-20.5
        for zz in [lo+50,hi-50]:
            hole=tm.creation.cylinder(17.5,14,sections=48);hole.apply_transform(tm.transformations.rotation_matrix(math.pi/2,[1,0,0]));hole.apply_translation([cx,front_y+12,zz]);m=diff(m,[hole])
        add(f'door-{i}',m,mat,'door',thickness=18)
        door_defs.append(dict(name=f'door-{i}',pivot=pivot,sign=sign,opening_limit_deg=86,front_y_mm=front_y))
    for p in ps:
        if cutters[p['name']]:p['mesh']=diff(p['mesh'],cutters[p['name']])
        assert p['mesh'].is_volume and components(p['mesh'])==1,(p['name'],components(p['mesh']))
    return dict(kind=kind,parts=ps,nodes=node_defs,caps=caps,doors=door_defs,divs=divs)

def static_check(b):
    ps=b['parts'];bad=[];count=0;exact=0
    for i,a in enumerate(ps):
        for q in ps[i+1:]:
            count+=1
            if overlap(a['mesh'],q['mesh']):
                exact+=1;v=collision_volume(a['mesh'],q['mesh'])
                if v>.05:bad.append(dict(a=a['name'],b=q['name'],mm3=round(v,4)))
    return dict(parts=len(ps),pairs=count,exact_pairs=exact,all_watertight=all(p['mesh'].is_watertight for p in ps),overlaps=bad)

def retention_check(b):
    ps={p['name']:p for p in b['parts']};results=[]
    for nd in b['nodes']:
        body='sphere-'+nd['name'];woods=sorted({w for pair in nd['connections'] for w in pair})
        names=[body]+[p['name'] for p in b['parts'] if p.get('owner')==body]
        delta=np.array([0,4 if nd['rear'] else -4,0]);vol=0.
        for n in names:
            m=ps[n]['mesh'].copy();m.apply_translation(delta)
            for w in woods:vol+=collision_volume(m,ps[w]['mesh'])
        results.append(dict(joint=nd['name'],attempt='withdraw locked sphere 4 mm along installation axis',obstruction_mm3=round(vol,4),blocked=vol>.05))
    for cap in b['caps']:
        p=ps[cap['name']];C=np.array(cap['T']);Ci=np.linalg.inv(C);frame=ps['frame-'+p['side']]['mesh']
        M=np.eye(4);M[2,3]=2.;v=collision_volume(moved(p['mesh'],C@M@Ci),frame)
        results.append(dict(joint=p['name'],attempt='lift locked stop 2 mm',obstruction_mm3=round(v,4),blocked=v>.05))
        M=tm.transformations.rotation_matrix(math.radians(30),[0,0,1]);v=collision_volume(moved(p['mesh'],C@M@Ci),frame)
        results.append(dict(joint=p['name'],attempt='turn locked stop 30 degrees without pressing',obstruction_mm3=round(v,4),blocked=v>.05))
        back=ps['back-panel']['mesh'].copy();back.apply_translation([0,0,4]);v=collision_volume(back,p['mesh'])
        results.append(dict(joint=p['name'],attempt='lift back panel 4 mm',obstruction_mm3=round(v,4),blocked=v>.05))
    return dict(checks=results,all_blocked=all(v['blocked'] for v in results),scope='Positive mesh obstruction only; NOT a retention-force, wear or strength test.')

def motion_check(b):
    ps={p['name']:p for p in b['parts']};fixed=[];tests=[]
    def positions(start):return sorted(set([0.,start,*[x for x in [.1,.3,.5,1,2,3,4,5,6,8,10,15,20,30,50,80,120,200,400,800] if x<start]]),reverse=True)
    def test(label,names,matrices):
        hits=[]
        for idx,M in enumerate(matrices):
            for name in names:
                m=moved(ps[name]['mesh'],M)
                for q in fixed:
                    v=collision_volume(m,q['mesh'])
                    if v>.05:hits.append(dict(sample=idx,moving=name,fixed=q['name'],mm3=round(v,4)))
        tests.append(dict(step=label,parts=names,samples=len(matrices),collisions=hits));fixed.extend(ps[n] for n in names)
    def translation(axis,start,sign):
        out=[]
        for x in positions(start):
            M=np.eye(4);M[axis,3]=x*sign;out.append(M)
        return out
    test('Base',['shelf-0'],[np.eye(4)])
    for r in range(3):
        test('Place partition',[f'partition-{r}'],translation(2,400,1));test('Place next shelf',[f'shelf-{r+1}'],translation(2,400,1))
    test('Close left frame',['frame-left'],translation(0,1100,-1));test('Close right frame',['frame-right'],translation(0,1100,1))
    for nd in b['nodes']:
        name='sphere-'+nd['name'];test('Slide empty sphere',[name],translation(1,400,1 if nd['rear'] else -1))
        for p in b['parts']:
            if p['group']!='key' or p.get('owner')!=name:continue
            C=np.array(p['T']);Cinv=np.linalg.inv(C)
            seq=[]
            for push in [-100,-70,-40,-20,-10,-5,-2,-1,0,.4,.8]:
                M=tm.transformations.rotation_matrix(-math.pi/2,PIN_AXIS,point=PIN_CENTER);M[:3,3]+=.0
                N=np.eye(4);N[:3,3]=push*PIN_AXIS;seq.append(C@N@M@Cinv)
            for angle in np.arange(-90,1,5):
                M=tm.transformations.rotation_matrix(math.radians(angle),PIN_AXIS,point=PIN_CENTER);N=np.eye(4);N[:3,3]=.8*PIN_AXIS;seq.append(C@N@M@Cinv)
            for push in [.6,.4,.2,0]:
                N=np.eye(4);N[:3,3]=push*PIN_AXIS;seq.append(C@N@Cinv)
            test('Insert, turn and seat printed key',[p['name']],seq)
    test('Slide back down',['back-panel'],translation(2,1250,1))
    for cap in b['caps']:
        C=np.array(cap['T']);Ci=np.linalg.inv(C);seq=[]
        for h in [50,30,20,10,5,2,1,0,-.5,-1,-1.5,-2]:
            M=tm.transformations.rotation_matrix(math.pi/2,[0,0,1]);M[2,3]=h;seq.append(C@M@Ci)
        for a in np.arange(90,-1,-5):
            M=tm.transformations.rotation_matrix(math.radians(a),[0,0,1]);M[2,3]=-2;seq.append(C@M@Ci)
        for h in [-1.5,-1,-.5,0]:
            M=np.eye(4);M[2,3]=h;seq.append(C@M@Ci)
        test('Insert, turn and seat rear stop',[cap['name']],seq)
    doors=[]
    for door in b['doors']:
        hits=[]
        angles=sorted(set([0.,86.,*np.arange(0,86,2)]))
        for angle in angles:
            M=tm.transformations.rotation_matrix(door['sign']*math.radians(angle),[0,0,1],point=door['pivot']);m=moved(ps[door['name']]['mesh'],M)
            for q in fixed:
                v=collision_volume(m,q['mesh'])
                if v>.05:hits.append(dict(angle=float(angle),part=q['name'],mm3=round(v,4)))
        doors.append(dict(name=door['name'],samples=len(angles),limit_deg=86,collisions=hits,scope='ideal pivot sweep only; actual supplier hinge is not modelled'))
    return dict(sequence=tests,door_sweeps=doors,scope='Discrete geometric checks only. Hinge installation, ergonomics, tolerances, loading and material behaviour not validated.')

def export(b):
    dst=OUT/f'variant-{b["kind"]:02d}';dst.mkdir(exist_ok=True)
    for mode in ['assembled','exploded']:
        sc=tm.Scene()
        for p in b['parts']:
            m=p['mesh'].copy()
            if mode=='exploded':
                if p['name']=='frame-left':m.apply_translation([-180,0,0])
                elif p['name']=='frame-right':m.apply_translation([180,0,0])
                elif p['group']=='back':m.apply_translation([0,150,0])
                elif p['group']=='door':m.apply_translation([0,-170,0])
                elif p['group']=='node':m.apply_translation([0,100 if p.get('rear') else -100,0])
                elif p['group']=='key':
                    owner=next(v for v in b['parts'] if v['name']==p['owner']);m.apply_translation([0,100 if owner.get('rear') else -100,0])
                elif p['group']=='cap':m.apply_translation([0,0,70])
            m.visual.vertex_colors=COLORS[p['material']];sc.add_geometry(m,node_name=p['name'])
        sc.apply_transform(tm.transformations.rotation_matrix(-math.pi/2,[1,0,0]));sc.apply_transform(np.diag([.001,.001,.001,1]));sc.export(dst/(mode+'.glb'))
    for p in b['parts']:p['mesh'].export(dst/(p['name']+'.stl'))
    rows=[]
    for p in b['parts']:
        rows.append(dict(part=p['name'],group=p['group'],material=p['material'],x_mm=round(p['mesh'].extents[0],2),y_mm=round(p['mesh'].extents[1],2),z_mm=round(p['mesh'].extents[2],2)))
    with (dst/'parts.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    bounds=np.array([p['mesh'].bounds for p in b['parts']]);lo=bounds[:,0].min(axis=0);hi=bounds[:,1].max(axis=0)
    params=dict(width_mm=1000,height_mm=1200,depth_mm=350,actual_envelope_mm=np.round(hi-lo,3).tolist(),bounds_mm=np.round([lo,hi],3).tolist(),plywood_mm=18,back_mm=6,shelf_main_depth_mm=215,sphere_diameter_mm=90,sphere_count=sum(p['group']=='node' for p in b['parts']),printed_keys=sum(p['group']=='key' for p in b['parts']),back_stops=2,corpus_metal_bolts=0,corpus_screws=0,hinges='User accepted factory-mounted clip-on hinges with hidden screws. Exact hinge/mounting plate and 86-degree stop require fitting before cutting.',door_opening_candidate_deg=86,status='Geometry study; NOT a production release')
    (dst/'parameters.json').write_text(json.dumps(params,indent=2))
    return params

if __name__=='__main__':
    summary={}
    for k in [3,4]:
        print('Building',k,flush=True);b=build(k);params=export(b)
        print('Static',k,flush=True);st=static_check(b);print('Overlaps',len(st['overlaps']),flush=True)
        print('Assembly motion',k,flush=True);mo=motion_check(b)
        retention=retention_check(b)
        summary[str(k)]=dict(parameters=params,static=st,motion=mo,retention=retention)
        (OUT/f'variant-{k:02d}/verification.json').write_text(json.dumps(summary[str(k)],indent=2))
        print('Motion hits',sum(len(s['collisions']) for s in mo['sequence']),'door hits',sum(len(s['collisions']) for s in mo['door_sweeps']),'retention blocked',retention['all_blocked'],flush=True)
    (OUT/'verification-summary.json').write_text(json.dumps(summary,indent=2))
