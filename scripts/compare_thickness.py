"""Compare actual modeled masses and illustrative elastic shelf deflection."""
import json

from audit_assembly import MODEL, ROOT, load_parts

base = load_parts(ROOT/'outputs/cambusa-frame-v17/closed.glb')
light = load_parts(MODEL/'closed.glb')
plywood_density = 680  # kg/m³, Metsä Wood birch at RH 65%.
aluminum_density = 2700  # kg/m³, generic estimate.
modulus = {12:6781,18:7452}  # Weak face-grain direction, N/mm².
changed = ('B01-top-inset','B02-left-pegboard','B03-right-side','B04-back',
           'B10-left-shelf','B11-left-shelf','B20-right-shelf','B21-right-shelf')
assert set(base) == {name for name in light if not name.startswith('ShelfAngle-')}
savings = []
for name in changed:
    before,after = base[name],light[name]
    mass_before = before.volume * plywood_density / 1e9
    mass_after = after.volume * plywood_density / 1e9
    savings.append({'id':name,'v17_kg':round(mass_before,3),'v18_kg':round(mass_after,3),
                    'saved_kg':round(mass_before-mass_after,3)})
plywood_saved = sum((base[name].volume-light[name].volume)*plywood_density/1e9 for name in changed)
angles_added = sum(mesh.volume*aluminum_density/1e9 for name,mesh in light.items() if name.startswith('ShelfAngle-'))
shelf = light['B10-left-shelf']
span, depth, _ = shelf.extents
results = []
for thickness, E in modulus.items():
    inertia = depth * thickness**3 / 12
    self_mass = span*depth*thickness*plywood_density/1e9
    for payload in (10,15,20):
        total = (self_mass+payload)*9.81
        deflection = 5*total*span**3/(384*E*inertia)
        results.append(dict(thickness_mm=thickness, payload_kg=payload, deflection_mm=round(deflection,3)))
data = {
    'compares':['cambusa-v17','cambusa-v18'], 'changed_plywood':savings,
    'plywood_removed_kg':round(plywood_saved,2),'aluminum_added_kg':round(angles_added,2),
    'net_mass_removed_kg':round(plywood_saved-angles_added,2),
    'shelf_span_mm':span,'shelf_depth_mm':depth,'shelf_bending':results,
    'scope':'Nominal solid geometry; mass excludes pending fasteners; simply supported rectangular shelf under uniform short-term load including self-weight',
    'limitations':['Deflection is not a load rating', 'Shelf brackets and center divider attachment require validation',
                   'Long-term creep, impact, concentrated objects and cabinet stability are outside this estimate'],
    'references':[
        'https://www.metsagroup.com/contentassets/8a5519dc6e534fcfa99c06759fbb8bad/metsa_wood_birch_plywood_product_datasheets_en.pdf',
        'https://www.metsagroup.com/contentassets/2e9ddda886f04453825068d3b37afcdc/uk_doc_metsawood_birch_plywood_pf_2022-11-07.pdf',
    ],
}
(MODEL/'МАССА-И-ПОЛКИ.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(f'plywood saved {plywood_saved:.2f} kg, angles {angles_added:.2f} kg, net {plywood_saved-angles_added:.2f} kg')
print(results)
