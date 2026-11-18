# THE IRON ARCHIVE 2.0 — núcleo funcional (Windows)

Sistema local-first para organizar a produção de Shorts sobre ASOIAF / Game of Thrones / House of the Dragon. **Não altera nem remove o projeto antigo.** Python 3.11+ e biblioteca padrão bastam para o núcleo. O Hermes é um diretor opcional; se estiver indisponível, a fila e os agentes continuam funcionando em modo de preparação manual. Não há promessa de que seis modelos de IA sejam executados autonomamente: cada agente é um papel com contrato de entrada/saída, invocado pelo coordenador e, quando habilitado, pelo Hermes.

## Instalação segura

1. Extraia em `D:\TheIronArchive_V2` (ou outro local **novo**, sem sobrescrever o antigo).
2. Execute `INICIAR.bat`. O script detecta Python e mostra o menu. Não instala pacotes.
3. Escolha **Diagnóstico**. Confira `config/settings.json` e os caminhos locais.
4. Escolha **Criar episódio**; informe título e objetivo. A pasta e a fila serão criadas.
5. Escolha **Executar próxima etapa**. Inicialmente os agentes produzem briefings e arquivos de trabalho, sem inventar pesquisas, lore ou arquivos audiovisuais.
6. Opcional: configure `hermes.enabled=true` e `hermes.command` após testar a sintaxe da CLI instalada. Não assuma que `delegate_task` funciona.

## Comandos

```powershell
python main.py doctor
python main.py new --title "Por que Jaime matou o Rei Louco?" --goal "Revelar a ordem de incendiar Porto Real" 
python main.py status
python main.py run --steps 1
python main.py approve --job 3
python main.py reject --job 3
python main.py reset-stale
python main.py prepare --job 3
python -m unittest discover -s tests -v
```

## Funcionamento

O banco SQLite em `data/ironarchive.sqlite3` controla jobs com estados `pending`, `waiting_approval`, `prepared`, `running`, `done`, `failed`, `rejected`, `awaiting_integration`. Cada job possui tentativas, log e arquivo de resultado. `done` é reservado a resultados realmente executados e validados; `prepared` marca um briefing manual pronto (comando `prepare --job N`) e nunca substitui uma aprovação em `waiting_approval`. O modo padrão é `manual`: gera tarefas e templates verificáveis; a próxima etapa avança sobre predecessores `done` ou `prepared` e bloqueia em `waiting_approval`, `failed`, `rejected`, `running` e `awaiting_integration`. No modo produção apenas `done` libera etapas seguintes. Para execução real via Hermes é preciso definir uma CLI testada em `config/settings.json` (ver `docs/INTEGRACOES.md`). Jobs de render, download e publicação não são executados sem aprovação. **Publicação não é implementada nesta versão.**

Os seis papéis são Scout (pesquisa), Maester (roteiro e lore), Artist (imagens), Editor (montagem), Inspector (QA), Engineer (diagnóstico). O pipeline gera uma sequência inicial desses seis papéis. Resultados não verificados são marcados como pendentes de pesquisa/validação.

## Privacidade e direitos

Não salve tokens no `settings.json`; use variáveis de ambiente para futuras integrações. Referências de trechos de séries são registradas com URL, origem e contexto. O sistema não baixa vídeos protegidos nem contorna DRM. Trechos de terceiros podem causar reivindicações ou bloqueios de direitos autorais, mesmo com narração original.

## Estrutura

- `main.py`: CLI
- `ironarchive/`: fila, persistência, agentes e diagnósticos
- `agents/`: instruções dos seis papéis
- `config/settings.json`: configuração inicial
- `data/`: SQLite criado ao executar
- `projects/`: episódios gerados
- `docs/`: arquitetura, integrações, migração e limitações
- `tests/`: testes automatizados

## Centro de Comando (interface web local)

`python ironarchive/command_center.py` inicia um servidor web leve (apenas a biblioteca padrao do Python) que escuta exclusivamente em `127.0.0.1` (porta `8765`; mude com a variavel de ambiente `CC_PORT`). Nao instala dependencias, nao expoe servicos na rede e nao usa APIs pagas nem tokens no front-end.

Exibe o estado real da fila SQLite: episodios, jobs dos seis papeis (Scout, Maester, Artist, Editor, Inspector, Engineer) com estados e tentativas, arquivos de saida em `projects/<slug>/outputs` e o log de eventos. Permite apenas acoes compatíveis com o modelo de estados: aprovar/rejeitar jobs em `aguardando_aprovacao` e preparar manualmente jobs `pendentes`. `Executar proxima etapa` roda `run_one()` de verdade — nunca marca uma producao como concluída sem executar o pipeline real.

A interface é escura, cinematica e medieval (carvao, ouro envelhecido e bronze), responsiva, com icones SVG inline e fontes do sistema, sem assets externos. Está integrada ao `INICIAR.bat` (opcao 7). Os endpoints REST em `/api/*` ficam disponíveis para integracao futura.

**Importante:** esta é uma fundação funcional e testada localmente, não um editor de vídeo completo nem uma correção comprovada do Hermes instalado na sua máquina.
