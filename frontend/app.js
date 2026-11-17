'use strict';
const LIVE=window.ALERTARIO_CONFIG?.mode==='backend';
const $=selector=>document.querySelector(selector);
const esc=AlertaCharts.escape;
const page=document.body.dataset.page;
const points=[['AR-001','Rio das Pedras'],['AR-002','Rocinha'],['AR-003','Complexo do Alemão'],['AR-004','Tijuca'],['AR-005','Santa Teresa']];
const color=label=>({'Alto':'red','Atenção':'amber','Normal':'green'}[label]||'amber');
const tag=label=>`<span class="badge ${color(label)}">${esc(label||'Sem dados')}</span>`;
const num=(v,unit='')=>v==null?'—':`${Number(v).toLocaleString('pt-BR',{maximumFractionDigits:1})}${unit}`;
const time=value=>value?new Date(value).toLocaleString('pt-BR'):'Sem medição';
const options=selected=>points.map(([id,name])=>`<option value="${id}" ${selected===id?'selected':''}>${name}</option>`).join('');
const localDate=date=>new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);
let ui={community:'',origin:'all',start:localDate(new Date(Date.now()-86400000)),end:'',selected:'AR-001'};
try{ui={...ui,...JSON.parse(sessionStorage.getItem('ar-ui-v2')||'{}')}}catch{}
let session=null,csrf='',state={sensors:[],alerts:[],occurrences:[]},metrics=null,busy=false,timer=null,draft=false,integrationText='';
function saveUI(){try{sessionStorage.setItem('ar-ui-v2',JSON.stringify(ui))}catch{}}
function toast(text){$('#toast').textContent=text;$('#toast').style.display='block';clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').style.display='none',5000)}
async function api(path,method='GET',body){
 const response=await fetch(path,{method,credentials:'same-origin',headers:{...(body?{'Content-Type':'application/json'}:{}),'X-CSRF-Token':csrf},...(body?{body:JSON.stringify(body)}:{})});
 let result;try{result=await response.json()}catch{throw new Error('Resposta inválida da API')}
 if(!response.ok){if(response.status===401&&page!=='login')location.replace('index.html');throw new Error(typeof result.detail==='string'?result.detail:'Entrada inválida')}
 return result;
}
function query(){const q=new URLSearchParams();if(ui.community)q.set('community',ui.community);q.set('origin',ui.origin);
 if(ui.start)q.set('start',new Date(ui.start).toISOString());if(ui.end)q.set('end',new Date(ui.end).toISOString());return q.toString()}
function filters(){return `<section class="card filters"><form id="filters"><label>Comunidade<select name="community"><option value="">Todas</option>${options(ui.community)}</select></label><label>De<input type="datetime-local" name="start" value="${esc(ui.start)}"></label><label>Até<input type="datetime-local" name="end" value="${esc(ui.end)}"></label><label>Origem<select name="origin"><option value="all">Todas</option><option value="simulated" ${ui.origin==='simulated'?'selected':''}>Simulada</option><option value="device" ${ui.origin==='device'?'selected':''}>Ponte física</option></select></label><button>Aplicar filtros</button></form><p class="muted">O recorte controla os indicadores, os dois gráficos e o CSV. Os alertas recebidos são registros operacionais da comunidade.</p></section>`}
function cards(){return `<div class="stats">${[
 ['Nível máximo no recorte',num(metrics.max_water_cm,' cm'),'MAX das amostras filtradas'],
 ['Umidade média das amostras',num(metrics.avg_soil_pct,'%'),'AVG no mesmo recorte'],
 ['Pontos com último risco alto',metrics.high_risk_points,'Última classificação de cada ponto no recorte'],
 ['Maior variação média',num(metrics.max_rise_cm_min,' cm/min'),'Variação entre primeira e última amostra de cada ponto']
 ].map(([title,value,note])=>`<article class="stat"><div class="stat-top">${title}</div><strong>${value}</strong><small>${note}</small></article>`).join('')}</div><p class="muted">${metrics.readings_count} amostras · ${metrics.points_with_data} pontos com dados · ${metrics.simulated_count} amostras simuladas. Dados do recorte; não é probabilidade de desastre.</p>`}
function heading(label,title,description){return `<div class="heading"><div><span class="eyebrow">${label}</span><h1>${title}</h1><p>${description}</p></div><button id="refresh" class="secondary">↻ Consultar banco</button></div>`}
function sensor(){return state.sensors.find(s=>s.id===ui.selected)||state.sensors[0]}
function plots(){const s=sensor(),series=metrics.series.find(item=>item.sensor_id===s?.id),samples=series?.samples||[];
 return `<div class="bottom-grid"><section class="card"><div class="card-head"><div><h2>Água · ${esc(s?.name||'Ponto')}</h2><p>${samples.length} amostras do recorte · cm</p></div></div><div class="card-body">${AlertaCharts.chart(samples,'water','cm')}</div></section><section class="card"><div class="card-head"><div><h2>Umidade · ${esc(s?.name||'Ponto')}</h2><p>Mesmo período e origem · %</p></div></div><div class="card-body">${AlertaCharts.chart(samples,'soil','%','#c28a21')}</div></section></div>`;
}
function selectPoint(){return `<div class="sensor-list">${state.sensors.map(s=>`<button data-point="${s.id}" class="${ui.selected===s.id?'selected':''}">${esc(s.name)}</button>`).join('')}</div>`}
function latestNotice(){const s=sensor();return `<div class="notice">${s?.has_reading?`Última medição: ${time(s.measured_at)}. Recebida: ${time(s.received_at)}. Origem: ${s.simulated?'simulada':'ponte física'}. ${s.stale?'Desatualizada há mais de cinco minutos.':''}`:'O ponto ainda não recebeu uma leitura.'}</div>`}
function mapView(){const filtered=new Set(metrics.series.map(s=>s.sensor_id));return `<section class="card"><div class="card-head"><h2>Pontos no recorte</h2><span class="badge">MAPA ESQUEMÁTICO</span></div><div class="map"><svg viewBox="0 0 700 400" role="img" aria-label="Mapa ilustrativo das comunidades"><rect width="700" height="400" fill="#e5eee6"/><path d="M0 300Q190 220 350 315T700 300V400H0" fill="#bedce2"/>${Array.from({length:10},(_,i)=>`<path d="M${i*75} 0L${i*75+160} 360" stroke="white" stroke-width="7"/><path d="M0 ${i*45}L700 ${i*45-70}" stroke="white" stroke-width="4"/>`).join('')}</svg>${state.sensors.filter(s=>filtered.has(s.id)).map(s=>`<button data-point="${s.id}" class="pin ${s.risk.cls}" style="left:${s.x}%;top:${s.y}%" aria-label="${esc(s.name)}: ${esc(s.risk.label)}"></button>`).join('')}<div class="map-popup"><b>${esc(sensor()?.name||'Ponto')}</b> ${tag(sensor()?.risk.label)}<p>Medição: ${time(sensor()?.measured_at)}</p><a href="sensores.html" class="text-link">Abrir leituras →</a></div></div><div class="map-legend">Posições ilustrativas. As cores indicam o estado atual, com aviso de leitura desatualizada.</div></section>`}
function overview(){return heading('MONITORAMENTO COMUNITÁRIO','Dados para acompanhar. Informação para agir.','Atualização automática a cada 5 segundos; sensores e classes experimentais.')+filters()+cards()+mapView()+selectPoint()+latestNotice()+plots()}
function sensorPage(){const s=sensor();return heading('SENSORES E ANÁLISE','Da leitura à informação.','As mesmas amostras alimentam indicadores, gráficos e análises persistidas.')+filters()+cards()+selectPoint()+latestNotice()+plots()+`<div class="bottom-grid"><section class="card"><div class="card-head"><h2>Simulador de leitura</h2><span class="badge">EXERCÍCIO</span></div><div class="card-body">${session.profile==='manager'?`<form id="simulation">${[['water','Água',s.water??55,200,'cm'],['soil','Solo',s.soil??35,100,'%'],['rain','Chuva informada',s.rain??0,100,'mm']].map(([id,title,value,max,unit])=>`<label class="field">${title}<input type="range" name="${id}" min="0" max="${max}" value="${value}"><output>${num(value,unit)}</output></label>`).join('')}<button>Salvar leitura simulada</button><button type="reset" class="secondary">Descartar alterações</button></form>`:'<p>A simulação é exclusiva do gestor. Leituras e alertas podem ser acompanhados por moradores.</p>'}<p class="muted">Chuva é uma entrada separada; não há pluviômetro no circuito. O potenciômetro representa umidade.</p></div></section><section class="card"><div class="card-head"><h2>Análise única do ponto</h2>${tag(s.risk.label)}</div><div class="card-body"><p>${esc(s.last_risk?.explanation||'Aguardando uma leitura.')}</p><p class="muted">Análise ${s.last_risk?.analysis_id??'legada/sem ID'} · ${s.last_risk?.forecast_next_3h_mm==null?'sem previsão na análise':num(s.last_risk.forecast_next_3h_mm,' mm previstos / 3h')}.</p><div class="actions"><button id="weather" class="secondary">Consultar previsão</button>${session.profile==='manager'?'<button id="reanalyze">Atualizar análise com previsão</button><button id="explain" class="secondary">Explicar com Ollama</button>':''}</div><p id="integration-result" role="status">${esc(integrationText)}</p><p class="muted">kNN e limites didáticos com dados sintéticos. Não é aviso oficial. Previsão: Open-Meteo.</p></div></section></div><button id="export" class="secondary" style="margin-top:18px">↓ CSV do recorte</button>`}
function inbox(){let alerts=state.alerts;if(session.profile==='manager')alerts=alerts.filter(a=>a.sensor_id===ui.selected);
 return `<section class="card"><div class="card-head"><h2>Caixa de avisos da comunidade</h2><span class="badge">${alerts.filter(a=>!a.acknowledged).length} NÃO CONFIRMADOS</span></div>${alerts.length?alerts.map(a=>`<article class="alert-item"><div style="width:100%"><h3>Aviso #${a.id} · ${esc(a.community||points.find(p=>p[0]===a.sensor_id)?.[1]||a.sensor_id)}</h3>${tag(a.risk)}<p>${esc(a.text)}</p><p class="muted">${time(a.created_at)} · ${a.simulated?'Leitura simulada':'Ponte física'} · análise ${a.analysis_id??'legada'}</p>${a.acknowledged?'<span class="badge">LEITURA CONFIRMADA</span>':`<button data-ack="${a.id}">Confirmar leitura do aviso #${a.id}</button>`}</div></article>`).join(''):'<p class="empty">Nenhum aviso persistido para esta comunidade. O aviso aparecerá automaticamente quando chegar uma nova classificação.</p>'}</section>`}
function callForm(){return `<section class="card" style="margin-top:22px"><div class="card-head"><h2>Relatar uma ocorrência</h2></div><div class="card-body"><form id="call-form"><label class="field">Comunidade<select name="community">${options(session.profile==='manager'?ui.selected:session.community_id)}</select></label><label class="field">Relato<textarea name="text" minlength="8" maxlength="500" required placeholder="Descreva o que observou"></textarea></label><button>Registrar ocorrência</button><button type="reset" class="secondary">Descartar alterações</button></form></div></section>`}
function residentPage(){return heading('PAINEL DO MORADOR','Os avisos chegam até você.','Nenhum botão de geração é necessário. O painel consulta os alertas salvos a cada 5 segundos.')+(session.profile==='manager'?selectPoint():'')+`<p class="notice">${LIVE?'Avisos internos persistidos. A confirmação registra o mesmo identificador mostrado no cartão.':'Demonstração estática. Alertas e confirmações ficam apenas na sessão do navegador.'} Não há envio de SMS por esta tela.</p>`+inbox()+callForm()}
function calls(){return `<section class="card"><div class="card-head"><h2>Ocorrências operacionais</h2><span class="muted">Lista atual, independente do recorte histórico</span></div><div class="table-wrap"><table><thead><tr><th>ID</th><th>COMUNIDADE</th><th>RELATO</th><th>STATUS</th><th>AÇÃO</th></tr></thead><tbody>${state.occurrences.length?state.occurrences.map(o=>`<tr><td>${o.id}</td><td>${esc(o.place)}</td><td>${esc(o.text)}</td><td>${esc(o.status)}</td><td>${o.status==='Concluído'?'Concluído':`<button data-call="${o.id}" data-status="${o.status==='Aberto'?'Em análise':'Concluído'}">${o.status==='Aberto'?'Analisar':'Concluir'}</button>`}</td></tr>`).join(''):'<tr><td colspan="5">Nenhuma ocorrência registrada.</td></tr>'}</tbody></table></div></section>`}
function managerPage(){return heading('CENTRAL DE GESTÃO','Um recorte para decidir melhor.','Filtros compartilhados entre indicadores, séries e CSV.')+filters()+cards()+selectPoint()+plots()+`<button id="export" class="secondary" style="margin:18px 0">↓ CSV do recorte</button>`+calls()+callForm()+`<section class="card" style="margin-top:22px"><div class="card-head"><h2>Monitoramento do serviço</h2><button id="monitor" class="secondary">Consultar saúde e métricas</button></div><div class="card-body"><p id="monitor-result">Uptime, requisições, erros e registros persistidos. Contadores desde a inicialização do processo.</p></div></section>`}
function render(){saveUI();if(!$('#page-content'))return;
 $('#page-content').innerHTML=`<div class="notice"><b>Ambiente acadêmico.</b> A base inicial contém dados fictícios de demonstração, independentes do Arduino. Filtre a origem para comparar simulação e dispositivo. Os registros não representam condições reais das comunidades.</div>`+({mapa:overview,sensores:sensorPage,morador:residentPage,gestao:managerPage})[page]()+`<footer class="footer"><span>AlertaRio · MVP acadêmico</span><span id="updated">Consulta: ${new Date().toLocaleTimeString('pt-BR')} · atualização automática 5s</span></footer>`;
 document.querySelector('.demo').textContent=LIVE?'BACKEND CONECTADO':'DEMONSTRAÇÃO ESTÁTICA';
 document.querySelectorAll('.avatar').forEach(a=>a.textContent=session.profile==='manager'?'DC':'MO');
 $('.side-user b').textContent=session.profile==='manager'?'Gestor':'Morador';
 $('.side-user p').textContent=LIVE?'Perfil verificado no servidor':'Perfil demonstrativo';
 document.querySelectorAll('a[href="gestao.html"]').forEach(a=>a.hidden=session.profile!=='manager');
 $('.connection').innerHTML=LIVE?'<span class="dot"></span>API e banco conectados':'Protótipo estático · sem API';
 bind();
}
async function refresh(){if(LIVE){state=await api('/api/state');metrics=await api('/api/analytics?'+query())}else{state=demoLoad();metrics=demoAnalytics()}render()}
async function action(fn){if(busy)return;busy=true;try{await fn()}catch(error){toast(error.message)}finally{busy=false}}
function bind(){
 const on=(id,event,fn)=>{const el=$(id);if(el)el['on'+event]=fn};
 on('#refresh','click',()=>{if(draft){toast('Salve ou descarte as alterações do formulário antes de consultar.');return}action(refresh)});
 document.querySelectorAll('#simulation,#call-form').forEach(form=>{form.oninput=()=>{draft=true;const label=$('#updated');if(label)label.textContent='Atualização pausada durante a edição.'};form.onreset=()=>{draft=false}});
 on('#logout','click',()=>action(async()=>{if(LIVE)await api('/api/auth/logout','POST',{});else sessionStorage.removeItem('ar-demo-session');location.href='index.html'}));
 on('#filters','submit',event=>{event.preventDefault();if(draft){toast('Salve ou descarte o rascunho antes de aplicar filtros.');return}const f=new FormData(event.target);if(f.get('start')&&f.get('end')&&f.get('start')>f.get('end')){toast('O início deve ser anterior ao fim.');return}
 ui={...ui,community:f.get('community'),origin:f.get('origin'),start:f.get('start'),end:f.get('end')};if(ui.community)ui.selected=ui.community;saveUI();action(refresh)});
 document.querySelectorAll('[data-point]').forEach(el=>el.onclick=()=>{ui.selected=el.dataset.point;ui.community=ui.selected;integrationText='';draft=false;saveUI();action(refresh)});
 document.querySelectorAll('input[type=range]').forEach(el=>el.oninput=()=>el.nextElementSibling.textContent=num(el.value,el.name==='water'?' cm':el.name==='soil'?'%':' mm'));
 on('#simulation','submit',event=>{event.preventDefault();const f=new FormData(event.target);action(async()=>{
  const body={sensor_id:ui.selected,water_level_cm:Number(f.get('water')),soil_moisture_pct:Number(f.get('soil')),rainfall_mm:Number(f.get('rain')),measured_at:new Date().toISOString(),simulated:true};
  if(LIVE)await api('/api/readings/simulate','POST',body);else demoAdd(body);
  draft=false;await refresh();toast('Leitura e análise salvas; alertas de mudança gerados automaticamente.');})});
 document.querySelectorAll('[data-ack]').forEach(el=>el.onclick=()=>action(async()=>{const id=Number(el.dataset.ack);if(LIVE)await api('/api/alerts/'+id+'/ack','POST',{});else{state.alerts.find(a=>a.id===id).acknowledged=true;demoSave()}await refresh();toast('Leitura do aviso #'+id+' confirmada.')}));
 document.querySelectorAll('[data-call]').forEach(el=>el.onclick=()=>action(async()=>{if(LIVE)await api('/api/calls/'+el.dataset.call,'PATCH',{status:el.dataset.status});else{state.occurrences.find(o=>o.id===Number(el.dataset.call)).status=el.dataset.status;demoSave()}await refresh()}));
 on('#call-form','submit',event=>{event.preventDefault();const f=new FormData(event.target);action(async()=>{const body={community_id:session.profile==='resident'?session.community_id:f.get('community'),text:f.get('text')};if(LIVE)await api('/api/calls','POST',body);else{state.occurrences.unshift({id:Date.now(),place:points.find(p=>p[0]===body.community_id)[1],text:body.text,status:'Aberto'});demoSave()}draft=false;await refresh();toast('Ocorrência registrada.')})});
 if(session.profile==='resident'&&$('#call-form select'))$('#call-form select').disabled=true;
 on('#monitor','click',()=>action(async()=>{if(!LIVE){toast('Monitoramento disponível no backend.');return}const m=await api('/api/monitoring');$('#monitor-result').textContent=`Banco ${m.database} · ${m.requests_total} requisições · ${m.server_errors_total} erros de servidor · uptime ${m.uptime_seconds}s · mediana ${m.median_request_ms}ms · ${m.records.readings} leituras e ${m.records.alerts} alertas.`}));
 on('#export','click',()=>{if(LIVE)location.href='/api/readings.csv?'+query();else toast('Execute o backend Python para exportar o CSV autenticado.')});
 for(const [id,path,method] of [['#weather','/api/weather/','GET'],['#reanalyze','/api/analysis/','POST'],['#explain','/api/ai/','POST']])on(id,'click',()=>action(async()=>{
  if(!LIVE){toast('Integração disponível no backend Python.');return}
  const result=await api(path+ui.selected+(id==='#reanalyze'?'/refresh':id==='#explain'?'/explain':''),method,method==='POST'?{}:undefined);
  if(id==='#reanalyze')await refresh();
  integrationText=result.text||(result.provider==='Open-Meteo'?`Previsão: ${num(result.next_3h_mm,' mm / próximas 3h')}. Fonte Open-Meteo, consulta ${time(result.fetched_at)}. A consulta isolada não altera análise.`:`Análise #${result.analysis_id}: ${result.label}. Mapa e alerta usam esta mesma análise.`);
  $('#integration-result').textContent=integrationText;
 }));
}
function demoLoad(){try{const saved=JSON.parse(sessionStorage.getItem('ar-demo-data-v2'));if(saved)return saved}catch{}
 const stamp=new Date().toISOString();const initial={sensors:points.map(([id,name],i)=>({id,name,x:[61,39,65,37,50][i],y:[62,70,27,37,47][i],has_reading:false,water:null,soil:null,rain:null,stale:true,measured_at:null,simulated:true,risk:{label:'Sem dados',cls:'amber'}})),alerts:[],occurrences:[]};
 const s=initial.sensors[0];Object.assign(s,{has_reading:true,stale:false,water:180,soil:90,rain:0,measured_at:stamp,received_at:stamp,risk:{label:'Alto',cls:'red'},last_risk:{label:'Alto',analysis_id:3,explanation:'Exemplo fictício da apresentação estática.',forecast_next_3h_mm:null},samples:[55,110,180].map((water,i)=>({id:i+1,measured_at:new Date(Date.now()-(2-i)*60000).toISOString(),water,soil:[35,70,90][i],simulated:true}))});
 initial.alerts.push({id:3,sensor_id:s.id,community:s.name,risk:'Alto',text:'Exemplo de aviso da demonstração estática. Nenhum envio realizado.',created_at:stamp,simulated:true,analysis_id:3,acknowledged:false});
 sessionStorage.setItem('ar-demo-data-v2',JSON.stringify(initial));return initial;}

function demoSave(){sessionStorage.setItem('ar-demo-data-v2',JSON.stringify(state))}
function demoAdd(body){const s=state.sensors.find(s=>s.id===body.sensor_id),old=s.last_risk?.label;
 const label=body.water_level_cm>=160||body.soil_moisture_pct>=85?'Alto':body.water_level_cm>=100||body.soil_moisture_pct>=65?'Atenção':'Normal';
 Object.assign(s,{water:body.water_level_cm,soil:body.soil_moisture_pct,rain:body.rainfall_mm,has_reading:true,stale:false,simulated:true,measured_at:body.measured_at,received_at:body.measured_at,risk:{label,cls:color(label)},last_risk:{label,explanation:'Regra simplificada do protótipo estático; execute o backend para o kNN.',analysis_id:Date.now(),forecast_next_3h_mm:null}});
 s.samples=s.samples||[];s.samples.push({id:Date.now(),measured_at:body.measured_at,water:s.water,soil:s.soil,simulated:true});
 if(label!==old)state.alerts.unshift({id:Date.now(),sensor_id:s.id,community:s.name,risk:label,text:'Exercício: mudança de classificação para '+label,created_at:body.measured_at,simulated:true,analysis_id:s.last_risk.analysis_id,acknowledged:false});demoSave();}
function demoAnalytics(){const from=ui.start?new Date(ui.start).getTime():-Infinity,to=ui.end?new Date(ui.end).getTime():Infinity;
 const series=state.sensors.filter(s=>!ui.community||s.id===ui.community).map(s=>({sensor_id:s.id,name:s.name,last_risk:s.risk.label,samples:(s.samples||[]).filter(r=>Date.parse(r.measured_at)>=from&&Date.parse(r.measured_at)<=to&&ui.origin!=='device')})).filter(s=>s.samples.length);
 const rows=series.flatMap(s=>s.samples);return{series,readings_count:rows.length,points_with_data:series.length,simulated_count:rows.length,high_risk_points:series.filter(s=>s.last_risk==='Alto').length,max_water_cm:rows.length?Math.max(...rows.map(r=>r.water)):null,avg_soil_pct:rows.length?rows.reduce((a,r)=>a+r.soil,0)/rows.length:null,max_rise_cm_min:null};}
async function start(){
 if(page==='login'){
  $('#show-password').onchange=event=>$('#password').type=event.target.checked?'text':'password';
  if(LIVE){$('#profile').closest('.field').hidden=true;$('#password').minLength=1;$('.login-note').textContent='Use uma conta cadastrada no backend. O servidor determina seu perfil.';$('.login-form > p').textContent='Autenticação no backend Python.';document.querySelector('label[for=password]').textContent='Senha';}
  $('#login-form button[type=submit]').textContent=LIVE?'Entrar →':'Entrar na demonstração →';
  $('#login-form').onsubmit=event=>{event.preventDefault();action(async()=>{try{if(LIVE)await api('/api/auth/login','POST',{email:$('#email').value,password:$('#password').value});else sessionStorage.setItem('ar-demo-session',JSON.stringify({profile:$('#profile').value,community_id:'AR-001'}));location.href='mapa.html'}catch(error){$('#login-error').textContent=error.message}})};return;
 }
 try{
  if(LIVE){session=await api('/api/auth/me');csrf=session.csrf_token}else{session=JSON.parse(sessionStorage.getItem('ar-demo-session')||'null');if(!session){location.replace('index.html');return}}
  if(page==='gestao'&&session.profile!=='manager'){location.replace('morador.html');return}
  await refresh();
  async function poll(){if(!busy&&!draft&&!document.hidden&&!document.activeElement?.closest('form')){busy=true;try{await refresh()}catch(error){const label=$('#updated');if(label)label.textContent='Sem atualização: '+error.message}finally{busy=false}}timer=setTimeout(poll,5000)}
  timer=setTimeout(poll,5000);window.addEventListener('pagehide',()=>clearTimeout(timer));
 }catch(error){if($('#page-content'))$('#page-content').textContent='Não foi possível carregar: '+error.message;else toast(error.message)}
}
start();
