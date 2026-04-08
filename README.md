# NEXUS AGENT v1.0

Agente de autonomia local para terminal, inspirado no fluxo de uso de Codex e Claude Code.

Local terminal autonomy agent inspired by Codex and Claude Code workflows.

Criado por `Ezequiel 135`.

---

## PT-BR

### Visão Geral

`NEXUS AGENT` roda no terminal, conversa com o usuário, usa ferramentas locais, executa tarefas em loop e mantém uma interface visual para mostrar o que está acontecendo em tempo real.

Ele combina:

- interface de terminal com visual profissional
- modo interativo estilo REPL
- integração com APIs de IA via LiteLLM
- ferramentas locais para shell, arquivos, mouse, teclado e tela
- autenticação por senha para entrar em modo autônomo
- logs, histórico, memória local e proteções contra comandos destrutivos

O agente de IA do terminal já foi ajustado para entender que, quando a tarefa mencionar tela, botão, janela, clicar, cursor, navegador, cor ou digitar no PC, ele deve usar as tools locais de visão e periférico em vez de responder apenas com texto.

Ele também possui memória local persistente. O que o usuário manda pode ser salvo em disco para reutilização futura pelo agente.

### Interface

O NEXUS AGENT pode rodar de dois jeitos:

#### 1. Modo UI

Modo com interface visual em `Textual + Rich`.

Na tela, o usuário vê:

- cabeçalho fixo com o nome `NEXUS AGENT`
- luz de segurança com estado real
- área principal de conversa
- painel lateral com logs das ações
- barra inferior com modelo, latência e estado do modo autônomo

#### 2. Modo Plain

Modo mais parecido com Codex / Claude Code no terminal puro.

Ideal para:

- terminal simples
- ambiente sem suporte completo a TUI
- PowerShell, Windows Terminal, SSH ou shell remoto

Prompt:

```text
nexus>
```

Comandos internos:

- `/help`
- `/status`
- `/tools`
- `/memory`
- `/remember texto`
- `/forget-all`
- `/blocked`
- `/clear`
- `/exit`

### Mockup ASCII da Interface

```text
+--------------------------------------------------------------------------------------+
| NEXUS AGENT v1.0 - STATUS: [OPERACIONAL]                             ● thinking/acting |
| Criado por Ezequiel 135                                                              |
+--------------------------------------------------------------------------------------+
| CHAT / OBJETIVO                                              | ACTION & LOG PANEL     |
|--------------------------------------------------------------|------------------------|
| Você: Organize minha pasta de downloads                      | [13:45:02] PROMPT ...  |
| NEXUS: Vou separar por tipo, mover arquivos e gerar resumo.  | [13:45:03] EXECUTANDO  |
| NEXUS: Lendo diretório atual...                              | [13:45:04] ARQUIVO ... |
| NEXUS: Aplicando reorganização...                            | [13:45:06] PERIFERICO  |
|                                                              | [13:45:08] RESULTADO   |
| nexus>                                                       |                        |
+--------------------------------------------------------------------------------------+
| Modelo: gpt-4o | Latência: 842 ms | CPU/RAM | AUTONOMOUS_MODE=ON | Ezequiel 135       |
+--------------------------------------------------------------------------------------+
```

### Estados Visuais do Agente

- `amarelo`: pensando
- `verde pulsando`: executando ação
- `vermelho`: erro

Logs também vão para:

```text
~/.nexus/nexus.log
```

### O Que o Agente Faz

- conversa com o usuário em linguagem natural
- recebe objetivos longos e executa subtarefas
- lê, escreve, move e apaga arquivos
- executa comandos no shell
- usa mouse, teclado e leitura de tela
- mantém histórico curto da conversa
- mantém memória local persistente
- permite setup inicial de API e modelo
- funciona em Linux e foi preparado para Windows Terminal

### Ferramentas Internas

- `executar_comando(comando)`
- `gerenciar_arquivos(acao, path, content=None, target_path=None)`
- `controle_periferico(acao, x=None, y=None, texto=None)`
- `memoria_local(acao, texto=None, consulta=None)`
- `verificar_pixel(x, y)`

### Estrutura do Projeto

