import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const version=process.argv[2]||'v30';
assert.ok(/^v\d+$/.test(version),'Use a version such as v30 or v31');
const out=path.join(root,`outputs/cambusa-${version}-costs-rf`);
const plan=JSON.parse(await fs.readFile(path.join(out,'plan.json'),'utf8'));
const cost=JSON.parse(await fs.readFile(path.join(out,'estimate.json'),'utf8'));
const wb=Workbook.create();
const summary=wb.worksheets.add('Смета');
const calc=wb.worksheets.add('Расчёт');
const wood=wb.worksheets.add('Дерево');
const profile=wb.worksheets.add('Профиль');
const ink='#252A31',blue='#214C9C',green='#27664A',header='#334451',yellow='#FFF0CC';
const num='#,##0.00;(#,##0.00);"—"';
function values(s,cell,data){s.getRange(cell).writeValues(data);}
function formula(s,cell,f){s.getRange(cell).formulas=[[f]];}
function base(s,last,cols){
  s.showGridLines=false;
  const r=s.getRange(`A1:${cols}${last}`);
  r.format.font={name:'Arial',size:11,color:ink};
  r.format.rowHeight=23;r.format.verticalAlignment='center';
  s.getRange(`A2:${cols}2`).format.font={name:'Arial',size:15,color:ink};
}
function head(s,r){
  s.getRange(r).format={fill:header,font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},
    rowHeight:31,verticalAlignment:'center',horizontalAlignment:'center'};
}
function width(s,col,n,last=100){s.getRange(`${col}1:${col}${last}`).format.columnWidth=n;}
function money(s,r){s.getRange(r).setNumberFormat(num);}

base(wood,42,'N');values(wood,'A2',[[`Деревянные детали ${version}`]]);
values(wood,'A3',[['28 деталей. Размеры относятся к сохранённой модели; изменение размеров требует новой раскладки.']]);
values(wood,'A4',[['мм','Листов','Деталей','Площадь, м²','Контур, м']]);head(wood,'A4:E4');
for(const [i,t] of [6,8,12,18].entries()){
  const r=5+i;values(wood,`A${r}`,[[t,plan.plywood_purchase_sheets[String(t)]]]);
  formula(wood,`C${r}`,`=COUNTIFS($C$13:$C$40,A${r})`);
  formula(wood,`D${r}`,`=SUMIFS($F$13:$F$40,$C$13:$C$40,A${r})`);
  formula(wood,`E${r}`,`=SUMIFS($G$13:$G$40,$C$13:$C$40,A${r})`);
}
values(wood,'A10',[['Листы 1525 × 1525. Поля 10 мм, зазор 8 мм; направление текстуры ещё не согласовано.']]);
values(wood,'A12',[['№','Деталь','Толщ., мм','A, мм','B, мм','Площадь, м²','Контур, м','Покрытие, м²','Лист','X, мм','Y, мм','Размер X','Размер Y','Код модели']]);
head(wood,'A12:N12');
function label(id){
 const map={'Back-infill-8':'Задняя вставка','Floor-Left-8':'Дно левое','Floor-Right-8':'Дно правое',
 'Center-18':'Перегородка','Top-18':'Верхняя панель','Right-roof':'Крыша правых секций',
 'Left-pegboard-18':'Левый пегборд','Right-wall-18':'Правая боковина','Left-door-face-18':'Левая дверь'};
 if(map[id])return map[id];
 if(id.startsWith('Shelf-'))return `Полка ${id.includes('Left')?'левая':'правая'} ${id.at(-1)}`;
 const kind=id.startsWith('Stile-L')?'стойка слева':id.startsWith('Stile-R')?'стойка справа':
 id.startsWith('Top-rail')?'верхняя перемычка':id.startsWith('Bottom-rail')?'нижняя перемычка':'вставка';
 return `Фасад ${id.at(-1)}: ${kind}`;
}
const placements=new Map(plan.sheets.flatMap(l=>l.pieces.map(p=>[p.part,{...p,sheet:`${l.thickness_mm}-${l.sheet}`}])));
for(const [i,p] of plan.wood.entries()){
 const r=13+i,l=placements.get(p.part);
 values(wood,`A${r}`,[[i+1,label(p.part),p.stock_mm,p.a_mm,p.b_mm,null,null,null,l.sheet,...l.xy_mm,...l.size_mm,p.part]]);
 formula(wood,`F${r}`,`=D${r}*E${r}/1000000`);
 formula(wood,`G${r}`,`=2*(D${r}+E${r})/1000`);
 formula(wood,`H${r}`,`=2*F${r}+G${r}*C${r}/1000`);
}
for(const [c,w] of [['A',5],['B',34],['C',12],['D',12],['E',12],['F',16],['G',14],['H',18],['I',10],['J',12],['K',12],['L',12],['M',12],['N',31]])width(wood,c,w,42);
wood.getRange('D5:E8').setNumberFormat('0.000');wood.getRange('F13:H40').setNumberFormat('0.000');
wood.getRange('C13:E40').setNumberFormat('0.0');wood.getRange('J13:M40').setNumberFormat('0.0');
wood.getRange('A13:A40').format.horizontalAlignment='center';
wood.freezePanes.freezeRows(12);wood.freezePanes.freezeColumns(2);

