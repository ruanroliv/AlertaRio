# Plano de testes e evidências

## Executar

Python: `python -m unittest discover -s tests -v`.
JavaScript: `node --test tests/frontend.test.cjs` e `node --check frontend/app.js`.
Fluxo/métrica: `python tools/verify_flow.py`.
Camadas: `python tools/process_data.py`.

| Caso | Entrada / ação | Saída esperada |
|---|---|---|
| T01 Acesso | Login válido, inválido e tentativas repetidas | Cookie HttpOnly; erro genérico; 429 ao exceder limite |
| T02 Perfil/CSRF | Morador tenta alterar leitura; POST sem CSRF | 403 e nenhuma alteração |
| T03 Ingestão | Leitura válida com chave do ponto | Reading + analysis + recibo; aviso se classe mudar |
| T04 Qualidade | Solo 150%, data inválida, evento repetido | Rejeição; inválido autenticado retido na Bronze; sem amostra tratada duplicada |
| T05 Ausência/tempo | Nenhuma amostra; medição de 1h recebida agora | Histórico vazio; ponto desatualizado; nenhuma curva de zeros |
| T06 Gráficos | Três amostras com intervalos 1s e 9s | Três pontos com espaçamento proporcional e horários medidos |
| T07 Analytics | Comunidade, período e origem definidos | Mesmos registros em cartões, séries e CSV; médias/máximos conferidos |
| T08 UTC | Mesmo instante em UTC e UTC−3 | Mesmo bucket horário UTC |
| T09 Análise única | Baixo risco + previsão mock 40mm, reanalisar | Mesmo analysis_id/risco em API, mapa e aviso |
| T10 Cidadão | Novo aviso; confirmar número exibido | Caixa mostra registro persistido; ACK grava esse ID; outra comunidade é bloqueada |
| T11 Ocorrência | Morador registra relato; gestor analisa | Registro persistido e transição de status válida |
| T12 Monitoramento | Gestor consulta métricas após requisições | Banco ok, uptime e contadores; morador recebe 403 |
| T13 Migração | Banco com contas existentes; repetir init | Contas preservadas e colunas novas disponíveis |
| T14 Provedor | Previsão indisponível e mensagem externa desligada | Erro explícito; nenhum dado fictício/nenhum envio pago substitui a falha |

## Resultado entregue

34 testes Python e 4 testes Node executados com sucesso no ambiente Python 3.12.14 / Node local. Logs em docs/evidence. A matriz do CI inclui 3.12 e 3.13, mas 3.13 não foi executado aqui. Os serviços externos pagos e Ollama não foram usados nesses testes.

No navegador, foram verificados login, filtros, ausência de amostras por origem, duas séries, salvamento de leitura, aviso novo aparecendo sem recarga na caixa já aberta, confirmação do mesmo ID e ocorrência do morador chegando à gestão. Não houve montagem de novo circuito no Wokwi nesta etapa; os arquivos e o replay estão entregues.

## DevOps

O serviço de monitoramento foi executado e seu resultado consta no ensaio flow.json. No painel Gestão há botão para consultar uptime, requisições, erros e registros. Contadores são por processo e reiniciam com o serviço. Isso não é uma plataforma de observabilidade distribuída.

Docker e GitHub Actions continuam como configuração reproduzível; nenhum build Docker ou workflow remoto foi executado neste ambiente. Não declarar CI/CD concluído sem o log/execução correspondente. A opção monitoramento funcionando é a evidência disponível para o critério DevOps.
