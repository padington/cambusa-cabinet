"""Record the unresolved Blum candidate; never promote a closed pose alone."""
import json

from blum_inset import build, posed, linkage_residual
from build_concealed_cabinet import OUT, cabinet_structure, audit_contacts
from build_pegboard_cabinet import right_parts


def main():
    fixed,*_=cabinet_structure()
    moving,machining=build(fixed)
    report=dict(status='NOT RELEASED', geometry_scope='Three factory bodies; cup, housing and plate are envelopes',
                purpose='Candidate only; overview retains RSI 3025 from v28',poses={})
    for angle in (0,55,90,100,110):
        bad,threads=audit_contacts(fixed+right_parts(0)+posed(moving,angle))
        report['poses'][angle]=dict(unexpected_contacts=bad,thread_contacts=len(threads))
    report['maximum_pin_link_residual_mm']=max(linkage_residual(i/10) for i in range(1101))
    report['next_step']='Resolve the link-to-wood interference at 110 degrees against manufacturer CAD/datums before ordering or replacing the current hinge.'
    OUT.mkdir(exist_ok=True)
    (OUT/'concealed-hinge-candidate.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('Concealed candidate recorded; collisions at 110:',len(report['poses'][110]['unexpected_contacts']))


if __name__=='__main__':main()
