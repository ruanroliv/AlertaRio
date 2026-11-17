/* Dependency-free SVG chart. Measured timestamps, never fixed labels or invented zero samples. */
(function(root){
  'use strict';
  const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function chart(samples,key,unit,color='#198d79'){
    const points=samples.filter(s=>Number.isFinite(s[key])&&Number.isFinite(Date.parse(s.measured_at)))
      .slice().sort((a,b)=>Date.parse(a.measured_at)-Date.parse(b.measured_at));
    if(!points.length)return '<div class="empty" role="status">Sem amostras neste recorte. Nenhuma leitura foi substituída por zero.</div>';
    const times=points.map(s=>Date.parse(s.measured_at)),first=times[0],span=times.at(-1)-first;
    const max=key==='soil'?100:Math.max(200,...points.map(s=>s[key]));
    const coordinates=points.map((s,i)=>({x:span?45+(times[i]-first)/span*455:272.5,y:140-s[key]/max*112,s}));
    const line=coordinates.map(p=>`${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ');
    const ticks=[0,Math.floor((points.length-1)/2),points.length-1].filter((v,i,a)=>a.indexOf(v)===i);
    return `<svg class="chart" viewBox="0 0 540 180" role="img" aria-label="${escape(key==='soil'?'Umidade':'Nível de água')}: ${points.length} amostras com horário de medição"><path d="M45 25V140H505" fill="none" stroke="#cddbd8"/>${[0,.5,1].map(f=>`<path d="M45 ${140-f*112}H505" stroke="#e5eeeb" stroke-dasharray="3 4"/><text x="3" y="${144-f*112}">${Math.round(f*max)} ${escape(unit)}</text>`).join('')}<polyline points="${line}" fill="none" stroke="${color}" stroke-width="2.5"/>${coordinates.map(p=>`<circle cx="${p.x.toFixed(2)}" cy="${p.y.toFixed(2)}" r="4" fill="${color}"><title>${escape(new Date(p.s.measured_at).toLocaleString('pt-BR'))}: ${p.s[key]} ${escape(unit)}</title></circle>`).join('')}${ticks.map(i=>`<text x="${coordinates[i].x.toFixed(2)}" y="162" text-anchor="middle">${escape(new Date(points[i].measured_at).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit',second:'2-digit'}))}</text>`).join('')}<text x="270" y="177" text-anchor="middle">Horário de medição · fuso do navegador</text></svg>`;
  }
  root.AlertaCharts={chart,escape};
  if(typeof module!=='undefined')module.exports=root.AlertaCharts;
})(typeof window!=='undefined'?window:globalThis);
