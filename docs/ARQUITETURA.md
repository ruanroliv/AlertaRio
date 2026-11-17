# Arquitetura AlertaRio v2

```mermaid
flowchart TD
  W["Wokwi: água e solo mock"] -->|"cópia manual"| J["Arquivo JSONL"]
  J --> B["Ponte Python: tempo e event_id"]
  B --> A["FastAPI: chave e validação"]
  A --> R["Bronze: original e rejeitados"]
  A --> S["Silver: leituras UTC no SQLite"]
  S --> I["Motor kNN: análise persistida"]
  M["Open-Meteo opcional"] --> I
  I --> V["Avisos com analysis_id"]
  V --> C["Morador: caixa e confirmação"]
  S --> G["Gold: agregações e filtros"]
  G --> F["Mapa, sensores e gestão"]
  I --> F
  C --> S
  L["Ollama opcional: explicação"] -.-> I
  D["Git, testes e monitoramento"] -.-> A
```

As leituras são simuladas e identificadas; o replay não é rede direta do Arduino virtual. Bronze guarda original autenticado e resultado do tratamento; Silver e análises ficam no SQLite; Gold é materializável em JSON/CSV e servido pela mesma API do dashboard. O backend serve frontend/ no mesmo domínio, com cookie de sessão e CSRF.

O motor cria uma análise por ingestão, usa previsão em cache quando disponível e gera aviso em mudança de classe. Atualizar com previsão é um POST de gestor e cria outra análise persistida. A caixa do cidadão consulta a cada 5s e confirma o ID mostrado. O histórico dos avisos não usa o risco atual para reescrever classes passadas.

A conexão Ollama é de explicação da análise, não de decisão ou comando operacional. Mensagens externas são extensão por script com habilitação e destinatário autorizado; não são requisito para o aviso interno funcionar.