base(profile,34,'G');values(profile,'A2',[['Профиль OB-3030-BLACK']]);
values(profile,'A3',[['Раскладка на хлыстах поставщика. Пять хлыстов проверены перебором и не вмещают комплект.']]);
values(profile,'A4',[['Чистая длина, м']]);formula(profile,'B4','=SUM(C14:C29)/1000');
values(profile,'A5',[['Количество хлыстов']]);formula(profile,'B5','=MAX(A14:A29)');
values(profile,'A6',[['Оплачиваемый метраж, м']]);formula(profile,'B6','=B5*B7/1000');
values(profile,'A7',[['Хлыст, мм',3040]]);values(profile,'A8',[['Отброс с каждого конца, мм',60]]);
values(profile,'A9',[['Пропил, мм',5]]);values(profile,'A10',[['Оплачиваемых резов']]);formula(profile,'B10','=COUNT(C14:C29)+2*B5');
values(profile,'D7',[['С учётом контактных пятен анодирования до 55 мм на концах.']]);
values(profile,'D8',[['Длина хлыста и пропил взяты из карточки поставщика.']]);
values(profile,'D9',[['Смена этих параметров требует перерасчёта раскладки скриптом.']]);
values(profile,'D10',[['https://www.rsi-llc.ru/catalog/69/1945/']]);
values(profile,'A13',[['Хлыст','Деталь','Длина, мм','Начало, мм','Конец, мм','Пропил, мм','Остаток, мм']]);head(profile,'A13:G13');
let pr=14;
for(const l of plan.bars)for(const p of l.pieces){
 values(profile,`A${pr}`,[[l.bar,p.part,p.length_mm,p.start_mm,null,l.kerf_mm,l.remainder_mm]]);
 formula(profile,`E${pr}`,`=C${pr}+D${pr}`);pr++;
}
for(const [c,w] of [['A',36],['B',27],['C',15],['D',18],['E',18],['F',17],['G',22]])width(profile,c,w,34);
profile.getRange('B4:B6').setNumberFormat('0.000');profile.getRange('B5').setNumberFormat('0');
profile.getRange('C14:G29').setNumberFormat('0.0');profile.freezePanes.freezeRows(13);

