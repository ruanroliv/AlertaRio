const test=require('node:test');
const assert=require('node:assert/strict');
const {chart,escape}=require('../frontend/charts.js');
test('ausência de dados não produz uma curva de zeros',()=>{
 const html=chart([],'water','cm');assert.match(html,/Sem amostras/);assert.doesNotMatch(html,/<polyline/);
});
test('timestamps com intervalos diferentes produzem espaçamento proporcional',()=>{
 const base=Date.parse('2026-01-01T12:34:50Z');
 const samples=[0,1000,10000].map((dt,i)=>({measured_at:new Date(base+dt).toISOString(),water:10+i*10}));
 const html=chart(samples,'water','cm');
 const x=[...html.matchAll(/<circle cx="([\d.]+)"/g)].map(m=>Number(m[1]));
 assert.equal(x.length,3);assert.ok(Math.abs((x[1]-x[0])/(x[2]-x[0])-.1)<.001);
 assert.doesNotMatch(html,/08:00|09:00|10:00|11:00/);
});
test('horários e valores inválidos não viram dados válidos',()=>{
 assert.match(chart([{measured_at:'invalid',soil:50}],'soil','%'),/Sem amostras/);
 assert.match(chart([{measured_at:new Date().toISOString(),soil:null}],'soil','%'),/Sem amostras/);
});
test('texto interpolado em SVG é escapado',()=>{
 const html=chart([{measured_at:'2026-01-01T00:00:00Z',water:2}],'water','<script>');
 assert.doesNotMatch(html,/<script>/);assert.equal(escape('<img>'),'&lt;img&gt;');
});
