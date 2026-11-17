# Integrações e limites verificados

| Integração | Implementação | Verificação nesta entrega |
|---|---|---|
| HTML/JS → FastAPI → SQLite | Sessão, leituras, alertas, chamados e exportação | API testada e fluxo gestor verificado no navegador |
| Open-Meteo | Previsão horária, cache 10 min e acumulado das próximas 3h | Consulta externa real respondeu; análise com previsão vista no navegador |
| kNN local | 300 amostras sintéticas, k=5, limites explícitos | Executado; não validado para emergências |
| Ollama | POST /api/generate, explicação cognitiva opcional | Contrato implementado; nenhum modelo local disponível para execução ponta a ponta |
| Twilio SMS/WhatsApp | Prévia, envio restrito, proteção contra duplicidade | Prévia e bloqueios testados; nenhum envio real realizado |
| Tinkercad | Sketch, tabela de ligações, replay JSONL | Tinkercad abriu sem sessão autenticada; montagem/execução na conta do grupo pendentes |
| Arduino USB | Ponte pyserial com chave individual | Caminho implementado; sem placa física disponível |
| Docker | Dockerfile não-root e Compose | Docker indisponível neste ambiente; build/smoke test configurados no CI |
| CI | Testes API, sintaxe JS, build e smoke test Docker | Arquivo de workflow entregue; execução no GitHub depende de colocar o repositório lá |

## Previsão do tempo

Endpoint autenticado: `GET /api/weather/AR-001`. A API usa Open-Meteo com coordenadas aproximadas do centro de cada comunidade. Não usa localização do cidadão. Previsão é uma saída meteorológica de modelo, não chuva medida por um sensor. Horários são UTC, identificados como tal.

Consulta de classificador com previsão: `POST /api/analysis/AR-001/refresh` (gestor + CSRF, corpo `{}`). Sem a opção, o classificador local usa só a leitura persistida. A previsão não é somada à chuva já medida como se fosse a mesma grandeza.

Falhas retornam 502/429 de forma explícita. Valores fictícios não substituem uma previsão indisponível. O uso do serviço deve respeitar seus termos e a atribuição de fonte.

## SMS / WhatsApp

O provedor implementado é Twilio. São necessárias conta, remetente autorizado e credenciais no `.env` local. WhatsApp também depende do sandbox ou remetente aprovado e das regras vigentes de janela/template do provedor; texto livre não funciona em qualquer contexto.

O envio está desligado por padrão. O backend exige simultaneamente:

- Gestor autenticado, sessão válida e token CSRF.
- `ENABLE_REAL_MESSAGES=true` no servidor.
- Destinatário E.164 incluído em `MESSAGE_TEST_RECIPIENTS`.
- Corpo com `dry_run=false` e `confirm_send=true`.

Cada mensagem é prefixada como EXERCÍCIO ACADÊMICO e não como aviso oficial. As credenciais não entram no JavaScript, no sketch ou no Git. Não cole chaves no chat.

`POST /api/alerts/{id}/notify` aceita:

```json
{"phone":"+5511999999999","channel":"sms","dry_run":true,"confirm_send":false}
```

Esse exemplo só retorna a prévia. Faça o teste com um número seu autorizado e não com moradores reais. Envio real pode gerar cobrança no provedor.

Para chamadas pelo terminal, primeiro faça login, guarde o cookie retornado e o `csrf_token` somente no ambiente da ferramenta. O script `tools/notify.py` solicita esses dados por login interativo, sempre começa em prévia e pede confirmação local antes de enviar quando executado com `--send`.

A API cria um registro único por alerta/destinatário/canal antes de acionar o provedor. Sucesso significa aceitação no provedor, NÃO entrega ao celular. Timeout/falha mantém estado `unknown` para evitar reenvio automático potencialmente duplicado. Verifique a situação no provedor antes de qualquer recuperação administrativa. Não existe webhook de confirmação de entrega nesta versão.

Os alertas internos são criados automaticamente quando a classe muda; a mensagem externa é uma ação explícita de teste. Não há disparo em massa ou envio automático para uma população cadastrada.

## Hospedagem

A URL de apresentação existente continua sendo uma demonstração estática. Ela não executa Python e não contém autenticação real. O projeto completo usa o mesmo front-end servido pelo FastAPI, no mesmo domínio da API.

Para colocar o backend na internet, é necessário um ambiente com Python/Docker, armazenamento persistente e HTTPS. Escolha de provedor, conta e domínio ainda não foi feita. A versão entregue já pode ser executada localmente sem contratar hospedagem.

## Referências oficiais

- FastAPI: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
- Open-Meteo: https://open-meteo.com/en/docs
- Ollama: https://docs.ollama.com/api/generate
- Twilio: https://www.twilio.com/docs/messaging/api/message-resource
- Arduino pulseIn: https://docs.arduino.cc/language-reference/en/functions/advanced-io/pulseIn/
- Tinkercad Circuits: https://www.tinkercad.com/circuits


## Mudança da versão 2
A caixa do morador exibe avisos persistidos automaticamente. Não existe mais botão de geração de mensagem fictícia no modo backend. Confirmação usa o ID exibido. O envio externo continua opcional, por script, independente dessa caixa. O backend usa frontend/; dist/ é somente saída de build estático.
