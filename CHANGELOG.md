# Changelog

Todas as mudanças relevantes do Nexus Agent devem ser registradas aqui.

O formato segue a ideia de:
- `Added` para novidades
- `Changed` para mudanças de comportamento
- `Fixed` para correções de bugs
- `Removed` para remoções

## [Unreleased]

## [26.4.6] - 2026-04-18

### Added
- Parser de fallback para executar comando shell simples quando a IA devolver apenas uma linha segura como `gh auth status` ou `git status`, mesmo sem JSON de tool-call.
- Testes cobrindo extracao de comando textual puro e rejeicao de texto narrativo longo.

### Changed
- O plain CLI e a UI visual agora tentam executar automaticamente respostas de comando puro da IA antes de tratar a resposta como texto comum.

### Fixed
- Corrigido o caso em que a IA devolvia um comando curto valido, mas o Nexus apenas mostrava a resposta em vez de executar.

## [26.4.5] - 2026-04-18

### Added
- Testes cobrindo comandos read-only do GitHub CLI, incluindo `gh repo view`, `gh pr status`, `gh pr checks`, `gh issue list` e `gh run list`.

### Changed
- O classificador de seguranca agora reconhece mais subcomandos read-only do `gh` e permite diagnostico do repositório/projeto sem pedir confirmacao desnecessaria.

### Fixed
- Corrigido o caso em que consultas seguras do GitHub CLI ainda caiam em `Luz Amarela`, atrasando fluxos como inspecionar PRs, issues, runs e status do repositório.

## [26.4.4] - 2026-04-16

### Added
- Atalho local para abrir browser/app direto a partir de prompts como `abre o chrome`, `open firefox` e variações equivalentes, sem depender do LLM gerar tool-calls corretas.
- Testes cobrindo detecção de browser direto, launcher visual local e tolerância a argumentos de ferramentas em formatos JSON/Python dict.

### Changed
- O modo plain e a UI visual agora tratam comandos shell puros e pedidos simples de abrir navegador como execução direta no host antes de cair no fluxo conversacional/planner.
- O executor de comandos passou a transmitir eventos de `stdout`/`stderr` durante a execução, melhorando o feedback em estilo terminal.
- A whitelist de comandos foi ampliada para fluxos comuns de desenvolvimento, incluindo `gh`, `npm`, `pnpm`, `yarn`, `node`, `go`, `cargo`, `bun` e `make`.

### Fixed
- Corrigido o bug em que pedidos como `abre o chrome` podiam ficar presos em raciocínio excessivo ou em tool-call inválida em vez de abrir/focar o navegador real.
- Corrigido o erro de parse quando o modelo devolvia argumentos de ferramenta com JSON malformado; o bridge agora tenta recuperar com fallback seguro antes de falhar.
- Corrigido o caso de `gh auth status`, que agora pode rodar como comando direto read-only sem ser barrado indevidamente.

## [26.4.3] - 2026-04-16

### Added
- Tool `inspecionar_sistema` com snapshot do host, comandos de controle disponíveis, browsers detectados e navegador padrão.
- Suporte bilíngue PT-BR/EN com preferência configurável por `response_language` e comandos `/language auto|pt|en`.
- Testes para resposta local imediata em smalltalk e para validar que o `install.sh` não imprime mais sequências ANSI cruas na mensagem final.

### Changed
- O runtime agora injeta contexto do host no prompt do agente, incluindo SO detectado, comandos de controle e navegador padrão.
- Conversas comuns sem intenção de execução passaram a usar resposta direta, sem tool-calls e com limite menor de tokens.
- Sessões privilegiadas passaram a reconhecer mais comandos de controle do sistema em Linux, macOS e Windows.

### Fixed
- Corrigida a mensagem final do `install.sh`, que mostrava `\033[...]` literal em vez de aplicar cor nos comandos destacados.
- Corrigido o comportamento do agente para não tratar saudações e conversa simples como tarefas longas com planejamento desnecessário.

## [26.4.2] - 2026-04-15

