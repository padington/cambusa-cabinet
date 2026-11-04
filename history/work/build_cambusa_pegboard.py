from pathlib import Path
import sys,json,math,copy,zipfile,csv
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work/vendor'))
import numpy as np
import trimesh as tm
from shapely.geometry import box,Point
from shapely.ops import unary_union
from build_mobile_options import add,ply,panel,rounded,scene,COLORS
from build_assembly_v1 import cube,cylinder,collision_volume
from render_assembly_v1 import render,font
from PIL import Image,ImageDraw

OUT=ROOT/'outputs/cambusa-pegboard-v05';OUT.mkdir(parents=True,exist_ok=True)
D=500
COLORS['inner']=[115,84,57,255]

def wheels(ps):
    from build_mobile_options import wheels as original
    original(ps)
    for p in ps:
        if p['name'].startswith(('caster-2','caster-3')):p['mesh'].apply_translation([0,D-350,0])

def face(ps,name,x0,x1,z0,z1,y=0,t=18,group='door',**kw):
    # Restrained dark handles near the central meeting line, echoing Cambusa.
    add(ps,name,panel(rounded(x0,z0,x1,z1,4),1,y,t),'wood',group,**kw)
    hx=x1-22 if name.startswith('left') else x0+22
    zh=(z0+z1)/2
    add(ps,name+'-handle',panel(rounded(hx-4,zh-38,hx+4,zh+38,3),1,y-7,7),'frame',group,**kw)

def door(ps,name,x0,x1,z0,z1,side):
    pivot=[x0-2 if side=='left' else x1+2,-2,0]
    face(ps,name,x0,x1,z0,z1,pivot=pivot,sign=-1 if side=='left' else 1,owner=name)
    return dict(pivot=pivot,sign=-1 if side=='left' else 1,owner=name)

def drawer(ps,num,z,inside):
    # 435 mm clear cabinet width. A 12 mm wooden box gives an indicative
    # 417 mm exterior / 393 mm interior width, following 560H planning logic.
    front=50 if inside else 18;back=front+390
    common=dict(drawer_id=num,travel_mm=280)
    def item(s,lo,hi,mat='inner'):
        add(ps,f'drawer-{num}-{s}',cube(lo,hi),mat,'drawer',**common)
    item('left',[508,front,z+22],[520,back,z+122])
    item('right',[913,front,z+22],[925,back,z+122])
    item('front-wall',[520,front,z+22],[913,front+12,z+122])
    item('rear-wall',[520,back-12,z+22],[913,back,z+122])
    item('bottom',[508,front,z+13],[925,back,z+22])
    face(ps,f'drawer-{num}-face',507 if inside else 503,926 if inside else 948,z,z+136,
         y=38 if inside else 0,t=12 if inside else 18,group='drawer',**common)
    for j,x in enumerate([502,925]):
        # Separate fixed and moving envelopes only. Exact purchased runner
        # section, fasteners and locking devices are deliberately not claimed.
        add(ps,f'fixed-runner-{num}-{j}',cube([x,front+5,z+1],[x+6,front+395,z+12]),'metal','runner')
        item(f'moving-runner-{j}',[x+1,front+7,z+3],[x+5,front+392,z+11],'frame')

def build(inside):
    ps=[];wheels(ps)
    for x in [0,952]:
        for y in [0,470]:ply(ps,f'profile-post-{x}-{y}',[x,y,104],[x+30,y+30,1200],'frame','profile')
    for j,z in enumerate([104,440,788,1170]):
        for y in [0,470]:
            start=499 if j==1 and y==0 else 30
            ply(ps,f'profile-cross-{j}-{y}',[start,y,z],[952,y+30,z+30],'frame','profile')
        for x in ([0,952] if j in [0,3] else [0]):
            ply(ps,f'profile-depth-{j}-{x}',[x,30,z],[x+30,470,z+30],'frame','profile')
    for i,z in enumerate([134,470,818,1152]):
        # Left door has 70 mm trays. Recess that part of the middle shelf.
        poly=box(30,30,952,464)
        if i==1:poly=poly.difference(box(29,29,481,104))
        add(ps,f'shelf-{i}',panel(poly,2,z,18))
    for i,(z0,z1) in enumerate([(152,470),(488,818),(836,1152)]):
        ply(ps,f'partition-{i}',[481,32,z0],[499,456,z1])
        ply(ps,f'side-left-{i}',[30,30,z0],[48,464,z1])
        ply(ps,f'side-right-{i}',[934,30,z0],[952,464,z1])
    ply(ps,'back-panel',[48,464,152],[934,470,1152],'back','back')
    holes=[(y,z) for y in range(50,451,50) for z in range(160,1161,50)]
    shape=rounded(0,104,500,1200,7).difference(unary_union([Point(y,z).buffer(6,resolution=4) for y,z in holes]))
    add(ps,'pegboard-full-right',panel(shape,0,982,18),'wood','pegboard')
    meta=door(ps,'left-tall-door',34,477,156,780,'left')
    # These lightweight internal trays move with the left door. Their stop
    # position leaves room for both the middle shelf and the books behind it.
    for k,z in enumerate([220,570]):
        for name,lo,hi in [
            ('bottom',[80,18,z],[440,88,z+9]),
            ('lip',[80,79,z+9],[440,88,z+43]),
            ('left',[80,18,z+9],[89,79,z+43]),
            ('right',[431,18,z+9],[440,79,z+43])]:
            add(ps,f'left-door-tray-{k}-{name}',cube(lo,hi),'inner','door',**meta)
    if inside:door(ps,'right-low-door',503,948,156,432,'right')
    for num,z in enumerate([156,296]):drawer(ps,num,z,inside)
    from build_mobile_options import books
    books(ps,75,130,836,6);books(ps,545,100,488,7)
    # Two 150 mm projecting shelf brackets, each carried by a pegboard stem.
    for yy in [150,350]:
        add(ps,f'accessory-stem-{yy}',cylinder(0,[999,yy,760],5.75,46,16),'frame','accessory')
        ply(ps,f'accessory-bracket-{yy}',[1001,yy-6,722],[1009,yy+6,766],'frame','accessory')
        ply(ps,f'accessory-arm-{yy}',[1009,yy-6,722],[1135,yy+6,734],'frame','accessory')
    ply(ps,'accessory-shelf',[1009,125,734],[1135,375,752],'wood','accessory')
    for yy in [100,250]:
        add(ps,f'accessory-hook-{yy}',cylinder(0,[1010,yy,1010],5.75,58,16),'metal','accessory')
        add(ps,f'accessory-tip-{yy}',cylinder(2,[1038,yy,1020],5,20,16),'metal','accessory')
    return dict(id='inside' if inside else 'outside',title='Ящики за дверцей' if inside else 'Ящики снаружи',
                detail='Два внутренних ящика; сначала открыть правую дверцу.' if inside else 'Прямой доступ к двум ящикам; слева дверца с лотками.',
                parts=ps,peg_holes=holes)

