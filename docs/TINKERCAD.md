# AlertaRio — circuito Arduino no Tinkercad

## Entrega e situação

O sketch `iot/alertario.ino`, a tabela de ligações e a ponte Python estão prontos. O Tinkercad foi aberto, mas o navegador não tinha uma sessão autenticada. Por isso o circuito não foi criado/salvo na conta do grupo nesta entrega. O sketch precisa ser compilado e a simulação executada no Tinkercad para obter as capturas exigidas pelo professor.

## Componentes

- Arduino Uno R3 e protoboard pequena.
- Sensor ultrassônico de 3 pinos (5V, GND e SIG). Para esse formato, use THREE_PIN_SENSOR=1; o pacote v2 vem em 0 para Wokwi/HC-SR04.
- Alternativa: HC-SR04 de 4 pinos (VCC, GND, TRIG e ECHO); manter `THREE_PIN_SENSOR` em `0`.
- Potenciômetro de 10 kΩ para representar a umidade do solo, sem fingir que é uma medição real de solo.
- Um LED vermelho, um verde e dois resistores de 220 Ω.

## Ligações

| Origem | Destino |
|---|---|
| Arduino 5V | Trilho positivo da protoboard |
| Arduino GND | Trilho negativo da protoboard |
| Ultrassônico VCC/5V | Trilho positivo |
| Ultrassônico GND | Trilho negativo |
| Ultrassônico SIG (3 pinos) | D9 |
| HC-SR04 TRIG (alternativa 4 pinos) | D9 |
| HC-SR04 ECHO (alternativa 4 pinos) | D10 |
| Potenciômetro: terminal externo 1 | 5V |
| Potenciômetro: cursor central | A0 |
| Potenciômetro: terminal externo 2 | GND |
| D6 | Resistor 220 Ω → ânodo do LED vermelho |
| D5 | Resistor 220 Ω → ânodo do LED verde |
| Cátodo de cada LED | GND |

Os GNDs devem ser comuns. Se usar trilhos separados na protoboard, faça as pontes entre eles.

## Montar e demonstrar

1. Entre em https://www.tinkercad.com/circuits e crie um circuito.
2. Adicione os componentes e ligue conforme a tabela.
3. Abra Código, escolha Texto, cole o conteúdo completo de `iot/alertario.ino`.
4. Confira o valor de `THREE_PIN_SENSOR` e inicie a simulação.
5. Abra o Monitor Serial a 9600 baud.
6. Ajuste a distância do ultrassônico e gire o potenciômetro.
7. O nível calculado é `200 cm - distância`; distância de 145 cm representa nível de 55 cm. Distância de 20 cm representa nível de 180 cm.
8. O potenciômetro varia de 0 a 100%. O LED vermelho acende com água >=100 cm ou umidade >=65%; o verde indica abaixo desses limites didáticos. O LED não representa o modelo kNN do servidor.
9. Em timeout do ultrassônico, ambos LEDs apagam e sai um JSON de erro, que a ponte descarta. Não é substituído por nível zero.

Saída esperada, apenas ilustrativa (substitua pela saída observada):

```json
{"sensor_id":"AR-001","water_level_cm":180.0,"soil_moisture_pct":90.0,"uptime_ms":6000}
```

## Caminho dos dados do Tinkercad até a API

O Uno virtual deste exercício não tem conexão de rede configurada. A ponte abaixo lê um arquivo com linhas copiadas do Monitor Serial; isso é um replay/importação, não streaming automático diretamente do site.

1. Copie somente as linhas JSON do Monitor Serial para `iot/minhas-leituras.jsonl`.
2. Crie a chave individual do sensor no backend:

```powershell
.\.venv\Scripts\python.exe -m backend.manage device-key --sensor AR-001
```

3. Guarde a chave mostrada em variável de ambiente **local**, sem colar em mensagens ou versioná-la:

```powershell
$env:DEVICE_API_KEY = Read-Host 'Chave do sensor'
.\.venv\Scripts\python.exe iot/bridge.py --file iot/minhas-leituras.jsonl --rain-mm 0
```

A chuva é uma entrada explícita separada; o circuito não possui pluviômetro. O replay usa o horário de importação como `measured_at`; `uptime_ms` do simulador não é horário civil. Todas as leituras do arquivo entram como `simulated=true`.

Para demonstrar a ingestão antes de montar o circuito, existe `iot/example.jsonl`. Ele contém dados fictícios escritos no projeto, não uma captura real do Tinkercad.

## Arduino físico via USB

Com placa real conectada, o mesmo código pode enviar pela serial:

```powershell
.\.venv\Scripts\python.exe iot/bridge.py --port COM3 --rain-mm 0
```

O caminho USB marca `simulated=false` para indicar a origem física do transporte. Isso NÃO certifica calibração, qualidade do sensor nem a umidade simulada pelo potenciômetro. A ponte roda no computador; não é um módulo Wi-Fi embarcado.

## Capturas para avaliação

- Circuito inteiro com ligações e nomes dos componentes visíveis.
- Código compilado e simulação em execução.
- Cenário de nível baixo e solo seco.
- Cenário de nível alto e solo úmido, com LED vermelho e JSON correspondente.
- Retorno da ponte com `accepted_id` e a leitura no painel conectado ao backend.


Na v2, prefira docs/WOKWI.md para replay com preservação do uptime, IDs de eventos e atualização automática do painel. O código do circuito é o mesmo, com a seleção de três ou quatro pinos.