### Added
- Teste `tests/test_install_script.py` para cobrir o fallback do `install.sh` quando `apt-get update` falha por repositório de terceiro e o Python precisa do pacote versionado `python3.x-venv`.

### Changed
- O `install.sh` agora detecta o pacote `python3.x-venv` correspondente ao Python em uso e tenta instalar apenas com repositórios oficiais do sistema quando um PPA/repositório externo quebra o `apt update`.
- A mensagem de erro do clone passou a orientar autenticação local do `git`/`gh`, em vez de sugerir token embutido na URL.

### Fixed
- Corrigida a instalação automática em Ubuntu/Zorin quando `python3-venv` sozinho não basta e o ambiente precisa de `python3.10-venv` ou equivalente.
- Corrigida a instalação em máquinas com repositório de terceiros quebrado, como o caso de chave GPG ausente do Brave, sem exigir mexer no projeto manualmente.

## [26.4.1] - 2026-04-15

### Added
- Teste `tests/test_local_runtime_config.py` para cobrir runtime local, placeholder de API key e normalizacao de modelo no Ollama.

### Changed
- O `README.md` foi reescrito para focar em visao geral do projeto, instalacao, configuracao e uso.
- O fluxo de correcao voltou a registrar release de bugfix com versao e entrada propria no `CHANGELOG.md`.

### Fixed
- Corrigida a configuracao de runtime local/OpenAI-compatible para nao falhar quando o endpoint e localhost sem API key real.
- Corrigida a configuracao do provider `Ollama`, com `base_url` padrao e normalizacao de modelo para chamadas via LiteLLM.
- Corrigida a inicializacao do setup plain e da CLI plain quando `rich` ainda nao esta instalado no ambiente.
- Corrigido o instalador para tentar caminhos de fallback melhores e exibir log util quando a instalacao de dependencias falha.

## [26.4.0] - 2026-04-11

### Added
- Blocos `Updated Plan`, eventos de pensamento/ação e resumo curto de saída logo abaixo de `Ran ...`.
- Checagem de atualização em background com cache local e aviso para usar `nexus update` quando houver versão mais nova.
- Testes para transcript estruturado e para o checker de atualização.

### Changed
- A UI visual e o modo plain ficaram mais próximos do estilo Codex/Claude Code ao mostrar progresso, plano e resultados.
- O logger de execução agora resume `stdout` e `stderr` de comandos em vez de só sinalizar que o comando terminou.

## [26.3.1] - 2026-04-11

### Added
- Formatação de transcript estilo agente de terminal para logs e passos de execução.
- Banner `Worked for ...`, linhas `• Ran ...` e bloco `↳ Interacted with background terminal` em fluxos compatíveis.
- Testes para o formatador de transcript e o novo estilo de interação.

### Changed
- A UI visual e o modo plain agora narram melhor o progresso, os comandos executados e o fechamento de cada tarefa.
- O prompt do agente ficou mais curto e operacional, mais próximo de Codex/Claude Code.

## [26.3.0] - 2026-04-11

### Added
- Tela inicial com splash/loading e seletor de perfil `Dia a dia` vs `Profissional` antes de entrar no chat visual.
- Sessão temporária de `sudo`/`root` com timeout, confirmação dupla no `root`, escopo limitado por executável e log opcional.
- Testes cobrindo fluxo do launcher visual, perfil rápido e exigência de sessão privilegiada para comandos elevados.

### Changed
- O perfil `Dia a dia` agora reduz o planejamento para tarefas simples de mouse, teclado, abrir app e ações diretas.
- O perfil `Profissional` mantém o fluxo completo com preview de plano, mais rodadas e execução mais cuidadosa.
- A UI visual e o modo plain agora expõem comandos `/profile`, `/sudo` e `/root`.

### Fixed
- O Nexus não força mais um fluxo de 6 passos em pedidos simples quando a sessão está em modo rápido.
- Comandos privilegiados agora falham de forma explícita quando a sessão `sudo/root` não foi ativada pelo usuário.

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
