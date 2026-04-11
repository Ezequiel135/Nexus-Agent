# NEXUS AGENT 26.3.1

<div align="center">

**Agente de Autonomia Local para Terminal**

Inspirado no fluxo de trabalho do Codex e Claude Code — mas com cérebro de verdade.

[![GitHub](https://img.shields.io/badge/GitHub-Ezequiel135-blue?logo=github)](https://github.com/Ezequiel135/Nexus-Agent)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**Criado por Ezequiel 135**

</div>

---

## 📑 Índice

- [O que é](#o-que-é)
- [Resumo Rápido](#resumo-rápido)
- [Por que usar](#por-que-usar)
- [Recursos](#recursos)
- [MCP](#mcp)
- [Notebook + Bots Remotos](#notebook--bots-remotos)
- [Arquitetura](#arquitetura)
- [Instalação](#instalação)
- [Atualização](#atualização)
- [Uso](#uso)
- [Ferramentas](#ferramentas)
- [Modo Missão](#modo-missão)
- [Segurança](#segurança)
- [Comandos Principais](#comandos-principais)
- [Arquivos do Usuário](#arquivos-do-usuário)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Sistema de Versionamento](#sistema-de-versionamento-calver)
- [Changelog](#changelog)
- [Contribuindo](#contribuindo)
- [Licença](#licença)

---

## O que é

O **NEXUS AGENT** é um agente de autonomia local que roda no terminal, conversa com você em linguagem natural e executa tarefas reais no seu computador — com shell, arquivos, mouse, teclado e visão de tela.

Diferente de assistentes que só respondem, o Nexus **planeja, age e reporta**. Ele transforma objetivos complexos ("organiza minha pasta de downloads") em planos detalhados e executa cada passo autonomamente.

---

## Resumo Rápido

- **Objetivo:** executar tarefas reais no computador a partir de linguagem natural.
- **Interface:** modo visual com Textual e modo plain orientado a terminal.
- **Capacidades:** shell, arquivos, OCR, mouse, teclado, memória, MCP, notebooks e bots remotos.
- **Escala:** múltiplas contas, múltiplos agentes e execução paralela.
- **Segurança:** comandos avaliados por Luz Verde antes da execução.
- **Versão atual:** `26.3.1`, com versionamento CalVer.
- **Histórico de mudanças:** veja `CHANGELOG.md` para correções e melhorias recentes.

### Quick Start

```bash
git clone https://github.com/Ezequiel135/Nexus-Agent.git
cd Nexus-Agent
chmod +x install.sh nexus
./install.sh
nexus
```

### Destaques da 26.3.1

- Tela inicial com loading real e seletor visual entre `Dia a dia` e `Profissional`.
- Modo `Dia a dia` reduz o excesso de planejamento em tarefas simples; `Profissional` mantém o fluxo completo.
- Sessão temporária de `sudo/root` com timeout, confirmação dupla em `root`, escopo limitado e log opcional.
- Transcript mais parecido com Codex/Claude Code, com passos curtos, `Ran ...`, `Worked for ...` e interação de terminal em segundo plano.
- Runtime `online`, `hybrid` e `offline`, com comandos slash funcionando sem depender de API remota.

---

## Por que usar

| 💬 Assistentes comuns | 🤖 Nexus Agent |
|----------------------|----------------|
| Respondem perguntas | Executam tarefas reais |
| Dependem de prompts perfeitos | Decompõem objetivos automaticamente |
| Sem memória persistente | Memorizam preferências e contexto |
| Sem segurança embutida | Luz Verde em tempo real (🟢🟡🔴) |
| Apenas texto | Shell + Arquivos + Mouse + Teclado + OCR |

---

## Recursos

### 🧠 Cérebro de Verdade — Planner/Executor Real
O agente não é mais um mock. Ele gera um plano JSON com subtarefas, decidi qual ferramenta usar em cada passo e executa em loop até terminar.

### 🛠️ Tool Registry Dinâmico
Sistema de ferramentas plugável com auto-registro. Fácil estender e integrar com LangChain, CrewAI ou OpenAI Tools.

### 🟢 Luz Verde Real
Sandbox de segurança integrado em cada comando:
- 🟢 **Verde** — seguro (diretórios permitidos: `~`, `~/.nexus`, `/tmp`, cwd)
- 🟡 **Amarelo** — atenção (ex: `rm -r`, `dd`, `mkfs`)
- 🔴 **Vermelha** — bloqueado (ex: `rm -rf /`, `shutdown`, `mkfs`)

### 🎯 Modo Missão
Para tarefas com +4 palavras ou palavras-chave ("organizar", "criar", "instalar"), o agente ativa automaticamente o Modo Missão:
1. Mostra o plano completo antes de executar
2. Espera aprovação explícita com `/approve` quando necessário
3. Executa cada passo com logs, dry-run e cancelamento
4. Salva a missão na memória local

### 📡 Installer Viral
Instalador multiplataforma que funciona de primeira:
- Detecção automática de OS (Linux/macOS)
- Fallback Python: `python3` → `python` → `python3.10-12`
- Primeira abertura já entra em setup e deixa escolher entre UI Visual ou Terminal Plain
- Setup agora aceita várias contas e vários agentes nomeados
- Cores no terminal, barra de progresso
- PATH auto-configurado em `~/.bashrc` e `~/.zshrc`
- Suporte a instalação global (`NEXUS_INSTALL_GLOBAL=1`)

### 🔁 Retry Automático de API
- Quando a API responde com erro de cota/rate limit, o Nexus tenta novamente até **10 vezes**
- O backoff é progressivo: **10s, 20s, 30s...**
- Erros de chave inválida ou modelo inválido continuam falhando imediatamente, sem retry cego

### 🌐 Browser Explícito
As ações de navegador não usam mais o navegador padrão nem Brave. O agente abre URLs apenas em browsers suportados detectados explicitamente: `Chrome`, `Chromium`, `Firefox` ou `Edge`.
Se quiser forçar um navegador específico, defina `NEXUS_BROWSER=chrome`, `chromium`, `firefox` ou `edge`.

### 👥 Contas e Agentes
- Dá para ter várias contas com chaves de API diferentes e alternar entre elas com `nexus login` e `nexus logout`
- Dá para ter vários agentes nomeados, cada um preso a uma conta, com instruções extras próprias
- O setup aceita `Outro / Custom` para providers com `Nome/ID do provider`, `Base URL / Endpoint` e `API Key` em campos separados
- O setup agora mostra um aviso acima de cada caixa dizendo exatamente onde colocar `Nome do provider`, `Base URL` e `API Key`

### ⚡ Agentes Múltiplos em Paralelo
- O comando `nexus parallel run` executa a mesma tarefa em vários agentes ao mesmo tempo
- Dá para escolher `--mode chat` para resposta completa ou `--mode plan` para gerar planos paralelos
- Cada agente roda com a conta e instrução próprias, facilitando comparação entre perfis
- O prompt principal da UI agora abre com foco no campo de escrita, sem travar a digitação

### 📓 Notebooks Jupyter
- Criação e leitura de notebooks `.ipynb` direto pelo CLI
- Adição de células de código ou markdown
- Execução local via kernel `python3` com persistência do notebook atualizado
- Ferramenta nativa `gerenciar_notebooks` para o agente operar notebooks automaticamente

## MCP

Na linha `26.3.1`, o NEXUS AGENT suporta **MCP (Model Context Protocol)** via `stdio`.

### MCP na versão 26.3.1

- Cadastro de servidores MCP no `config.json`
- Comandos CLI para adicionar, listar, ler recursos e remover servidores MCP
- Ferramenta nativa `consultar_mcp` para o agente buscar contexto via MCP

### Comandos MCP

```bash
# Lista servidores MCP cadastrados
nexus mcp list

# Adiciona um servidor MCP
nexus mcp add --name filesystem --command "npx -y @modelcontextprotocol/server-filesystem ~/projeto"

# Lista recursos publicados pelo servidor
nexus mcp resources filesystem

# Lê um recurso MCP
nexus mcp read filesystem "file:///home/user/projeto/README.md"

# Lista tools publicadas pelo servidor
nexus mcp tools filesystem

# Remove o servidor
nexus mcp remove filesystem
```

## Notebook + Bots Remotos

A versão `26.3.1` mantém **Notebook integration (Jupyter)**, **automação remota por bots** e **agentes múltiplos em paralelo**, agora com runtime offline/hybrid, aprovação manual de plano e endurecimento forte de segurança.

### O que entra na 26.3.1

- UI inicial de configuração refeita do zero, com layout responsivo, rolagem e foco correto
- Campos de texto e navegação do setup ajustados para evitar travamentos
- Comandos CLI para criar, listar, ler, editar e executar notebooks `.ipynb`
- Diretório padrão `~/.nexus/notebooks` para armazenar notebooks do agente
- Ferramenta `gerenciar_notebooks` exposta ao LLM
- Integração remota com **Telegram Bot API** via polling
- Integração remota com **WhatsApp Cloud API** via webhook
- Modo remoto com trava global `arm/disarm`
- Allowlist de remetentes autorizados e prefixo obrigatório por integração
- Execução paralela de vários agentes via `nexus parallel run`

## Changelog

O histórico consolidado de correções, melhorias e mudanças notáveis agora fica em `CHANGELOG.md`.

### Comandos de Notebook

```bash
nexus notebook list
nexus notebook create demos/analise --title "Análise inicial"
nexus notebook add-cell demos/analise --type code --content "print('hello')"
nexus notebook read demos/analise
nexus notebook run demos/analise --timeout 300
```

### Comandos de Bots Remotos

```bash
# Telegram
nexus remote add-telegram --name tg-pessoal --bot-token "TOKEN" --allow 123456789 --prefix "!nexus"

# WhatsApp Cloud API
nexus remote add-whatsapp --name wa-pessoal --access-token "TOKEN" --phone-number-id "ID" --verify-token "SEGREDO" --allow 5511999999999

# Segurança do modo remoto
nexus remote list
nexus remote arm
nexus remote start tg-pessoal
nexus remote disarm
```

### Observações Importantes

- O modo remoto fica **desarmado por padrão**
- O Nexus só executa mensagens vindas de remetentes da allowlist
- Cada integração exige um prefixo, como `!nexus abrir o VS Code`
- No WhatsApp, o webhook precisa estar exposto publicamente em HTTP(S), por exemplo com reverse proxy ou túnel
- A disponibilidade final no WhatsApp depende também da conta e das regras da plataforma Meta

---

## Arquitetura

```
NEXUS AGENT 26.3.1
├── core/
│   ├── llm.py           # LiteLLMBridge + PlannerExecutor
│   ├── actions.py       # AcoesAgente (ToolRegistry)
│   ├── mcp.py           # Cliente MCP via stdio
│   ├── notebooks.py     # Integração Jupyter / .ipynb
│   ├── remote.py        # Telegram + WhatsApp remotos
│   ├── tool_registry.py # Sistema dinâmico de ferramentas
│   ├── safeguards.py    # Luz Verde (segurança)
│   ├── memory.py        # Memória local persistente
│   ├── config.py        # Configuração e caminhos
│   ├── state.py         # Monitor de atividade
│   └── logging_utils.py # Logs estruturados
├── ui/
│   ├── app.py           # Interface Textual (modo UI)
│   ├── plain_cli.py     # Terminal puro (modo Codex)
│   └── setup_cli.py     # Setup via CLI
├── pc_remote_agent/     # Automação local (pyautogui + OCR)
├── main.py              # Entry point do comando `nexus`
├── install.sh           # Instalador Linux/macOS
└── requirements.txt     # Dependências Python
```

### Fluxo de Execução

```
Usuário → Objetivo → PlannerExecutor → Plano JSON
         ↓
    Loop por passo:
      - Verifica Luz Verde
      - Dispara ferramenta via ToolRegistry
      - Log + Memória
         ↓
    Missão concluída → Resumo no chat
```

---

## Instalação

### Requisitos

- **Python 3.10+**
- **Git** (para clone do repositório)
- **Linux/macOS** (Windows via WSL ou PowerShell script)

### Opção 1: Installer Viral (recomendado)

Importante: depois do clone, o comando global `nexus` só deve ser usado depois de executar `./install.sh`.
Se você rodar `nexus start` antes disso, pode acabar abrindo outro launcher antigo já instalado no sistema.

```bash
# Clone o repositório
git clone https://github.com/Ezequiel135/Nexus-Agent.git
cd Nexus-Agent

# Execute o instalador
chmod +x install.sh nexus
./install.sh

# Abra um NOVO terminal e rode:
nexus
```

**One-liner via curl:**

```bash
curl -fsSL https://raw.githubusercontent.com/Ezequiel135/Nexus-Agent/main/install.sh | bash
nexus
```

### Opção 2: Instalação Manual

```bash
# Clone
git clone https://github.com/Ezequiel135/Nexus-Agent.git
cd Nexus-Agent

# Crie venv
python3 -m venv .venv
source .venv/bin/activate

# Instale dependências
pip install -r requirements.txt

# Configure
python main.py setup

# Rode direto do repositório, sem depender do comando global
./nexus start

# Ou rode via Python
python main.py start
```

### Opção 3: Windows Terminal / PowerShell

```powershell
# Clone
git clone https://github.com/Ezequiel135/Nexus-Agent.git
cd Nexus-Agent

# Execute o instalador PowerShell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1

# Modo plain (recomendado no Windows)
nexus start --plain
```

---

## Atualização

O NEXUS AGENT inclui um fluxo de atualização pensado para instalações feitas pelo próprio projeto.

### Atualização recomendada

```bash
nexus update
```

Esse comando:

- sincroniza o código da instalação com o branch `main`
- usa a URL salva em `~/.nexus/repo.txt`
- tenta reinstalar dependências do ambiente virtual local do Nexus

### Atualização manual do clone local

Se você estiver executando direto do repositório:

```bash
git pull origin main
python3 -m pip install -r requirements.txt
```

### Atualização manual da instalação em `~/.nexus`

```bash
git -C ~/.nexus/src pull origin main
~/.nexus/env/bin/python -m pip install -r ~/.nexus/src/requirements.txt
```

### Verificação pós-update

```bash
nexus doctor
type -a nexus
```

Use `type -a nexus` para confirmar que o shell está chamando o launcher correto, principalmente se você já teve outro projeto usando o mesmo nome.

---

## Uso

### Primeiro Acesso

Na primeira execução, o Nexus entra em **modo setup** e pede:

1. **Tipo de UI** — `Visual` ou `Terminal puro`
2. **Nome da conta** — para separar chaves e logins
3. **Provider** — OpenAI, Anthropic, Google, Ollama, Groq ou `Outro / Custom`
4. **API Key** — sua chave do provedor
5. **Model Name** — ex: `gpt-4o-mini`, `claude-3-5-sonnet`, `llama3`
6. **Nome/ID do provider custom** — quando escolher `Outro / Custom`, em caixa própria
7. **Base URL / Endpoint** — em caixa própria, separada da API Key
8. **Nome do agente inicial** — primeiro agente da conta
9. **Instrução extra do agente** — opcional
10. **Senha Mestra** — protege o modo autônomo

A configuração é salva em `~/.nexus/config.json`.

### Iniciar

```bash
# Início padrão (abre visual ou plain conforme sua preferência salva)
nexus

# Modo UI completo (se a UI visual estiver disponível)
nexus start

# Modo terminal puro (estilo Codex/Claude Code)
nexus start --plain

# Com tarefa inicial
nexus start --task "Organize minha pasta Downloads por tipo"

# Após instalação, recarregue o terminal
source ~/.bashrc
```

### Dentro do Nexus

**Modo UI:** digite objetivos em linguagem natural no campo de input.

**Modo Plain:**
```
nexus> Organize meus arquivos baixados separando PDFs, imagens e documentos

# O agente planeja e executa automaticamente
[PLANO CONCLUIDO]
  Passo 1: Ler diretório ~/Downloads...
  Passo 2: Classificar arquivos...
  Passo 3: Criar pastas...
  Passo 4: Mover arquivos...
  Passo 5: Gerar resumo...
```

### Comandos Internos (Modo Plain)

| Comando | Descrição |
|--------|-----------|
| `/help` | Mostra ajuda |
| `/init` / `/onboarding` | Tour guiado |
| `/status` | Status do agente |
| `/accounts` | Lista contas configuradas |
| `/agents` | Lista agentes configurados |
| `/mcp` | Lista servidores MCP |
| `/notebooks` | Lista notebooks Jupyter |
| `/remote` | Lista integrações remotas |
| `/tools` | Lista ferramentas disponíveis |
| `/memory` | Mostra memória local |
| `/remember texto` | Salva memória manual |
| `/forget-all` | Apaga toda memória |
| `/blocked` | Comandos bloqueados |
| `/clear` | Limpa tela |
| `/exit` | Sai |

---

## Ferramentas

Todas as ferramentas são **chamadas automaticamente** pelo LLM com base no contexto:

| Ferramenta | Descrição | Parâmetros |
|------------|-----------|------------|
| `executar_comando` | Executa shell | `comando: str` |
| `gerenciar_arquivos` | CRUD de arquivos | `acao: ler\|escrever\|listar\|mover\|deletar`, `path: str`, `content?, target_path?` |
| `controle_periferico` | Mouse/teclado/OCR | `acao: clicar\|digitar\|mover_mouse\|screenshot\|posicao_cursor`, `x?, y?, texto?` |
| `memoria_local` | Memória persistente | `acao: salvar\|buscar\|limpar`, `texto?, consulta?` |
| `verificar_pixel` | Lê cor RGB da tela | `x: int`, `y: int` |
| `consultar_mcp` | Consulta servidores MCP | `acao, servidor?, uri?, ferramenta?, argumentos?` |
| `gerenciar_notebooks` | Opera notebooks Jupyter | `acao, path?, content?, title?, kernel_name?, timeout?, cwd?` |

### Exemplos de Uso

```bash
# Shell
nexus> ls -la ~/Downloads

# Arquivos
nexus> Crie um arquivo notes.txt com "comprar leite"

# Memória
nexus> Lembre que meu modelo favorito é gpt-4o

# Mouse/Teclado
nexus> Clique no botão Aceito na tela
```

---

## Modo Missão

Ativado automaticamente para objetivos complexos. O Nexus:

1. **Planeja** — decompõe em subtarefas
2. **Mostra** — exibe o plano completo antes de executar
3. **Executa** — roda cada passo com verificação de segurança
4. **Reporta** — log de cada ação e resumo final

### Exemplo

```
Você: Organiza minha pasta downloads

📋 PLANO:
1. Ler diretório ~/Downloads
2. Classificar arquivos por extensão
3. Criar pastas: PDFs, Imagens, Documentos, etc.
4. Mover arquivos para pastas correspondentes
5. Gerar resumo das operações

🚀 EXECUTANDO 5 PASSOS...
[✓] PASSO 1/5: Ler diretório ~/Downloads...
[✓] PASSO 2/5: Classificar 47 arquivos...
[✓] PASSO 3/5: Criar 6 pastas...
[✓] PASSO 4/5: Mover arquivos...
[✓] PASSO 5/5: Gerar resumo...

✅ Missão concluída — 47 arquivos organizados em 6 pastas
```

---

## Segurança

### Luz Verde em Tempo Real

Cada comando é verificado antes de executar:

🟢 **Verde** — Seguro. Executa imediatamente.
🟡 **Amarelo** — Atenção. Pode alterar sistema (ex: `apt install`).
🔴 **Vermelha** — Bloqueado. Risco de dano.

### Comandos Bloqueados

- `rm -rf /` — remoção total da raiz
- `mkfs`, `fdisk`, `parted` — formatação/particionamento
- `dd of=/dev/` — escrita direta em dispositivo
- `shutdown`, `reboot`, `poweroff` — desligamento
- `flashrom`, `efibootmgr` — firmware/EFI
- Acesso a `/boot`, `/efi`, `/etc` críticos

Visualize a lista completa:

```bash
nexus blocked
```

### Zonas Seguras

Comandos são permitidos dentro de:
- `~` (sua home)
- `~/.nexus` (dados do Nexus)
- `/tmp`, `/var/tmp` (temp)
- Diretório atual de trabalho (`pwd`)

### Segurança do Modo Remoto

- `nexus remote arm` libera a automação remota explicitamente
- `nexus remote disarm` corta a execução remota imediatamente
- Telegram e WhatsApp usam allowlist de IDs/números autorizados
- Mensagens sem o prefixo configurado são ignoradas
- O listener remoto também exige a senha mestra ao iniciar

---

## Comandos Principais

```bash
# Setup inicial
nexus setup                    # Recria a configuracao inicial completa

# Contas
nexus accounts                 # Lista contas configuradas
nexus login                    # Adiciona nova conta e ativa
nexus login --account "Conta"  # Troca para uma conta existente
nexus logout                   # Desativa a conta atual

# Agentes
nexus agents                   # Lista agentes configurados
nexus add-agent                # Cria um novo agente
nexus add-agent --account "Conta"  # Cria agente preso a uma conta especifica
nexus use-agent "Agente"       # Ativa um agente existente

# Agentes em paralelo
nexus parallel list
nexus parallel run --task "Comparar estrategia de deploy" --agent "Agente principal" --agent "Revisor" --mode plan
nexus parallel run --task "Responder ao cliente com resumo tecnico" --mode chat

# MCP
nexus mcp list                 # Lista servidores MCP
nexus mcp add --name srv --command "comando"
nexus mcp resources srv        # Lista recursos do servidor
nexus mcp read srv "uri"       # Le recurso MCP
nexus mcp tools srv            # Lista tools do servidor
nexus mcp remove srv           # Remove servidor MCP

# Notebooks Jupyter
nexus notebook list
nexus notebook create demo/analise --title "Analise"
nexus notebook add-cell demo/analise --type code --content "print('oi')"
nexus notebook read demo/analise
nexus notebook run demo/analise --timeout 300

# Bots remotos
nexus remote list
nexus remote add-telegram --name tg --bot-token "TOKEN" --allow 123456789
nexus remote add-whatsapp --name wa --access-token "TOKEN" --phone-number-id "ID" --verify-token "SEGREDO" --allow 5511999999999
nexus remote arm
nexus remote start tg
nexus remote disarm
nexus remote remove tg

# Ajuda e diagnóstico
nexus --help                   # Ajuda do CLI
nexus onboarding               # Tour guiado
nexus blocked                  # Lista comandos bloqueados
nexus doctor                   # Diagnóstico do sistema

# Execução
nexus start                    # Inicia modo UI
nexus start --plain            # Inicia modo terminal puro
nexus start --task "objetivo"  # Executa tarefa inicial

# Manutenção
nexus update                   # Atualiza a instalação Nexus via git + pip
nexus uninstall                # Remove instalação local
```

---

## Arquivos do Usuário

O Nexus armazena tudo em `~/.nexus/`:

| Arquivo | Descrição |
|---------|-----------|
| `config.json` | Contas, agentes, provider ativo, model, senha, MCP e integrações remotas |
| `history.json` | Histórico recente da conversa (últimas 24 mensagens) |
| `memory.json` | Memória local persistente (até 200 itens) |
| `activity.json` | Estado atual do agente |
| `nexus.log` | Logs detalhados de ações |
| `repo.txt` | URL do repositório usada na instalação |
| `notebooks/` | Notebooks `.ipynb` criados pelo Nexus |

---

## Estrutura do Projeto

```text
Nexus-Agent/
├── main.py                        # CLI principal
├── nexus                          # Launcher local
├── install.sh                     # Instalador Linux/macOS
├── install.ps1                    # Instalador Windows
├── pyproject.toml                 # Metadados e versão CalVer
├── requirements.txt               # Dependências Python
├── README.md
├── core/
│   ├── llm.py                     # LiteLLM + PlannerExecutor
│   ├── actions.py                 # AcoesAgente (ToolRegistry)
│   ├── parallel.py                # Execução paralela de agentes
│   ├── version.py                 # Helpers de versão e CalVer
│   ├── mcp.py                     # Cliente MCP
│   ├── notebooks.py               # Integração Jupyter
│   ├── remote.py                  # Bots remotos
│   ├── tool_registry.py           # Sistema de ferramentas
│   ├── safeguards.py              # Segurança (Luz Verde)
│   ├── memory.py                  # Memória local
│   ├── config.py                  # Configuração
│   ├── state.py                   # Monitor de atividade
│   └── logging_utils.py           # Logging
├── ui/
│   ├── app.py                     # Interface visual com Textual
│   ├── plain_cli.py               # Interface terminal pura
│   └── setup_cli.py               # Setup inicial
├── pc_remote_agent/               # Automação de GUI
└── tests/                         # Testes unitários
```

### Estrutura de runtime em `~/.nexus`

```text
~/.nexus/
├── config.json                    # Contas, agentes e preferências
├── history.json                   # Histórico recente
├── memory.json                    # Memória persistente
├── activity.json                  # Estado atual do agente
├── nexus.log                      # Logs de execução
├── repo.txt                       # URL usada pelo comando update
├── notebooks/                     # Notebooks criados pelo agente
└── src/                           # Clone usado pela instalação do Nexus
```

---

## Troubleshooting

### 1. `nexus` não é reconhecido como comando

**Causa:** PATH não recarregado após instalação.

**Solução:**
```bash
# Abra um novo terminal
source ~/.bashrc   # ou ~/.zshrc
nexus doctor
```

### 2. Apareceu `NEXUS COMPRESSOR` ou outro programa antigo ao rodar `nexus`

**Causa:** o shell está chamando outro arquivo, normalmente `/usr/local/bin/nexus`, e não o launcher deste repositório.

**Como confirmar:**
```bash
type -a nexus
```

Se aparecer `/usr/local/bin/nexus` com banner de outro projeto, você ainda não está executando o NEXUS AGENT deste repositório.

**Solução:**
```bash
# Dentro do clone, rode direto do projeto
cd Nexus-Agent
./nexus start

# Ou instale corretamente e recarregue o terminal
chmod +x install.sh nexus
./install.sh
source ~/.bashrc
type -a nexus
```

Se continuar apontando para um launcher antigo em `/usr/local/bin/nexus`, remova ou renomeie esse arquivo antigo antes de usar `nexus`.

### 3. `ERRO DE COMUNICACAO: VERIFIQUE SUA COTA`

**Causa:** API key inválida, cota esgotada ou modelo errado.

**Solução:**
```bash
nexus setup  # reconfigure
```

**Comportamento atual:**
- Se o problema for **cota/rate limit**, o Nexus faz até **10 tentativas**
- O tempo de espera cresce em **10s, 20s, 30s...**
- Se o problema for **chave inválida** ou **modelo incorreto**, a falha volta imediatamente para você corrigir

### 4. Interface não abre (textual não instalado)

**Solução:**
```bash
# Reinstale dependências
source ~/.nexus/env/bin/activate
pip install -r requirements.txt

# Ou use modo plain
nexus start --plain
```

### 5. Automação gráfica não funciona no Linux

**Causa:** Sem acesso ao DISPLAY ou em SSH sem X11 forwarding.

**Solução:**
```bash
# Verifique
nexus doctor

# Use modo plain em ambientes remotos
nexus start --plain
```

### 6. Como atualizar corretamente?

**Para instalações feitas com o Nexus:**

```bash
nexus update
nexus doctor
```

**Para uso direto no clone local:**

```bash
git pull origin main
python3 -m pip install -r requirements.txt
```

### 7. Como desinstalar?

```bash
nexus uninstall
# Remove ~/.nexus e ~/.local/bin/nexus
```

---

## Roadmap

- [x] v1.0 — UI Textual, ferramentas básicas, segurança
- [x] v2.0 — Planner/Executor, Tool Registry, Modo Missão, Luz Verde real
- [x] v2.1 — Suporte a MCP (Model Context Protocol)
- [x] v2.2 — Notebook integration (Jupyter) + bots remotos (Telegram/WhatsApp)
- [x] v3.0 — Agentes múltiplos em paralelo

---

## Sistema de Versionamento (CalVer)

Este projeto utiliza um sistema de versão baseado no calendário e progresso de desenvolvimento:
**Formato: `ANO . ATUALIZAÇÃO . BUGFIX`**

- **ANO:** Os dois últimos dígitos do ano atual (Ex: `26` para 2026).
- **ATUALIZAÇÃO:** Incrementado a cada nova funcionalidade ou melhoria implementada.
- **BUGFIX:** Incrementado quando o código recebe apenas correções de erros.

**Exemplos:**
- `26.1.0`: Primeira versão funcional de 2026.
- `26.1.1`: Correção de um erro na versão anterior.
- `27.1.0`: Primeira versão lançada em 2027.

---

## Contribuindo

```bash
git clone https://github.com/Ezequiel135/Nexus-Agent.git
cd Nexus-Agent

# Crie branch
git checkout -b feature/nome-da-feature

# Faça alterações, teste, commit
git commit -m "feat: descrição da mudança"

# Push e PR
git push origin feature/nome-da-feature
```

---

## Licença

MIT — use, modifique, compartilhe.

---

<div align="center">

**NEXUS AGENT** — autonomia local, cérebro de verdade.

Feito por Ezequiel 135 · [GitHub](https://github.com/Ezequiel135/Nexus-Agent)

</div>
