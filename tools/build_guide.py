"""Build the delivery PDF from documented implementation and recorded evidence."""
from pathlib import Path
import json,re
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,PageBreak,Flowable
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.pagesizes import A4
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output/Guia_Entrega_AlertaRio_v2.pdf';OUT.parent.mkdir(exist_ok=True)
flow=json.loads((ROOT/'docs/evidence/flow.json').read_text(encoding='utf-8'))
navy=colors.HexColor('#163745');teal=colors.HexColor('#087f72');pale=colors.HexColor('#eef6f3');line=colors.HexColor('#dce6e3')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='T',fontName='Helvetica-Bold',fontSize=25,leading=30,textColor=navy,spaceAfter=13))
styles.add(ParagraphStyle(name='H',fontName='Helvetica-Bold',fontSize=16,leading=20,textColor=navy,spaceAfter=11))
styles.add(ParagraphStyle(name='Sub2',fontName='Helvetica-Bold',fontSize=11,leading=14,textColor=teal,spaceBefore=10,spaceAfter=7))
styles.add(ParagraphStyle(name='B2',fontName='Helvetica',fontSize=9.4,leading=13.5,textColor=navy,spaceAfter=8))
styles.add(ParagraphStyle(name='Small2',fontName='Helvetica',fontSize=8,leading=11,textColor=colors.HexColor('#5d7079'),spaceAfter=6))
styles.add(ParagraphStyle(name='Cell2',fontName='Helvetica',fontSize=8.5,leading=11.5,textColor=navy))
styles.add(ParagraphStyle(name='Head2',fontName='Helvetica-Bold',fontSize=8.5,leading=11,textColor=colors.white))
styles.add(ParagraphStyle(name='Mono2',fontName='Courier',fontSize=7.5,leading=11,textColor=navy,spaceAfter=8))
story=[]
def para(t,style='B2'):return Paragraph(t,styles[style])
def add(t,style='B2'):story.append(para(t,style))
def table(headers,rows,widths):
 t=Table([[para(escape(x),'Head2') for x in headers]]+[[para(x,'Cell2') for x in row] for row in rows],colWidths=widths,repeatRows=1)
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),navy),('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,pale]),('LINEBELOW',(0,0),(-1,-1),.5,line),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]));story.append(t);story.append(Spacer(1,9))
def page(label,title):story.append(PageBreak());add(label.upper(),'Small2');add(title,'H')
class Diagram(Flowable):
 def __init__(self):Flowable.__init__(self);self.width=511;self.height=245
 def draw(self):
  c=self.canv
  def box(x,y,w,title,detail):
   c.setFillColor(pale);c.setStrokeColor(line);c.roundRect(x,y,w,45,5,fill=1,stroke=1);c.setFillColor(navy);c.setFont('Helvetica-Bold',8.5);c.drawCentredString(x+w/2,y+28,title);c.setFont('Helvetica',7.2);c.drawCentredString(x+w/2,y+12,detail)
  def arrow(x,y,x2,y2):
   import math
   c.setStrokeColor(teal);c.line(x,y,x2,y2);a=math.atan2(y2-y,x2-x)
   for d in (-.45,.45):c.line(x2,y2,x2-5*math.cos(a+d),y2-5*math.sin(a+d))
  box(4,190,145,'Wokwi / JSONL','Agua + umidade mock')
  box(183,190,145,'Ponte + API','Chave, tempo, idempotencia')
  box(362,190,145,'Bronze','Original + rejeitados')
  arrow(149,212,183,212);arrow(328,212,362,212)
  box(183,108,145,'SQLite / Silver','Leitura UTC + analise unica')
  arrow(255,190,255,153)
  box(4,108,145,'Previsao opcional','Cache / reanalise autenticada');arrow(149,130,183,130)
  box(362,108,145,'Gold / Analytics','Filtros e funcoes');arrow(328,130,362,130)
  box(183,20,145,'Morador','Aviso persistido + ACK do ID');arrow(255,108,255,65)
  box(362,20,145,'Mapa / Gestao','Dois graficos + indicadores');arrow(435,108,435,65)
  box(4,20,145,'Engenharia','Git, testes e monitoramento');arrow(149,42,183,42)
add('ALERTARIO V2 / GUIA DE ENTREGA','Sub2')
add('Do sensor simulado<br/>ao aviso do cidadão.','T')
add('Implementação corrigida, arquitetura e evidências - 17/11/2026','Small2')
add('<b>Problema:</b> comunidades precisam entender sinais de elevação da água e umidade, sem interpretar cada leitura manualmente. O MVP transforma observações simuladas em classes e avisos internos rastreáveis.')
add('<b>Escopo:</b> cinco páginas em HTML/CSS/JS, Python/FastAPI, SQLite, circuito Wokwi por código, ingestão por replay, análise kNN experimental e dashboard filtrável. O modelo e os limites são didáticos, sem validação para emergências reais.')
add('Arquitetura implementada','Sub2');story.append(Diagram())
add('A cópia da saída serial para JSONL é manual. Depois de receber a leitura, análise, geração de aviso e consulta pelo painel são automatizadas. O polling é de 5s em aba ativa, pausado durante edição. Não há conexão direta do Uno virtual com localhost.','Small2')
add('O que mudou da primeira versão','Sub2')
add('Código-fonte padronizado em frontend; água e umidade com horários medidos; ausência de dados sem zeros inventados; filtros nos mesmos indicadores e CSV; análise persistida com ID; caixa automática do morador e confirmação do aviso exato; Bronze/Silver/Gold e regressões testadas.')
add('Migrações aditivas preservam contas e leituras antigas. A apresentação hospedada continua estática; autenticação, banco e kNN do sistema completo exigem o servidor Python.','Small2')
page('01 / IA e automação','Uma análise, uma fonte e um aviso rastreável')
add('O motor kNN usa cinco vizinhos dos 300 exemplos sintéticos, com água/200, solo/100 e chuva/100 normalizados. Desempate prioriza a maior classe. Piso Atenção: água >=100 cm ou solo >=65%; piso Alto: água >=160 cm ou solo >=85%. Previsão >=30 mm nas próximas 3h eleva o piso uma classe. O resultado é o maior entre o voto e o piso.')
add('A cada ingestão a análise é persistida com reading_id, analysis_id, modelo, versão, fontes e data. Mudança de classe cria aviso. Atualizar análise com previsão é POST de gestor com CSRF e persiste outra análise; mapa, API e aviso passam a usar o mesmo resultado. Os índices 25/60/90 não são probabilidades.')
table(['Entrada do roteiro','Saída observada / esperada'],[
 ['AR-001: água 55 cm; solo 35%; chuva declarada 0 mm','Normal; no primeiro caso do ensaio, analysis_id=1 e alert_id=1; confirmação do mesmo alerta.'],
 ['AR-001: água 180 cm; solo 90%; chuva declarada 0 mm','Alto; aviso criado sem comando de geração na interface.'],
 ['55 cm / 35% + previsão MOCK de 40 mm','Atenção; teste de regressão verifica o mesmo ID em análise, mapa e aviso. Não é uma previsão real usada nesse teste.']
],[225,286])
add('Prompt opcional de explicação (Ollama)','Sub2')
add('“Você explica um exercício acadêmico de monitoramento. Dados e modelo são sintéticos, sem validação para emergências. Explique em português em até 100 palavras os fatores da classificação abaixo. Não invente dados, locais, horários ou probabilidades. Não emita ordem de evacuação nem recomendação operacional. Mencione que é experimental. Dados estruturados: {assessment}”','Small2')
add('A entrada é a análise persistida, não uma decisão nova do LLM. O conector exige serviço/modelo instalado e não foi executado com Ollama nesta entrega. Não é necessário para o fluxo principal.')
add('Métrica e comparação antes/depois','Sub2')
table(['Medição','Resultado do ensaio local'],[
 ['Aderência ao roteiro sintético',f"{flow['successful']}/{flow['scenarios']} entradas produziram classe, aviso e confirmação correspondentes."],
 ['Disponibilidade no backend',f"Mediana {flow['median_backend_availability_ms']} ms; P95 {flow['p95_backend_availability_ms']} ms. Não inclui rede externa ou espera do polling."],
 ['Passos para exibir aviso em página já aberta','Antes: recarregar e clicar em Simular recebimento (2 ações). Agora: caixa consulta automaticamente (0 ações). Confirmação não entra na contagem.']
],[190,321])
add('A comparação de passos é análise do fluxo, não estudo de tempo humano. 20/20 não é acurácia de previsão de desastre. O ensaio usa banco temporário e está reproduzível por tools/verify_flow.py; valores completos em docs/evidence/flow.json.','Small2')
page('02 / Big Data e visualização','Da coleta ao recorte que apoia uma decisão')
table(['Camada','Organização e processamento'],[
 ['Bronze / original','JSONL com recibo, payload autenticado, uptime, origem e status received/processed/rejected. A credencial de cabeçalho não é gravada.'],
 ['Silver / tratado','Leitura validada no SQLite e CSV materializável. UTC, faixas, origem e IDs. Rejeição de duplicidade por event_id.'],
 ['Gold / agregado','Indicadores e séries com comunidade, datas e origem; JSON materializado e mesma função usada pela API e CSV filtrado.']
],[120,391])
add('A ponte reconstrói intervalos de measured_at a partir do uptime e ancora a última amostra no começo do replay. received_at registra chegada separadamente. Medição antiga não fica atual só por chegar agora. Ausência de observações produz mensagem sem amostras.')
table(['Indicador','Função / apoio à decisão'],[
 ['Nível máximo','MAX(water) no recorte; localizar pico do cenário.'],
 ['Umidade média','SUM(soil)/COUNT(amostras); acompanhar saturação representada. É média das observações, não da população.'],
 ['Pontos com último risco alto','Contar cada ponto uma vez, conforme a última amostra no recorte e sua análise disponível; priorizar acompanhamento.'],
 ['Maior variação média','Por ponto: (última água - primeira água) / minutos decorridos. Mostrar o maior valor. Nulo sem intervalo válido; negativo indica queda.']
],[165,346])
add('Os filtros são compartilhados entre cartões, duas séries e exportação. O mapa apresenta estado atual dos pontos do recorte, enquanto os indicadores descrevem o período escolhido. A lista de ocorrências é operacional e independente do recorte histórico.')
add('Gráficos de água em cm e umidade em % usam horários medidos e espaçamento proporcional. Há tooltips com data/valor. O fuso mostrado é o do navegador; armazenamento e agrupamento são UTC. O simulador comprime tempo e pode gerar taxas grandes, sem significado físico validado.')
add('Materializar e conferir','Sub2')
add('python tools/process_data.py --community AR-001 --origin simulated','Mono2')
add('O script grava data/lake/silver/readings.csv e data/lake/gold/indicators.json. Exemplos de saída fictícia estão em docs/evidence. Modelo e dicionário de campos completos em docs/DADOS.md. Não é necessário DAX: as funções são implementadas em Python sobre SQLite.')
add('A solução simula a arquitetura de dados de um MVP. Não alega infraestrutura ou desempenho Big Data distribuído.','Small2')
page('03 / MVP, IoT e experiência','Um uso completo, com dois canais sensoriais')
table(['Tela','Uso funcional'],[
 ['Login','Sessão no servidor e perfil provisionado pela CLI. Não existe senha padrão.'],
 ['Mapa','Pontos esquemáticos, estado atual, filtros e indicadores do recorte.'],
 ['Sensores','Duas séries, histórico medido, formulário de gestor e análise única.'],
 ['Morador','Avisos persistidos da sua comunidade, chegada automática e confirmação do ID mostrado; relato de ocorrência.'],
 ['Gestão','Dashboard filtrável, CSV, transição de chamados e monitoramento do serviço.']
],[105,406])
add('Circuito Wokwi sem montagem manual de fios','Sub2')
add('Cole iot/sketch.ino em sketch.ino e iot/diagram.json em diagram.json. O ultrassônico representa nível de água; o potenciômetro é explicitamente um mock de umidade. TRIG D9, ECHO D10, SIG do potenciômetro A0; LEDs D6/D5. THREE_PIN_SENSOR=0 para HC-SR04 de quatro pinos.')
add('Copie linhas completas em ordem de uptime para iot/minhas-leituras.jsonl. Gere a chave uma vez e envie pelo bridge. O mesmo arquivo não é importado duas vezes por engano; --new-run cria outro exercício explícito.')
add('Roteiro de demonstração','Sub2')
for item in [
 '1. Gestor entra; Wokwi varia água e solo; a ponte retorna reading ID, analysis_id e receipt_id.',
 '2. Os gráficos abertos atualizam as amostras e seus horários. Baixo e alto nível produzem classes distintas.',
 '3. Morador recebe o aviso na caixa em uma aba ativa. Confirma o número exibido. Não há botão para fabricar um aviso.',
 '4. Morador registra ocorrência; gestor a vê e muda de Aberto para Em análise e depois Concluído.',
 '5. Gestor aplica comunidade, período e origem; cartões, gráficos e CSV refletem as mesmas leituras.']:
 add(item)
add('Prova realizada nesta implementação','Sub2')
add('Navegador: login, recorte sem dados por origem, dois gráficos, gravação de leitura, aviso novo chegando sem recarga, confirmação do mesmo aviso e ocorrência do morador chegando à gestão. O projeto Wokwi por arquivos foi entregue; a nova montagem no simulador e suas capturas devem ser feitas pelo grupo.')
add('O caso Wokwi informado por Ruan (aproximadamente 54,6 cm e 35%) é compatível com o circuito. Não foi usada uma placa física. SMS/WhatsApp real é uma extensão e não participa da prova do aviso interno.','Small2')
page('04 / DevOps, segurança e qualidade','Execução comprovada, limites declarados')
add('Segurança implementada','Sub2')
add('Scrypt com salt, sessão opaca em cookie HttpOnly, CSRF, limite de login, validação de entrada, chave individual de dispositivo e controle de perfil no servidor. Produção exige HTTPS e cookie Secure; o exercício local roda em localhost. Morador só confirma avisos da própria comunidade.')
add('Testes executados','Sub2')
table(['Grupo / casos','Resultado'],[
 ['Backend: autenticação, perfil, CSRF, ingestão, alertas, métricas, UTC, migração e monitoramento','34 testes passaram em Python 3.12.14.'],
 ['Gráficos: ausência de dados, tempo proporcional, valores inválidos e escape de texto','4 testes Node passaram.'],
 ['Sintaxe e arquivos','node --check e rotas dos cinco HTMLs/recursos verificadas.'],
 ['Fluxo sintético repetido','20 entradas com classe, aviso e ACK correspondentes; não são 20 previsões de campo.']
],[345,166])
add('Plano de 14 grupos de casos está em docs/TESTES.md; logs em docs/evidence. A matriz do CI inclui Python 3.12 e 3.13, mas somente 3.12 foi executado neste ambiente.')
add('Monitoramento funcionando','Sub2')
m=flow['monitoring']
add(f"O ensaio registrou banco <b>{m['database']}</b>, <b>{m['requests_total']} requisições</b>, <b>{m['server_errors_total']} erros de servidor</b> e {m['records']['readings']} leituras / {m['records']['analyses']} análises / {m['records']['alerts']} avisos no banco temporário. Há endpoint de gestor e botão na Gestão para consultar uptime, mediana de latência e contadores.")
add('Os contadores são por processo, reiniciam no restart e não substituem observabilidade distribuída. Esta é a evidência de monitoramento local para a opção DevOps da rubrica.')
add('Docker, CI e versionamento','Sub2')
add('Código organizado e versionado em Git; Dockerfile não-root, Compose com volume e workflow de testes/build/smoke test entregues. Caminhos usam frontend. O CI publica relatórios somente quando efetivamente executado pelo grupo; não há deploy Python automático configurado.')
add('<b>Não executados aqui:</b> build Docker, workflow remoto no GitHub, Python 3.13, placa física, Ollama e envio Twilio. Não apresentar arquivos de configuração como se fossem logs de execução. A rubrica aceita Docker, CI/CD, Jenkins ou monitoramento; não é necessário afirmar que todos foram executados.','Small2')
page('05 / Instalação, entrega e checklist','Atualizar sem perder contas e leituras')
add('Pare o servidor e faça backup da pasta data inteira. Extraia em uma pasta nova; copie a data antiga para a nova, mesclando. Preserve seu .env local, sem incluí-lo na entrega pública. Não copie .venv entre caminhos diferentes. O backend aplica migrações aditivas, sem apagar tabelas ou contas.')
add('Na raiz do projeto, no PowerShell','Sub2')
for text in ['py -3.13 -m venv .venv',r'.\.venv\Scripts\python.exe -m pip install -r requirements.txt',r'.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8080 --workers 1 --no-proxy-headers']:
 add(escape(text),'Mono2')
add('Acesse http://localhost:8080. Se não trouxe um banco, crie gestor e morador pela CLI, conforme README. Não há conta padrão. O site de apresentação estático não executa esse backend.')
add('Conferência da rubrica (15 pontos possíveis)','Sub2')
table(['Área','Entregue e evidência ainda necessária'],[
 ['IA e automação','Motor e automação implementados, regras/prompt neste PDF, exemplos e métricas registradas. Mostrar execução local do fluxo para avaliação.'],
 ['Dados e visualização','Modelo, Bronze/Silver/Gold, processamento, quatro indicadores filtráveis e funções documentados. Conferir seus dados reais de simulação no recorte.'],
 ['MVP e IoT','Cinco páginas, dois canais mock, fluxo interno e arquitetura. Capturar o Wokwi em execução com ambos canais alterados.'],
 ['Engenharia','Git, segurança, 34+4 testes e monitoramento executados. Docker/CI opcionais configurados, mas evidência remota ainda depende do grupo.']
],[130,381])
add('Arquivos que o avaliador deve receber','Sub2')
add('Código e README; este PDF; circuito sketch.ino/diagram.json; saídas próprias da simulação; logs de teste; amostra Bronze/Silver/Gold; JSON do ensaio; capturas ou gravação do fluxo do grupo; acesso ao repositório do grupo.')
add('A primeira versão do PDF de revisão continua sendo um diagnóstico histórico. Este guia descreve a v2. Não substitui as evidências de execução do ambiente do aluno nem garante pontuação. Limites, origem simulada e recursos não executados devem permanecer explícitos.','Small2')

def decorate(c,doc):
 c.setFillColor(navy);c.rect(0,A4[1]-15,A4[0],15,fill=1,stroke=0);c.setStrokeColor(line);c.line(42,40,A4[0]-42,40);c.setFillColor(colors.HexColor('#5d7079'));c.setFont('Helvetica',7);c.drawString(42,27,'AlertaRio v2 | Guia de entrega | 17/11/2026');c.drawRightString(A4[0]-42,27,str(doc.page))
SimpleDocTemplate(str(OUT),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=35,bottomMargin=52,title='AlertaRio v2 - Guia de entrega e evidências').build(story,onFirstPage=decorate,onLaterPages=decorate)
print(OUT)
