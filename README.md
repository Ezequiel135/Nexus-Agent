# NEXUS AGENT v2.0

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
- [Por que usar](#por-que-usar)
- [Recursos](#recursos)
- [Arquitetura](#arquitetura)
- [Instalação](#instalação)
- [Uso](#uso)
- [Ferramentas](#ferramentas)
- [Modo Missão](#modo-missão)
- [Segurança](#segurança)
- [Comandos](#comandos)
- [Estrutura](#estrutura)
- [Troubleshooting](#troubleshooting)

---

## O que é

O **NEXUS AGENT** é um agente de autonomia local que roda no terminal, conversa com você em linguagem natural e executa tarefas reais no seu computador — com shell, arquivos, mouse, teclado e visão de tela.

Diferente de assistentes que só respondem, o Nexus **planeja, age e reporta**. Ele transforma objetivos complexos ("organiza minha pasta de downloads") em planos detalhados e executa cada passo autonomamente.

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
2. Executa cada passo com logs
3. Salva a missão na memória local

### 📡 Installer Viral
Instalador multiplataforma que funciona de primeira:
- Detecção automática de OS (Linux/macOS)
- Fallback Python: `python3` → `python` → `python3.10-12`
- Primeira abertura já entra em setup e deixa escolher entre UI Visual ou Terminal Plain
- Cores no terminal, barra de progresso
- PATH auto-configurado em `~/.bashrc` e `~/.zshrc`
- Suporte a instalação global (`NEXUS_INSTALL_GLOBAL=1`)

### 🌐 Browser Explícito
As ações de navegador não usam mais o navegador padrão nem Brave. O agente abre URLs apenas em browsers suportados detectados explicitamente: `Chrome`, `Chromium`, `Firefox` ou `Edge`.
Se quiser forçar um navegador específico, defina `NEXUS_BROWSER=chrome`, `chromium`, `firefox` ou `edge`.

---

## Arquitetura

```
NEXUS AGENT v2.0
├── core/
│   ├── llm.py           # LiteLLMBridge + PlannerExecutor
│   ├── actions.py       # AcoesAgente (ToolRegistry)
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

## Uso

### Primeiro Acesso

Na primeira execução, o Nexus entra em **modo setup** e pede:

1. **Tipo de UI** — `Visual` ou `Terminal puro`
2. **Provider** — OpenAI, Anthropic, Google, Ollama, Groq
3. **API Key** — sua chave do provedor
4. **Model Name** — ex: `gpt-4o-mini`, `claude-3-5-sonnet`, `llama3`
5. **Senha Mestra** — protege o modo autônomo

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

---

## Comandos Principais

```bash
# Setup inicial
nexus setup                    # Configura provider, API, modelo, senha

# Ajuda e diagnóstico
nexus help                     # Ajuda interativa
nexus onboarding               # Tour guiado
nexus blocked                  # Lista comandos bloqueados
nexus doctor                   # Diagnóstico do sistema

# Execução
nexus start                    # Inicia modo UI
nexus start --plain            # Inicia modo terminal puro
nexus start --task "objetivo"  # Executa tarefa inicial

# Manutenção
nexus update                   # Atualiza via git pull
nexus uninstall                # Remove instalação local
```

---

## Arquivos do Usuário

O Nexus armazena tudo em `~/.nexus/`:

| Arquivo | Descrição |
|---------|-----------|
| `config.json` | Provider, API key, model name |
| `history.json` | Histórico recente da conversa (últimas 24 mensagens) |
| `memory.json` | Memória local persistente (até 200 itens) |
| `activity.json` | Estado atual do agente |
| `nexus.log` | Logs detalhados de ações |
| `repo.txt` | URL do repositório (usado no `update`) |

---

## Estrutura do Projeto

```
Nexus-Agent/
├── src/
│   ├── main.py                    # CLI entry point (nexus)
│   ├── core/
│   │   ├── llm.py                 # LiteLLM + PlannerExecutor
│   │   ├── actions.py             # AcoesAgente (ToolRegistry)
│   │   ├── tool_registry.py       # Sistema de ferramentas
│   │   ├── safeguards.py          # Segurança (Luz Verde)
│   │   ├── memory.py              # Memória local
│   │   ├── config.py              # Configuração
│   │   ├── state.py               # Monitor de atividade
│   │   └── logging_utils.py       # Logging
│   ├── ui/
│   │   ├── app.py                 # Interface Textual (v2.0)
│   │   ├── plain_cli.py           # CLI puro
│   │   └── setup_cli.py           # Setup via terminal
│   ├── pc_remote_agent/           # Automação de GUI
│   ├── requirements.txt
│   └── install.sh                 # Instalador viral
└── README.md
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

### 5. Como atualizar?

```bash
nexus update
# ou manual:
git -C ~/.nexus/src pull origin main
source ~/.nexus/env/bin/activate
pip install -r ~/.nexus/src/requirements.txt
```

### 6. Como desinstalar?

```bash
nexus uninstall
# Remove ~/.nexus e ~/.local/bin/nexus
```

---

## Roadmap

- [x] v1.0 — UI Textual, ferramentas básicas, segurança
- [x] v2.0 — Planner/Executor, Tool Registry, Modo Missão, Luz Verde real
- [ ] v2.1 — Suporte a MCP (Model Context Protocol)
- [ ] v2.2 — Notebook integration (Jupyter)
- [ ] v3.0 — Agentes múltiplos em paralelo

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
