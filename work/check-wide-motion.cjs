const fs=require('node:fs');
const assert=require('node:assert/strict');
const template=fs.readFileSync('work/viewer-wide-hinge-template.html','utf8');
const code=template.slice(template.indexOf('  function hingeTransform('),template.indexOf('  let drag, scheduled'));
const points=JSON.parse(fs.readFileSync('outputs/wide-hinge-study/linkage.json','utf8')).points;
const transform=new Function('model','radians',code+'return hingeTransform;')({widePoints:points,wideOffset:[43,79.5]},Math.PI/180);
const reference=JSON.parse(fs.readFileSync('outputs/wide-hinge-study/kinematics-reference.json','utf8'));
let worst=0,count=0;
for(const [degrees,bodies] of Object.entries(reference))for(const [body,expected] of Object.entries(bodies)){
 const actual=transform(body,Number(degrees));
 for(const key of ['matrix','shift'])for(let i=0;i<expected[key].length;i++)worst=Math.max(worst,Math.abs(actual[key][i]-expected[key][i]));
 count++;
}
assert.ok(worst<1e-8,`JS/Python transform difference ${worst}`);
fs.writeFileSync('outputs/wide-hinge-study/motion-viewer-checks.json',JSON.stringify({passed:true,body_poses:count,maximum_matrix_or_shift_difference:worst,scope:'Browser six-bar solver matches the geometry solver for seven bodies at six opening angles'},null,2)+'\n');
console.log('Six-bar viewer/geometry agreement:',count,'body poses, maximum difference',worst);
