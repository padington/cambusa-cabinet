"""Reconcile the v30 model with complete wood blanks and Russian stock sizes.

This estimates procurement, not CNC toolpaths or fabrication release.
"""
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

from audit_assembly import load_parts
from build_pegboard_cabinet import right_leaf
from build_right_lift import SECTIONS, pose
from build_pegboard_cabinet import slot_end

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/cambusa-v30-costs-rf'
MODEL = ROOT / 'outputs/cambusa-v30-review-fixes/cabinet-0.glb'


def read_csv(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        w.writeheader(); w.writerows(rows)


def wood_parts(model):
    result = []
    for row in read_csv(ROOT/'outputs/cambusa-v30-review-fixes/panels-and-shelves.csv'):
        names = ['Floor-Left-8','Floor-Right-8'] if row['part']=='Floor-8' else [row['part']]
        assert len(names)==int(row['count'])
        for name in names:
            a,b,t = (float(row[k]) for k in ('a_mm','b_mm','stock_mm'))
            assert np.allclose(sorted(model[name].extents),sorted([a,b,t]),atol=.003),name
            result.append(dict(part=name,a_mm=a,b_mm=b,stock_mm=t,area_m2=a*b/1e6,
                               perimeter_m=2*(a+b)/1000,source='v30 body CSV + GLB'))
    # Right facades are tilted in the assembly. Use their unposed source
    # shapes; an axis-aligned bounding box of the tilted mesh is not a blank.
    for i,(_,top) in enumerate(SECTIONS,1):
        for p in right_leaf(top):
            name=f"{p['name']}-{i}"
            placed=pose(p,top,0,slot_end(top))['mesh']
            assert np.allclose(placed.bounds,model[name].bounds,atol=.003),name
            if p['name']=='Display-ledge':continue
            a,t,b = (round(float(v),3) for v in p['mesh'].extents)
            assert t in (6,18)
            result.append(dict(part=name,a_mm=a,b_mm=b,stock_mm=t,area_m2=a*b/1e6,
                               perimeter_m=2*(a+b)/1000,source='right_leaf local shape + posed GLB'))
    assert len(result)==28 and len({r['part'] for r in result})==28
    return result


def sheets(parts):
    """MaxRects, no common-line cutting; 10 mm edge trim and 8 mm gap."""
    result=[]
    for t in sorted({p['stock_mm'] for p in parts}):
        layouts=[]
        for p in sorted([r for r in parts if r['stock_mm']==t],key=lambda r:r['area_m2'],reverse=True):
            choices=[]
            for li,l in enumerate(layouts):
                for x,y,w,h in l['free']:
                    for a,b in {(p['a_mm'],p['b_mm']),(p['b_mm'],p['a_mm'])}:
                        if a+8<=w+.001 and b+8<=h+.001:
                            choices.append((min(w-a-8,h-b-8),w*h-(a+8)*(b+8),li,x,y,a,b))
            if not choices:
                layouts.append(dict(thickness_mm=t,sheet=len(layouts)+1,size_mm=[1525,1525],
                                    free=[(10,10,1513,1513)],pieces=[]))
                for a,b in {(p['a_mm'],p['b_mm']),(p['b_mm'],p['a_mm'])}:
                    if a<=1505 and b<=1505:
                        choices.append((min(1505-a,1505-b),0,len(layouts)-1,10,10,a,b))
            _,_,li,x,y,a,b=min(choices)
            l=layouts[li];px,py,pw,ph=x,y,a+8,b+8
            free=[]
            for fx,fy,fw,fh in l['free']:
                if px>=fx+fw or px+pw<=fx or py>=fy+fh or py+ph<=fy:
                    free.append((fx,fy,fw,fh));continue
                if px>fx:free.append((fx,fy,px-fx,fh))
                if px+pw<fx+fw:free.append((px+pw,fy,fx+fw-px-pw,fh))
                if py>fy:free.append((fx,fy,fw,py-fy))
                if py+ph<fy+fh:free.append((fx,py+ph,fw,fy+fh-py-ph))
            free=list(dict.fromkeys(r for r in free if min(r[2:])>.001))
            l['free']=[r for i,r in enumerate(free) if not any(
                i!=j and r[0]>=s[0] and r[1]>=s[1] and r[0]+r[2]<=s[0]+s[2] and
                r[1]+r[3]<=s[1]+s[3] for j,s in enumerate(free))]
            l['pieces'].append(dict(part=p['part'],xy_mm=[x,y],size_mm=[a,b]))
        for l in layouts:
            del l['free'];result.append(l)
    seen=Counter()
    for l in result:
        for i,p in enumerate(l['pieces']):
            seen[p['part']]+=1
            x,y=p['xy_mm'];a,b=p['size_mm']
            assert min(x,y)>=10 and x+a<=1515 and y+b<=1515
            for q in l['pieces'][i+1:]:
                qx,qy=q['xy_mm'];qa,qb=q['size_mm']
                assert x+a+8<=qx+.001 or qx+qa+8<=x+.001 or y+b+8<=qy+.001 or qy+qb+8<=y+.001
    assert seen==Counter(p['part'] for p in parts)
    return result


def bars(model):
    parts=[]
    for r in read_csv(ROOT/'outputs/cambusa-v29-concealed-hardware/profile-cuts.csv'):
        length=float(r['length_mm'])
        assert abs(max(model[r['part']].extents)-length)<.003
        parts.append(dict(part=r['part'],length_mm=length))
    parts.sort(key=lambda r:(-r['length_mm'],r['part']))
    # Supplier permits anodizing contact marks up to 55 mm at each end.
    # Reserve 60 mm at each end, plus a 5 mm kerf for every retained part.
    stock,trim,kerf=3040,60,5
    capacity=stock-2*trim
    def attempt(count):
        loads=[0.0]*count;groups=[[] for _ in loads];dead=set()
        def visit(i):
            if i==len(parts):return [list(g) for g in groups]
            key=(i,tuple(sorted(loads)))
            if key in dead:return None
            required=parts[i]['length_mm']+kerf;seen=set()
            for j,used in enumerate(loads):
                if used in seen or used+required>capacity:continue
                seen.add(used);loads[j]+=required;groups[j].append(parts[i])
                found=visit(i+1)
                if found:return found
                groups[j].pop();loads[j]-=required
            dead.add(key)
            return None
        return visit(0)
    failed=[]
    for n in range(math.ceil(sum(p['length_mm']+kerf for p in parts)/capacity),len(parts)+1):
        packed=attempt(n)
        if packed:break
        failed.append(n)
    layouts=[]
    for i,group in enumerate(packed,1):
        start=trim;rows=[]
        for p in group:
            rows.append(dict(p,start_mm=start));start+=p['length_mm']+kerf
        assert start<=stock-trim
        layouts.append(dict(bar=i,stock_mm=stock,trim_each_end_mm=trim,kerf_mm=kerf,
                            remainder_mm=stock-trim-start,pieces=rows))
    assert Counter(p['part'] for l in layouts for p in l['pieces'])==Counter(p['part'] for p in parts)
    return parts,layouts,failed


def draw_sheet_plan(layouts):
    w,h=1040,70+math.ceil(len(layouts)/3)*390
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img">',
         '<title>Раскладка фанеры v30, полные листы 1525 × 1525</title>',
         '<rect width="100%" height="100%" fill="#faf9f5"/>',
         '<text x="20" y="30" font-family="Arial" font-size="20">v30 · все 28 деревянных деталей · зазор 8 мм</text>']
    for i,l in enumerate(layouts):
        ox,oy=20+(i%3)*340,75+(i//3)*390;s=.2
        svg.append(f'<text x="{ox}" y="{oy-14}" font-family="Arial" font-size="15">{l["thickness_mm"]:g} мм · лист {l["sheet"]}</text>')
        svg.append(f'<rect x="{ox}" y="{oy}" width="305" height="305" fill="white" stroke="#6c6c6c"/>')
        for j,p in enumerate(l['pieces']):
            x,y=p['xy_mm'];a,b=p['size_mm'];label=escape(p['part'])
            fill=['#d8bea0','#d5d8c9','#c4d1d5'][j%3]
            svg.append(f'<rect x="{ox+x*s}" y="{oy+y*s}" width="{a*s}" height="{b*s}" fill="{fill}" stroke="#635547" stroke-width=".4"><title>{label}: {a:g} × {b:g} мм</title></rect>')
            code=next(k+1 for k,r in enumerate(ALL_WOOD) if r['part']==p['part'])
            if min(a,b)*s>=11:
                svg.append(f'<text x="{ox+(x+a/2)*s}" y="{oy+(y+b/2)*s}" text-anchor="middle" font-size="11" font-family="Arial">{code}</text>')
    svg.append('</svg>')
    (OUT/'cut-plan.svg').write_text('\n'.join(svg)+'\n')


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    model=load_parts(MODEL)
    ALL_WOOD=wood_parts(model)
    layout=sheets(ALL_WOOD)
    profile,bar_layout,failed=bars(model)
    write_csv(OUT/'wood-parts.csv',[dict(code=i+1,**p) for i,p in enumerate(ALL_WOOD)])
    write_csv(OUT/'profile-parts.csv',profile)
    write_csv(OUT/'profile-cut-plan.csv',[dict(bar=l['bar'],**p) for l in bar_layout for p in l['pieces']])
    part_rows=[dict(name=n,bounds_mm=np.round(m.bounds,3).tolist()) for n,m in model.items()]
    (OUT/'model-inventory.json').write_text(json.dumps(part_rows,indent=2)+'\n')
    plan=dict(version='cambusa-v30',model_sha256=hashlib.sha256(MODEL.read_bytes()).hexdigest(),
              wood=ALL_WOOD,sheets=layout,profile_parts=profile,bars=bar_layout,
              infeasible_profile_bar_counts=failed,
              profile_net_m=sum(r['length_mm'] for r in profile)/1000,
              profile_purchase_m=round(len(bar_layout)*3.04,3),
              profile_billable_cuts=len(profile)+2*len(bar_layout),
              plywood_purchase_sheets=dict(Counter(str(int(l['thickness_mm'])) for l in layout)),
              surface_area_m2=round(sum(2*p['area_m2']+p['perimeter_m']*p['stock_mm']/1000 for p in ALL_WOOD),6),
              sheet_edge_trim_mm=10,part_clearance_mm=8,grain_orientation_approved=False,
              fabrication_release=False)
    (OUT/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    draw_sheet_plan(layout)
    print(json.dumps({k:v for k,v in plan.items() if k not in ('wood','sheets','profile_parts','bars')},ensure_ascii=False,indent=2))