- `core/`: configuração, estado, safeguards, logs, memória e ponte LiteLLM
- `ui/`: interface visual e modo plain
- `main.py`: entrada principal do comando `nexus`
- `install.sh`: instalador Linux
- `install.ps1`: instalador PowerShell / Windows Terminal
- `requirements.txt`: dependências Python
- `pc_remote_agent/`: runtime de automação local

### Primeiro Boot

Se `~/.nexus/config.json` não existir, o NEXUS AGENT entra em modo de configuração e pede:

1. `Provider`
2. `API Key`
3. `Model Name`
4. `Senha mestra do NEXUS AGENT`

Depois disso, ele salva:

- `~/.nexus/config.json`
- `~/.nexus/history.json`
- `~/.nexus/activity.json`
- `~/.nexus/memory.json`

### Segurança

O agente bloqueia comandos que possam:

- danificar BIOS ou EFI
- formatar disco
- alterar boot
- apagar a raiz do sistema
- corromper o sistema operacional
- desligar ou reiniciar a máquina de forma destrutiva

Exemplos bloqueados:

- `rm -rf /`
- `mkfs.ext4 /dev/sda1`
- `fdisk /dev/sda`
- `parted /dev/nvme0n1`
- `dd if=image.iso of=/dev/sda`
- `flashrom -p internal -w bios.bin`
- `shutdown now`

Ver lista:

```bash
nexus blocked
```

### Instalação no Linux

Requisitos:

```bash
sudo apt-get update
sudo apt-get install -y git python3-venv python3-pip python3-dev python3-tk scrot xdotool tesseract-ocr
```

Instalação local:

```bash
cd "NEXUS AGENT"
chmod +x install.sh nexus
./install.sh
nexus start
```

Instalação via GitHub:

```bash
export NEXUS_REPO_URL="https://github.com/Ezequiel135/Nexus-Agent.git"
curl -sSL https://raw.githubusercontent.com/Ezequiel135/Nexus-Agent/main/install.sh | bash
```

Baixar com `git clone`:

```bash
git clone https://github.com/Ezequiel135/Nexus-Agent.git
cd "Nexus-Agent"
chmod +x install.sh nexus
./install.sh
```

Baixar como ZIP:

1. Abra `https://github.com/Ezequiel135/Nexus-Agent`
2. Clique em `Code`
3. Clique em `Download ZIP`
4. Extraia a pasta
5. Entre na pasta extraída e rode:

```bash
chmod +x install.sh nexus
./install.sh
```

### Instalação no Windows Terminal / PowerShell

Requisitos:

- Python 3.10+
- Git
- PowerShell ou Windows Terminal

Passo a passo:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
nexus start --plain
```

Baixar do GitHub no Windows:

```powershell
git clone https://github.com/Ezequiel135/Nexus-Agent.git
cd Nexus-Agent
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
```

### Comandos Principais

```bash
nexus setup
nexus blocked
nexus doctor
nexus start
nexus start --plain
nexus start --task "Organize minha pasta de downloads e crie um resumo"
nexus update
```

### Arquivos do Usuário

- `~/.nexus/config.json`: provider, API e modelo
- `~/.nexus/nexus.log`: histórico de ações
- `~/.nexus/history.json`: histórico recente da conversa
- `~/.nexus/activity.json`: estado atual do agente
- `~/.nexus/memory.json`: memória local persistente
- `~/.nexus/repo.txt`: origem usada pelo `update`

### Troubleshooting

#### 1. `Dependencias da interface nao instaladas`

Causa:

- `textual` ou outra lib do `requirements.txt` não está instalada

Solução:

```bash
pip install -r requirements.txt
```

Ou rode o agente em modo plain:

```bash
nexus start --plain
```

#### 2. `ERRO DE COMUNICACAO: VERIFIQUE SUA COTA OU CHAVE DE API`

Causa:

- chave inválida
- cota encerrada
- modelo incorreto
- provider mal configurado

Solução:

1. Rode `nexus setup`
2. confira provider, API key e model name
3. teste novamente

#### 3. Automação gráfica não funciona no Linux

Causa:

- terminal sem acesso ao display
- `DISPLAY` incorreto
- sessão remota sem permissões

Solução:

- use `nexus doctor`
- prefira `nexus start --plain` em ambiente remoto
- confirme acesso correto ao display gráfico

#### 4. `nexus` não é reconhecido como comando

Causa:

- terminal ainda não recarregou o `PATH`
- instalação incompleta

Solução:

- abra um novo terminal
- ou rode direto:

```bash
python3 main.py start --plain
```

#### 5. PowerShell bloqueia o script `install.ps1`

Causa:

- política de execução restrita

Solução:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
```