const start=7,last=start+cost.items.length-1;
const unknownStart=last+6,unknownEnd=unknownStart+cost.unpriced_hardware.length;
base(calc,unknownEnd+2,'L');
values(calc,'A2',[[`Закупка и работы ${version}`]]);
values(calc,'A3',[['Только продавцы и цеха РФ. Сборка дома. Цены в рублях на 05.11.2026.']]);
values(calc,'A4',[['Синие цены можно изменить. Жёлтые — плановые допущения, коммерческих предложений пока нет.']]);
values(calc,'A6',[['Код','Статья','Позиция','Количество','Ед.','Цена, ₽','Сумма, ₽','Основание',null,'Поставщик','Источник','Примечание']]);
head(calc,'A6:H6');head(calc,'J6:L6');
const itemRow=new Map();
for(const [i,p] of cost.items.entries()){
 const r=start+i;itemRow.set(p.id,r);
 values(calc,`A${r}`,[[p.id,p.category,p.description,p.quantity,p.unit,p.price,null,p.type,null,p.supplier,p.url,p.note]]);
 formula(calc,`G${r}`,`=IF(AND(ISNUMBER(D${r}),ISNUMBER(F${r})),ROUND(D${r}*F${r},2),"")`);
 if(p.id.startsWith('plywood-'))formula(calc,`D${r}`,`='Дерево'!B${5+[6,8,12,18].indexOf(Number(p.id.split('-')[1]))}`);
 if(p.id.startsWith('cnc-'))formula(calc,`D${r}`,`='Дерево'!E${5+[6,8,12,18].indexOf(Number(p.id.split('-')[1]))}`);
 if(p.id==='profile')formula(calc,`D${r}`,`='Профиль'!B6`);
 if(p.id==='profile-saw')formula(calc,`D${r}`,`='Профиль'!B10`);
 if(p.id==='finish')formula(calc,`D${r}`,`=SUM('Дерево'!H13:H40)`);
 calc.getRange(`F${r}`).format.font.color=blue;
 if(p.type==='Допущение')calc.getRange(`F${r}`).format.fill=yellow;
}
calc.getRange(`F${start}:G${last}`).setNumberFormat(num);
calc.getRange(`D${start}:D${last}`).setNumberFormat('0.000');
calc.getRange(`D${start}:D${last}`).format.font.color=green;
calc.getRange(`F${start}:F${last}`).conditionalFormats.add('containsBlanks',{format:{fill:'#FFE2DC',font:{color:'#A02C23',bold:true}}});
values(calc,`A${last+3}`,[["Неоценённая фурнитура: количества из модели, стоимость покрыта указанным плановой суммой."]]);
values(calc,`A${unknownStart}`,[["Код","Учтено в","Позиция","Количество","Ед.","Цена, ₽","Сумма, ₽","Состояние",null,"Комментарий"]]);
head(calc,`A${unknownStart}:H${unknownStart}`);
for(const [i,p] of cost.unpriced_hardware.entries()){
 const r=unknownStart+1+i,included=p.covered_by==='upper-cube';
 values(calc,`A${r}`,[[p.id,p.covered_by,p.description,p.quantity,'шт.',included?0:null,null,included?'В комплекте':'Нужны подбор / КП',null,p.note]]);
 if(included)formula(calc,`G${r}`,`=D${r}*F${r}`);
}
for(const [c,w] of [['A',24],['B',19],['C',67],['D',16],['E',10],['F',16],['G',18],['H',25],['I',3],['J',48],['K',78],['L',110]])width(calc,c,w,unknownEnd+2);
calc.getRange(`C7:C${unknownEnd}`).format.wrapText=true;
calc.getRange(`A7:H${unknownEnd}`).format.rowHeight=37;
calc.getRange(`D7:G${unknownEnd}`).format.horizontalAlignment='right';
calc.getRange(`H7:H${unknownEnd}`).format.horizontalAlignment='center';
calc.getRange(`K7:L${last}`).format.wrapText=true;
for(const [i,p] of cost.items.entries()){
  const lines=Math.max(Math.ceil(p.url.length/86),Math.ceil(p.note.length/113));
  if(lines>2)calc.getRange(`A${start+i}:L${start+i}`).format.rowHeight=lines*17;
}
calc.freezePanes.freezeRows(6);calc.freezePanes.freezeColumns(3);

