# Inteligência aplicada, regras e ganho

## Tarefa do cidadão

Transformar duas entradas sensoriais e chuva declarada em uma classe experimental e um aviso legível, sem exigir que o morador interprete números ou clique para fabricar um aviso. O sistema não emite ordem real de evacuação.

## Algoritmo

kNN local (k=5), 300 exemplos sintéticos em data/training/risk_synthetic.csv, normalização água/200, solo/100 e chuva/100, distância euclidiana quadrática e voto. Desempate prioriza a classe maior. Piso Atenção: água>=100 ou solo>=65. Piso Alto: água>=160 ou solo>=85. Previsão>=30 mm próximas 3h eleva o piso uma classe. A classe final é o máximo entre voto e piso.

25/60/90 são códigos ordinais, não probabilidades calibradas. Os rótulos foram gerados por regras sintéticas. Aderência a esses cenários não é acurácia de previsão em comunidades reais.

## Uma análise persistida

Cada ingestão cria analyses com reading_id, modelo, versão, resultado, fontes e timestamp. Se há previsão em cache com menos de 10 min, ela entra explicitamente; senão a análise registra ausência de previsão. Mapa, caixa de avisos e API leem a mesma análise persistida. Alertas guardam a classe histórica original.

GET /api/ai/AR-001 lê a análise. POST /api/analysis/AR-001/refresh (gestor+CSRF) busca previsão e persiste outra análise da última leitura recente. Essa atualização também pode gerar aviso por mudança de classe. GET com use_forecast=true não altera estado; retorna instrução para usar POST. Isso evita uma consulta GET modificando dados.

## Prompt opcional Ollama

“Você explica um exercício acadêmico de monitoramento. Dados e modelo são sintéticos, sem validação para emergências. Explique em português em até 100 palavras os fatores da classificação abaixo. Não invente dados, locais, horários ou probabilidades. Não emita ordem de evacuação nem recomendação operacional. Mencione que é experimental. Dados estruturados: {assessment}”

A entrada agora é a mesma análise persistida e inclui seu analysis_id. O LLM não determina classe e não dispara mensagens. Saída textual renderizada sem executar HTML. O conector é opcional, exige modelo local e não foi executado com Ollama nesta entrega.

## Comparação e métrica reproduzível

No fluxo anterior (30652cf), para mostrar aviso após ingestão com a página já aberta era necessário recarregar e clicar em Simular recebimento: duas ações. Agora a análise é automática e a caixa consulta a API a cada 5s: zero ações para disponibilizar o aviso. A confirmação de leitura não entra nessa contagem. É comparação de passos do desenho do fluxo, não um estudo cronometrado de usuários.

`python tools/verify_flow.py` executa 20 entradas alternando 55 cm/35%/0 mm e 180 cm/90%/0 mm, consulta a caixa de uma conta morador e confirma exatamente o aviso correspondente. Mede tempo backend entre envio da leitura e disponibilidade na API, sem latência do navegador/rede externa. Resultado em docs/evidence/flow.json. O polling acrescenta até aproximadamente um intervalo de 5s em aba ativa e sem formulário em edição; abas em segundo plano podem ser limitadas pelo navegador.

O relatório registra mediana e P95 observados, 20/20 cenários e limitações. Não se trata de medir mortes evitadas, acurácia de desastre ou tempo de entrega SMS. Para ganho humano, conduzir estudo separado com tarefas iguais e tempos observados.