---

## English

### Overview

`NEXUS AGENT` is a local terminal autonomy agent inspired by Codex and Claude Code.

It runs inside the terminal, talks to the user, uses local tools, executes tasks in loops, and keeps a visual interface showing what is happening in real time.

It combines:

- a professional terminal UI
- a REPL-style plain mode
- AI API integration through LiteLLM
- local tools for shell, files, mouse, keyboard, and screen
- password-based autonomous mode
- logs, short-term history, local memory, and destructive-command safeguards

The terminal AI has been adjusted to understand that whenever a task mentions screen, window, button, cursor, browser, color, clicking, or typing on the PC, it should use local vision and peripheral tools instead of replying only with text.

### Interface Modes

#### 1. UI Mode

Full visual mode built with `Textual + Rich`.

The screen shows:

- a fixed `NEXUS AGENT` header
- a real activity safety light
- a main chat area
- a side action/log panel
- a bottom status bar with model, latency, and autonomy state

#### 2. Plain Mode

The closest mode to Codex / Claude Code in a pure terminal flow.

Best for:

- simple terminals
- environments without full TUI support
- PowerShell, Windows Terminal, SSH, or remote shells

Prompt:

```text
nexus>
```

Built-in commands:

- `/help`
- `/status`
- `/tools`
- `/memory`
- `/remember text`
- `/forget-all`
- `/blocked`
- `/clear`
- `/exit`

### Agent Visual States

- `yellow`: thinking
- `pulsing green`: acting
- `red`: error

Logs are also written to:

```text
~/.nexus/nexus.log
```

### Internal Tools

- `executar_comando(comando)`
- `gerenciar_arquivos(acao, path, content=None, target_path=None)`
- `controle_periferico(acao, x=None, y=None, texto=None)`
- `memoria_local(acao, texto=None, consulta=None)`
- `verificar_pixel(x, y)`

### First Boot

If `~/.nexus/config.json` does not exist, NEXUS AGENT enters setup mode and asks for:

1. `Provider`
2. `API Key`
3. `Model Name`
4. `Master password`

It then stores:

- `~/.nexus/config.json`
- `~/.nexus/history.json`
- `~/.nexus/activity.json`
- `~/.nexus/memory.json`

### Linux Installation

Requirements:

```bash
sudo apt-get update
sudo apt-get install -y git python3-venv python3-pip python3-dev python3-tk scrot xdotool tesseract-ocr
```

Local install:

```bash
cd "NEXUS AGENT"
chmod +x install.sh nexus
./install.sh
nexus start
```

GitHub install:

```bash
export NEXUS_REPO_URL="https://github.com/Ezequiel135/Nexus-Agent.git"
curl -sSL https://raw.githubusercontent.com/Ezequiel135/Nexus-Agent/main/install.sh | bash
```

### Windows Terminal / PowerShell Installation

Requirements:

- Python 3.10+
- Git
- PowerShell or Windows Terminal

Steps:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
nexus start --plain
```

### Main Commands

```bash
nexus setup
nexus blocked
nexus doctor
nexus start
nexus start --plain
nexus start --task "Organize my downloads folder and create a summary"
nexus update
```

### Troubleshooting

#### 1. `Dependencias da interface nao instaladas`

Cause:

- `textual` or another dependency is missing

Fix:

```bash
pip install -r requirements.txt
```

Or run plain mode:

```bash
nexus start --plain
```

#### 2. `ERRO DE COMUNICACAO: VERIFIQUE SUA COTA OU CHAVE DE API`

Cause:

- invalid API key
- exhausted quota
- wrong model name
- wrong provider setup

Fix:

1. run `nexus setup`
2. check provider, API key, and model name
3. retry

#### 3. GUI automation does not work on Linux

Cause:

- no display access
- incorrect `DISPLAY`
- remote session without permissions

Fix:

- run `nexus doctor`
- prefer `nexus start --plain` on remote environments
- confirm GUI display access

#### 4. `nexus` command is not found

Cause:

- terminal has not reloaded `PATH`
- installation did not finish correctly

Fix:

- open a new terminal
- or run directly:

```bash
python3 main.py start --plain
```
