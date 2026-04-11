# Changelog

Todas as mudanças relevantes do Nexus Agent devem ser registradas aqui.

O formato segue a ideia de:
- `Added` para novidades
- `Changed` para mudanças de comportamento
- `Fixed` para correções de bugs
- `Removed` para remoções

## [Unreleased]

### Added
- Arquivo `CHANGELOG.md` para registrar releases, correções e melhorias do projeto.
- Teste `tests/test_nexus_ui.py` para garantir que a `NexusApp` monta corretamente.

### Changed
- Fluxo de primeira execução da CLI ficou mais profissional, com onboarding automático após o setup.
- O runtime do LLM agora faz retry automático em erro de cota/rate limit por até 10 tentativas.
- O backoff de retry da API agora é progressivo: 10s, 20s, 30s e assim por diante.
- O `README.md` foi atualizado para refletir as correções recentes e o comportamento de retry da API.

### Fixed
- Corrigidos os imports/bootstraps para executar `main.py` e `ui/setup_cli.py` fora da raiz do projeto.
- Corrigido o layout inicial da `SetupApp`, evitando campos vazios e renderização quebrada no primeiro load.
- Corrigido o CSS inválido da `NexusApp` que causava falha no parser do Textual.
- Corrigido o mount da `NexusApp` ao aceitar `id=` em `GreenLightBar`.

## [26.2.0] - 2026-04-10

### Added
- Runtime `online`, `hybrid` e `offline`, com suporte melhor para modelos locais via `Ollama`/`localhost`.
- Preview de plano com aprovação manual via `/approve`, cancelamento com `Esc` na UI visual e `/cancel` no terminal plain.
- Dry-run para ações destrutivas, backups automáticos antes de escrita/move/delete e auditoria em `~/.nexus/audit.jsonl`.
- Cache local de respostas do LLM e limites configuráveis de histórico, passos do planner e saída do modelo.
- Testes cobrindo bloqueio de comando malicioso, falhas de I/O, runtime offline e limites de execução.

### Changed
- O boot inicial ficou mais leve: o handshake remoto agora pode ser adiado para evitar travamento na primeira abertura.
- O planner foi separado da execução; a UI visual não executa mais o mesmo plano duas vezes.
- O shell local agora usa whitelist, bloqueia operadores complexos e evita `shell=True` para reduzir risco de perda de dados.
- Os slash commands passaram a funcionar localmente na UI visual e no modo plain sem depender de API remota.
- Setup visual/plain agora aceita `runtime_mode` e não exige API key quando o runtime/provedor é local.

### Fixed
- Corrigida a duplicação de execução no Modo Missão.
- Corrigida a exibição/foco inicial da `NexusApp`.
- Corrigido o fluxo do modo `plan` em agentes paralelos.
- Corrigidos logs com potencial de expor segredos; tokens passam por redação antes de ir para arquivo.

## [26.1.2] - 2026-04-10

### Added
- Suporte a MCP via `stdio`.
- Integração com notebooks Jupyter.
- Integrações remotas por Telegram e WhatsApp.
- Execução paralela de múltiplos agentes.

### Changed
- Setup inicial com UI visual e modo terminal plain.

### Fixed
- Ajustes gerais de setup, navegação e foco na UI inicial.
