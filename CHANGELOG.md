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
