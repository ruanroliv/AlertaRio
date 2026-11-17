# Coleta, tratamento e indicadores

## Modelo e camadas

Um ponto (devices) tem leituras (readings); cada leitura pode ter análises versionadas (analyses). Mudança de classe gera um aviso (alerts), vinculado à análise e à leitura. Confirmações (acknowledgments) vinculam usuário e aviso. users/sessions e calls/audit completam autenticação e operação.

- Bronze: `data/lake/bronze/AAAA-MM-DD.jsonl`, com recibo, origem, payload original autenticado e status received/processed/rejected. A chave do dispositivo está no cabeçalho, não no diário. Leituras inválidas autenticadas preservam valor e motivo. Erros de JSON não interpretável ou autenticação não geram observação válida.
- Silver: SQLite normalizado e `data/lake/silver/readings.csv` materializado pela ferramenta; datas UTC, faixas validadas, IDs e procedência. Dados pessoais não entram no CSV.
- Gold: `data/lake/gold/indicators.json`, com indicadores, séries e escopo dos filtros. A API calcula a mesma camada para o dashboard.

`python tools/process_data.py --community AR-001 --origin simulated` exporta o recorte. Aceita também --start e --end em ISO 8601 com fuso. O banco é a fonte autoritativa. O esquema simula uma arquitetura de dados para um MVP; não alega processamento Big Data distribuído.

## Dicionário essencial

| Campo | Tipo/unidade | Significado |
|---|---|---|
| sensor_id | texto AR-001..AR-005 | Ponto monitorado com duas entradas sensoriais |
| water_level_cm / water | número, cm | Nível representado pelo ultrassônico |
| soil_moisture_pct / soil | número, % | Umidade mock do potenciômetro |
| rainfall_mm / rain | número, mm | Entrada declarada do cenário, separada da previsão |
| measured_at | ISO 8601 UTC | Horário da medição, reconstruído do uptime no replay |
| received_at | ISO 8601 UTC | Horário da ingestão no servidor |
| device_uptime_ms | inteiro, ms | Contador do sketch preservado |
| event_id | texto | Identificador idempotente da linha/replay |
| simulated | booleano | Origem simulada ou transporte físico |
| receipt_id | texto | Rastreia Bronze e processamento |
| analysis_id | inteiro | Análise persistida usada por estado e aviso |

## Regras de tratamento

Validação: água 0–200 cm, solo 0–100%, chuva informada 0–300 mm, datas com fuso, idade máxima 24h, futuro máximo 5 min; ordem crescente por ponto e event_id sem repetição. Medições com mais de 5 min não são apresentadas como atuais. Não preencher ausência de amostras com zeros. UTC antes de agrupar. Não somar previsão futura e chuva observada como se fossem a mesma medida.

## Indicadores e funções

Todos recebem comunidade, início, fim e origem iguais aos gráficos e CSV. Os limites de tempo são inclusivos. Fuso de exibição é do navegador; persistência é UTC.

1. Nível máximo no recorte = MAX(water) das amostras filtradas.
2. Umidade média das amostras = SUM(soil)/COUNT(amostras). É média de observações, não média ponderada por população ou por comunidade.
3. Pontos com último risco alto = COUNT(pontos cuja última amostra no recorte tem classificação Alto). Um ponto não é contado várias vezes pela quantidade de amostras. A análise disponível mais recente da leitura é utilizada.
4. Variação média por ponto = (última água − primeira água)/(último horário − primeiro horário em minutos). O cartão usa o maior valor entre os pontos filtrados. Nulo com menos de duas amostras ou intervalo zero. Negativo indica queda; passos comprimidos do simulador podem gerar taxas grandes, sem interpretação física validada.

Agregação horária: GROUP por hora UTC, com quantidade e médias de água/solo. Implementação em Python sobre dados SQLite; DAX é opcional na rubrica.

Os gráficos usam os timestamps medidos, com espaçamento proporcional aos intervalos e tooltips de data/valor. Água e solo são séries separadas, em cm e %. O mapa mostra estado atual dos pontos presentes no recorte; seus pinos são esquemáticos. Por isso o risco atual pode estar desatualizado enquanto um indicador histórico ainda descreve dados do período escolhido.
