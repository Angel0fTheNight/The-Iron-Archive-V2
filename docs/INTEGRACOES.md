# Integrações — configuração, não suposições

## Hermes

A CLI está instalada segundo a auditoria, mas o erro `No module named 'tools.delegation_output_schema'` em `delegate_task` já ocorreu. Não dependemos da delegação nativa. Em `config/settings.json`, o modo padrão é `manual`. Para testar execução real, defina `execution_mode` como `hermes`, `hermes.enabled` como `true` e `hermes.args_template` como **lista de argumentos efetivamente testada** que aceite `{prompt_file}`. Exemplo ilustrativo apenas (NÃO usar sem conferir): `['ALGUM_SUBCOMANDO','{prompt_file}']`. O Python executa o processo sem shell, com timeout e captura de erros.

## ComfyUI

Caminho conhecido da auditoria: `D:\TheIronArchive\AIModels\ComfyUI`. Configure `comfyui.enabled=true` apenas quando o serviço estiver em execução; `doctor` consulta `/system_stats` local. Ainda não há submissão automática de workflows. O workflow de UI pode não ser compatível com a API; validar nós, modelos e formato antes de criar adaptador de render.

## FFmpeg

Detectado no PATH pela auditoria (9.0.2). Pode ser usado futuramente por `subprocess.run` com argumentos explícitos. Esta versão não monta vídeos automaticamente sem mídias de entrada reais.

## Kokoro / legendas

Há narração produzida anteriormente, mas o inventário não comprovou um comando global Kokoro funcional. Antes de integrar, localizar o ambiente usado no episódio piloto. Não duplicar instalações.

## YouTube

Publicação não implementada; futura integração OAuth com revisão humana obrigatória.
