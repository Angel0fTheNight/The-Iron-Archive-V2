# Arquitetura

`main.py` -> SQLite -> jobs ordenados -> adaptador manual ou Hermes -> arquivos Markdown em `projects/<slug>/outputs`.

**Modo manual (padrão):** funciona sem internet, sem credenciais e sem GPU. É um gerador de tarefas e trilha de auditoria, não uma IA autônoma. O modo Hermes pode produzir texto quando configurado com comando comprovadamente compatível.

**Estados dos jobs:** `pending` (fila), `waiting_approval` (render precisa de decisão humana), `prepared` (briefing manual pronto, sem execução), `running`, `done` (executado e validado), `failed`, `rejected`, `awaiting_integration`. No modo manual a próxima etapa avança sobre predecessores `done` ou `prepared`; bloqueia em `waiting_approval`, `failed`, `rejected`, `running` e `awaiting_integration`. No modo produção apenas `done` libera etapas seguintes. `done` é reservado a resultados realmente executados e validados; `prepared` é inserido manualmente via `main.py prepare --job N` e jamais substitui uma aprovação em `waiting_approval`.

**Segurança:** trabalhos de render ficam em `waiting_approval`; nenhum download nem publicação é executado. SQLite evita perder fila entre execuções. `reset-stale` recupera jobs deixados em `running` após travamento. Falhas são preservadas como `failed`, não repetidas automaticamente em loop. Para retry futuro, criar comando específico com limite e idempotência.

**Limitação:** jobs executam em ordem por episódio; ainda não há DAG paralela, execução contínua em background, workers remotos, verificação semântica automática ou renderizador integrado. Essa simplicidade é intencional até validar as ferramentas locais.
