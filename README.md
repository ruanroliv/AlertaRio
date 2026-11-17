# Atualização: dashboards com base demonstrativa

Ao iniciar o servidor em desenvolvimento, o projeto agora grava automaticamente **245 leituras fictícias (49 em cada um dos cinco pontos), análises, avisos de exercício e cinco ocorrências**. Não depende do Arduino, Wokwi, previsão ou serviços externos. Água, solo e chuva variam ao longo de 24 horas, com diferentes classes de risco. Nenhuma conta ou senha padrão é criada.

**Para usar:** extraia esta versão em uma pasta nova; siga a instalação abaixo e entre com sua conta. Caso queira preservar usuários, pare o servidor e copie sua pasta `data` para a nova instalação antes de iniciar. A carga acontece uma única vez e preserva os registros existentes. Reiniciar não duplica nem atualiza artificialmente os horários. Nas próximas datas, os dados continuam no histórico; a indicação de leitura desatualizada é correta.

Os gráficos e indicadores mostram a base sem depender do dispositivo. Use origem **Todas** ou **Simuladas** e limpe filtros de data para ver o histórico. A origem **Dispositivo** exclui os dados demonstrativos. A ponte Wokwi continua marcada como simulação. Dados anteriores do Arduino são preservados e continuam sendo os mais recentes do ponto; a base é acrescentada antes deles. Não são enviados SMS/WhatsApp durante essa carga.

Para desativar a carga automática antes da primeira inicialização no PowerShell:
```powershell
$env:DEMO_DATA="false"
```
Isso não remove registros já carregados. Em produção a carga automática fica desativada independentemente dessa variável. O servidor não lê `.env` automaticamente; use variáveis de ambiente ou `--env-file` com o suporte necessário instalado.

---

# AlertaRio

MVP em HTML/CSS/JavaScript puro, Python/FastAPI e SQLite. A IA e os limites são experimentais e usam dados sintéticos. Não é um sistema de alerta oficial.


## Instalar no Windows / VS Code

Abra a raiz `AlertaRio` no VS Code. PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Em instalação nova, crie as contas (não execute novamente se trouxe seu banco):

```powershell
.\.venv\Scripts\python.exe -m backend.manage create-user --email gestor@example.com --role manager
.\.venv\Scripts\python.exe -m backend.manage create-user --email morador@example.com --role resident --community AR-001
```

A CLI solicita uma senha de pelo menos 12 caracteres. Não há credenciais padrão. Os e-mails são identificadores locais; não existe envio de e-mail. Não precisa ativar a venv nem alterar a política de execução do PowerShell.

Inicie:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8080 --workers 1 --no-proxy-headers
```

Acesse **http://localhost:8080**, com esse endereço exato. A origem padrão da proteção CSRF é localhost:8080. Se escolher outro host/porta, defina `APP_ORIGIN` no ambiente do processo antes de iniciar. Não use Live Server para autenticação real.

## Estrutura

- `frontend/`: index, mapa, sensores, morador, gestao, styles.css, app.js, charts.js e config.js.
- `backend/main.py`: rotas, sessão, autorização e aplicação web.
- `backend/engine.py`: análise persistida única e geração automática de avisos.
- `backend/risk.py`: kNN e pisos didáticos.
- `backend/analytics.py`: filtro compartilhado, históricos e agregações.
- `backend/lake.py`: diário Bronze com original, recibo e resultado do processamento.
- `backend/monitoring.py`: requisições, erros, uptime e latência em memória.
- `backend/db.py`, `security.py`, `manage.py`: schema/migrações, senha e provisionamento.
- `iot/`: código Arduino, circuito JSON, amostra fictícia e ponte Python.
- `tools/process_data.py`: Silver CSV e Gold JSON sem dados pessoais.
- `tools/verify_flow.py`: ensaio reproduzível em banco temporário, sem mensagens externas.
- `docs/`: arquitetura, regras, dados, testes, integrações e evidências.
- `tests/`: testes backend e gráficos.
- `Dockerfile`, `compose.yaml`, `.github/workflows/ci.yml`: contêiner e pipeline.

## Dados para começar sem circuito

Opcional, somente se o banco ainda não possui leituras:

```powershell
.\.venv\Scripts\python.exe -m backend.manage seed-demo
```

Isso cria cinco leituras fictícias identificadas como simulação. O gráfico só contém as amostras existentes; use Wokwi ou o formulário para gerar uma série. Após cinco minutos sem medição recente, o ponto fica desatualizado.

## Testes e evidências reproduzíveis

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check frontend/app.js
node --test tests/frontend.test.cjs
.\.venv\Scripts\python.exe tools/verify_flow.py
.\.venv\Scripts\python.exe tools/process_data.py
```

Node é necessário para os testes JS, não para servir as páginas. O benchmark usa banco temporário e mede disponibilidade de alerta na API, não tempo humano ou de entrega de SMS. Consulte `docs/TESTES.md` e `docs/evidence/flow.json`.

## Docker

```sh
docker compose up --build -d
docker compose exec app python -m backend.manage create-user --email gestor@example.com --role manager
```

O volume `alertario-data` preserva o banco. Não use `down -v` se deseja preservar dados. Ao atualizar uma versão, faça backup do volume. O código de treinamento é o mesmo da versão anterior; o volume inicial inclui seu CSV. Atualizações futuras desse CSV exigem migração explícita do arquivo no volume.

Docker não pôde ser executado neste ambiente. O workflow entregue executa testes, build e smoke test ao ser colocado no GitHub; não houve execução remota do CI nem deploy Python aqui. **O monitoramento local foi executado**, como opção de evidência DevOps aceita pela rubrica.

## Integrações opcionais e apresentação estática

Open-Meteo pode ser consultado e incorporado por Atualizar análise com previsão (gestor). O novo resultado é persistido e passa a alimentar o mapa e os alertas. Sem consulta, o motor usa a última previsão em cache válida, se existir, ou registra que a análise não tem previsão.

Ollama explica a mesma análise persistida; é opcional. Twilio continua em dry-run por padrão; envio real só por script/gestor e número autorizado. Nenhum envio real acompanha os testes. Veja `docs/INTEGRACOES.md`.

O backend não lê `.env` automaticamente quando executado diretamente: use variáveis `$env:NOME='valor'` no PowerShell. Docker Compose lê `.env`. Nunca coloque segredos no JavaScript, sketch ou Git.

`python tools/build_static.py` gera `dist` para a demonstração estática. Na hospedagem estática, o login e as regras são demonstrativos e os registros ficam na sessão do navegador. Execute Python para o fluxo de autenticação, dados e IA real do projeto.