def transformed(b,doors=0,pull=0,index=1,accessories=True):
    result=[]
    for p in b['parts']:
        if not accessories and p['group']=='accessory':continue
        q=p.copy();q['mesh']=p['mesh'].copy()
        if p['group']=='door':
            q['mesh'].apply_transform(tm.transformations.rotation_matrix(p['sign']*doors*math.pi/180,[0,0,1],point=p['pivot']))
        elif p['group']=='drawer' and p['drawer_id']==index:q['mesh'].apply_translation([0,-pull,0])
        result.append(q)
    return result

def encode(ps):
    out=[]
    for p in ps:
        m=p['mesh'];q={k:v for k,v in p.items() if k!='mesh'}
        q.update(v=np.round(m.vertices,2).tolist(),f=m.faces.tolist())
        axis=0 if p['name'].startswith(('pegboard','side','partition')) else 2 if p['name'].startswith(('shelf','accessory-shelf')) else 1
        q['edge']=(np.abs(m.face_normals[:,axis])<.6).astype(int).tolist() if p['material'] in ['wood','inner'] else []
        out.append(q)
    return out

def main():
    models=[build(False),build(True)];reports=[]
    for b in models:
        print('Exporting',b['id'],flush=True)
        (OUT/(b['id']+'-closed.glb')).write_bytes(scene(b['parts']).export(file_type='glb'))
        view=transformed(b,110 if b['id']=='inside' else 80,250,1)
        (OUT/(b['id']+'-open.glb')).write_bytes(scene(view).export(file_type='glb'))
        render(b['parts'],900,940,yaw=36,pitch=17).save(OUT/(b['id']+'-closed.png'))
        render(view,900,940,yaw=36,pitch=17).save(OUT/(b['id']+'-open.png'))
        invalid=[p['name'] for p in b['parts'] if not p['mesh'].is_volume]
        assert not invalid,invalid
        structural=[p for p in b['parts'] if p['group'] in ['body','profile','back','pegboard','door']]
        hits=[]
        for i,p in enumerate(structural):
            for q in structural[i+1:]:
                if p.get('owner') and p.get('owner')==q.get('owner'):continue
                v=collision_volume(p['mesh'],q['mesh'])
                if v>.2:hits.append([p['name'],q['name'],round(v,2)])
        reports.append(dict(id=b['id'],closed_major_panel_intersections=hits,invalid_meshes=invalid,holes=len(b['peg_holes']),
                            note='Appearance study. Exact hardware, installation, retention and strength have not been validated.'))
    canvas=Image.new('RGB',(1800,1090),'#f6f5f1');dr=ImageDraw.Draw(canvas)
    for i,b in enumerate(models):
        canvas.paste(Image.open(OUT/(b['id']+'-open.png')),(900*i,100))
        dr.text((900*i+30,25),b['title'],font=font(33),fill='#29302a')
        dr.text((900*i+30,72),'100 × 120 × 50 см · перфорация на всей боковине',font=font(22),fill='#60665e')
    dr.text((30,1045),'Компоновка по идее Cambusa Fly · точная фурнитура, крепление навесов и устойчивость ещё не проверены',font=font(24),fill='#60665e')
    canvas.save(OUT/'comparison.png')
    # Shared geometry is stored once to keep the inline model compact.
    encoded=[encode(b['parts']) for b in models]
    lookup={p['name']:p for p in encoded[1]}
    shared=[p for p in encoded[0] if p['name'] in lookup and p==lookup[p['name']]]
    shared_names={p['name'] for p in shared}
    data=dict(shared=shared,colors=COLORS,models=[dict(id=b['id'],title=b['title'],detail=b['detail'],parts=[p for p in ep if p['name'] not in shared_names]) for b,ep in zip(models,encoded)])
    payload=json.dumps(data,ensure_ascii=False,separators=(',',':'))
    (ROOT/'work/cambusa-pegboard-data.json').write_text(payload)
    (OUT/'geometry-checks.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2))
    with (OUT/'pegboard-hole-centres-mm.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['depth_y_mm','height_z_from_floor_mm','diameter_mm']);w.writerows((y,z,12) for y,z in models[0]['peg_holes'])
    print(json.dumps(dict(payload_bytes=len(payload.encode()),shared_parts=len(shared),checks=reports),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
