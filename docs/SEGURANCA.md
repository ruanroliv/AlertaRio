# Autenticação e segurança do MVP

## Implementado

- Cadastro administrativo local por CLI, sem autoatribuição de perfil pelo navegador.
- Senhas com scrypt N=131072, r=8, p=1, salt individual de 16 bytes. Hash não reversível; comparação de tempo constante.
- Senha mínima de 12 caracteres no cadastro, sem senha padrão embutida.
- Cookie opaco HttpOnly e SameSite=Strict. Em `APP_ENV=production`, cookie Secure com prefixo `__Host-` e exigência de `APP_ORIGIN=https://...`.
- Token de sessão aleatório de 32 bytes; somente SHA-256 do token no banco; validade de 8 horas e revogação no logout. O token de autenticação não fica em localStorage/sessionStorage.
- O token CSRF fica na sessão do servidor e em memória no JavaScript; mutações por cookie exigem token e rejeitam Origin diferente do configurado. Login aceita somente JSON e verifica Origin quando enviado pelo navegador.
- Rate limit persistido em SQLite por conta e IP para login, sem confiar em X-Forwarded-For fornecido pelo cliente. Até duas verificações de senha simultâneas por processo para limitar pressão de memória.
- Perfil verificado no servidor para gestão, alteração de status, simulação de sensores, LLM e envio de mensagens.
- Chave individual por sensor, armazenada em hash, validada no endpoint IoT. Rotação pelo comando `device-key`; limite de ingestão de uma leitura/segundo/sensor.
- Validação de faixa, fuso horário, idade máxima de 24h, futuro máximo de 5 min e rejeição de leitura duplicada/anterior à última recebida do sensor.
- Consultas SQL parametrizadas, arquivos servidos por allowlist, registros de auditoria e proteção contra HTML em texto dos chamados na interface.
- Cabeçalhos CSP, X-Content-Type-Options, proteção de iframe, política de referência e no-store para API/HTML.
- Segredos por variáveis de ambiente; `.env` e dados persistidos fora do Git e do ZIP de entrega.

## Executar em produção

Use HTTPS com certificado válido, `APP_ENV=production`, `APP_ORIGIN` igual à origem pública exata, proxy reverso corretamente configurado e volume persistente com backup. O modo local HTTP usa cookie sem Secure para permitir o exercício em localhost; não o exponha como produção.

O servidor desativa confiança automática em cabeçalhos de proxy. Atrás de proxy, o rate limit por IP verá o IP do proxy; configure preservação confiável do IP com uma arquitetura adequada antes de liberar para muitos usuários. Não aceite cabeçalhos encaminhados de qualquer cliente da internet.

## Limitações explícitas

Não houve auditoria externa, pentest, MFA, recuperação de senha, verificação de e-mail, gestão de consentimento populacional ou alta disponibilidade. Usuários são provisionados por administrador; senhas/usuários podem ser substituídos via rotina administrativa futura. Para revogar acesso emergencialmente, um administrador com acesso ao banco pode desativar a conta; isso invalida também as sessões na próxima requisição.

A arquitetura SQLite usa um worker e é voltada a MVP. Limites locais não substituem WAF/rate limit distribuído e limites de corpo/conexão no proxy. A verificação Content-Length é uma camada adicional, não um limite completo para todo tipo de transferência HTTP. HTTPS e controles operacionais do host são necessários.

As migrações são aditivas; não apagam usuários ou leituras. A confirmação de aviso é restrita à comunidade do morador. O GET de análise não muda estado; reanálise exige POST autenticado e CSRF.

A aplicação cria alertas experimentais, não orientações oficiais. O gateway de mensagem só permite destinatários de teste e exige habilitação explícita. Nunca colocar moradores em um fluxo de evacuação baseado neste modelo sintético.
