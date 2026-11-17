# Wokwi integrado ao AlertaRio v2

## Dois arquivos, sem desenhar fios

Abra https://wokwi.com/projects/new/arduino-uno. Em `sketch.ino`, cole `iot/sketch.ino`. Em `diagram.json`, cole `iot/diagram.json`. O projeto inclui Uno, HC-SR04, potenciômetro como umidade mock e dois LEDs com resistores. `THREE_PIN_SENSOR` está em 0, para HC-SR04 de quatro pinos. O código `alertario.ino` é uma cópia equivalente para Arduino/Tinkercad.

TRIG=D9, ECHO=D10, potenciômetro SIG=A0, LED vermelho=D6 e verde=D5. O circuito JSON já contém alimentação e GND. Inicie e acompanhe o Monitor Serial a 9600 baud.

Distância 145 cm gera aproximadamente 55 cm de nível; distância 20 cm gera aproximadamente 180 cm. O potenciômetro altera 0–100% de umidade representada. O LED vermelho usa água>=100 ou solo>=65, não executa o kNN. O modelo do backend é uma etapa separada. Timeout gera JSON de erro, nunca uma leitura zero fictícia.

## Importação preservando o tempo da simulação

Copie somente linhas JSON completas, em ordem crescente de uptime, sem misturar reinícios, para `iot/minhas-leituras.jsonl`. Backend ativo, outro terminal na raiz:

```powershell
.\.venv\Scripts\python.exe -m backend.manage device-key --sensor AR-001
$env:DEVICE_API_KEY = Read-Host 'Chave mostrada no terminal'
.\.venv\Scripts\python.exe iot/bridge.py --file iot/minhas-leituras.jsonl --rain-mm 0
```

Não gere outra chave a cada importação: ela rotaciona a anterior. A variável só vale nesse terminal.

A ponte ancora a última amostra no começo da importação e reconstrói as anteriores pelas diferenças de `uptime_ms`. Assim, os gráficos preservam os intervalos do simulador, sem apresentar uma espera de rede como tempo de medição. `received_at` registra o instante de chegada separado. Dados do arquivo são sempre simulados.

Cada arquivo/linha gera um event_id estável. Reimportar o mesmo arquivo é rejeitado como duplicidade. Para um exercício deliberadamente novo com os mesmos valores, use `--new-run`. Isso cria outro replay, explicitamente, e não deve ser tratado como novas observações de campo.

```powershell
.\.venv\Scripts\python.exe iot/bridge.py --file iot/minhas-leituras.jsonl --rain-mm 0 --new-run
```

`rain-mm` é entrada separada, não uma medição do Arduino. O projeto não possui pluviômetro. O parâmetro deve corresponder ao cenário declarado.

O retorno mostra id da leitura, analysis_id e receipt_id. Em até 5s, um painel aberto consulta os novos dados. Mudança de classe cria aviso na caixa interna do morador. A confirmação usa seu alert_id.

O caminho é replay manual por arquivo. Não existe conexão de rede automática direta do Uno virtual para localhost. Para USB físico, existe `--port COM3`; sem placa disponível, esse caminho não foi executado nesta entrega. Mesmo USB físico não certifica calibração ou umidade real quando se usa potenciômetro.

## Evidência do aluno

Capture circuito, saída serial com dois canais alterados, recibo da ponte, dois gráficos com as mesmas amostras, aviso automático e confirmação do mesmo número. A montagem executada por Ruan foi relatada na conversa; os arquivos estão agora versionados, mas não foi aberta uma nova simulação Wokwi nesta implementação.