base(summary,31,'E');summary.tabColor=header;
values(summary,'A2',[[`Cambusa ${version}. Бюджет готовых деталей`]]);
values(summary,'A3',[['05.11.2026, рубли. Фанера ФК 1/2 Ш2, тёмная тонировка и матовый лак.']]);
values(summary,'A5',[['Статья','Товары','По тарифам','Допущения','Всего, ₽']]);head(summary,'A5:E5');
const categories=Object.keys(cost.category_totals);
for(const [i,cat] of categories.entries()){
 const r=6+i;values(summary,`A${r}`,[[cat]]);
 for(const [j,type] of ['Цена товара','Тариф','Допущение'].entries())
  formula(summary,`${String.fromCharCode(66+j)}${r}`,`=SUMIFS('Расчёт'!$G$${start}:$G$${last},'Расчёт'!$B$${start}:$B$${last},$A${r},'Расчёт'!$H$${start}:$H$${last},${JSON.stringify(type)})`);
 formula(summary,`E${r}`,`=SUM(B${r}:D${r})`);
}
values(summary,'A14',[['До запаса на изменения']]);
for(const c of ['B','C','D','E'])formula(summary,`${c}14`,`=SUM(${c}6:${c}12)`);
values(summary,'A16',[['Запас на изменения',cost.contingency_rate]]);summary.getRange('B16').setNumberFormat('0%');
summary.getRange('B16').format.fill=yellow;summary.getRange('B16').format.font.color=blue;
formula(summary,'E16','=ROUND(E14*B16,2)');
values(summary,'A18',[['Плановый бюджет']]);
formula(summary,'E18',`=IF(OR(COUNT('Расчёт'!D${start}:D${last})<${cost.items.length},COUNT('Расчёт'!F${start}:F${last})<${cost.items.length}),"Нужны цены / объёмы",SUM(E14,E16))`);
summary.getRange('A18:E18').format.fill='#E5EBEC';summary.getRange('A18:E18').format.font.bold=true;
summary.getRange('E18').conditionalFormats.addCustom('ISTEXT(E18)',{fill:'#FFE2DC',font:{color:'#A02C23',bold:true}});
money(summary,'B6:E14');money(summary,'E16');money(summary,'E18');
values(summary,'A21',[
 ['Товары: цены российских продавцов; оплачиваются целые листы и хлысты.'],
 ['По тарифам: расчёт объёмов резки и покрытия; это не согласованная цена заказа.'],
 ['Допущения: 24 000 ₽ на неоценённые работы, узлы, крепёж, подбор цвета и доставку.'],
 ['Фанера: 5 листов, включая лист 6 мм для вставок трёх правых фасадов.'],
 ['Профиль: 14,483 м деталей, покупка 18,24 м (6 × 3040 мм), 28 платных резов.'],
 ['Отделка: обе стороны и наружные торцы, около 10 м²; метод тарификации уточнить.'],
 ['Ящики и аксессуары пегборда в этот бюджет не включены.'],
 ['Это планирование закупки. Заказные механизмы и крепления ещё не готовы к заказу.'],
 [version==='v30'?'Геометрия шкафа и его сохранённая версия v30 не изменены.':'v31: пластины под оси удалены; 6 муфт в допущении на крепёж. Заготовки прежних размеров.']
]);
for(const [c,w] of [['A',49],['B',17],['C',18],['D',18],['E',22]])width(summary,c,w,31);
summary.getRange('A14:E14').format.borders={bottom:{style:'thin',color:'#9BA4AC'}};
summary.getRange('A18:E18').format.rowHeight=32;
summary.getRange('A21:E29').format.rowHeight=25;
summary.getRange('A3:E3').format.font={name:'Arial',size:11,italic:true,color:'#58606A'};

// Validate the input-driven result, including a valid zero and a missing rate.
const profilePrice=calc.getRange(`F${itemRow.get('profile')}`),oldPrice=profilePrice.values[0][0];
const initial=Number(summary.getRange('E18').values[0][0]);
assert.ok(Math.abs(initial-cost.planning_budget_rub)<.02,[initial,cost.planning_budget_rub]);
profilePrice.values=[[oldPrice+1]];
const edited=Number(summary.getRange('E18').values[0][0]);
assert.ok(Math.abs(edited-initial-plan.profile_purchase_m*1.1)<.03);
profilePrice.values=[[null]];assert.equal(summary.getRange('E18').values[0][0],'Нужны цены / объёмы');
profilePrice.values=[[0]];assert.equal(typeof summary.getRange('E18').values[0][0],'number');
profilePrice.values=[[oldPrice]];
wb.recalculate();
assert.ok(Math.abs(Number(summary.getRange('E18').values[0][0])-cost.planning_budget_rub)<.02);
for(const [i,p] of cost.items.entries())assert.ok(Math.abs(Number(calc.getRange(`G${start+i}`).values[0][0])-p.amount_rub)<.02,p.id);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:40},summary:'Formula errors'});
await fs.writeFile(path.join(out,'workbook-checks.json'),JSON.stringify({initial_budget:initial,edited_profile_budget:edited,missing_rate_guard:true,zero_rate_allowed:true,independent_json_reconciliation:true,error_scan:errors.ndjson},null,2));
console.log((await wb.inspect({kind:'table',range:'Смета!A5:E18',include:'values,formulas',tableMaxRows:14,tableMaxCols:5,maxChars:3500})).ndjson);
for(const [sheetName,range,name] of [
 ['Смета','A1:E30','budget'],['Расчёт','A1:H20','purchase'],['Расчёт',`A21:H${last}`,'purchase-rest'],
 ['Расчёт',`A${unknownStart}:H${unknownEnd}`,'unpriced'],
 ['Дерево','A1:H25','wood'],['Дерево','A26:H40','wood-rest'],['Профиль','A1:G29','profile']]){
 const img=await wb.render({sheetName,range,scale:1.3,format:'png'});
 await fs.writeFile(path.join(out,`preview-${name}.png`),new Uint8Array(await img.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(path.join(out,`estimate-${version}.xlsx`));
console.log('Workbook exported, all line amounts and price-change behavior verified.');
