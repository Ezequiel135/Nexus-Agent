# NEXUS AGENT

Agente local para terminal com execucao de tarefas reais no computador.

[![GitHub](https://img.shields.io/badge/GitHub-Ezequiel135-blue?logo=github)](https://github.com/Ezequiel135/Nexus-Agent)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## O que e

O **NEXUS AGENT** roda no terminal, entende instrucoes em linguagem natural e executa acoes locais com foco em produtividade e automacao. O projeto combina chat, planejamento, execucao assistida e ferramentas locais em uma interface simples.

## Recursos

- Execucao de comandos locais com controles de seguranca
- Manipulacao de arquivos e memoria local
- Interface visual com Textual e modo plain para terminal puro
- Suporte a MCP via `stdio`
- Notebooks Jupyter pelo CLI
- Agentes paralelos para comparar respostas e planos
- Integracoes remotas por bots

## Requisitos

- Python `3.10+`
- `git`
- Linux ou macOS

Dependencias de desktop como `scrot`, `xdotool` e `tesseract-ocr` sao recomendadas para recursos visuais no Linux.

## Instalacao

### Instalacao rapida

```bash
git clone https://github.com/Ezequiel135/Nexus-Agent.git
cd Nexus-Agent
chmod +x install.sh nexus
./install.sh
```

Depois abra um novo terminal e execute:

```bash
nexus
```

No Linux com `apt`, o instalador tenta baixar dependencias automaticamente e, se um repositório de terceiro quebrar o `apt update`, ele refaz a tentativa usando só os repositórios oficiais do sistema.

### Execucao direta no projeto

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python3 main.py start --plain
```

## Configuracao

Na primeira execucao, o setup salva a configuracao em `~/.nexus/config.json`.

Voce pode configurar:

- `UI mode`: `visual` ou `plain`
- `runtime`: `online`, `hybrid` ou `offline`
- `provider`: `OpenAI`, `Anthropic`, `Google`, `Ollama`, `Groq` ou `Custom`
- `model name`
- `base URL` quando necessario
- `API key`
- conta ativa e agente ativo

### Providers

#### OpenAI / Anthropic / Google / Groq

Preencha:

- provider
- API key
- model name
- base URL apenas se usar endpoint customizado

#### Ollama

Preencha:

- provider `Ollama`
- model name

Se a `base URL` ficar vazia, o projeto usa `http://127.0.0.1:11434`.

Exemplo de modelo:

```text
llama3.2
```

#### Custom

Preencha em campos separados:

- nome do provider
- base URL / endpoint
- API key
- model name

Nao misture URL, nome do provider e chave no mesmo campo.

### Variaveis de ambiente para setup nao interativo

```bash
export NEXUS_UI_MODE=plain
export NEXUS_RUNTIME_MODE=hybrid
export NEXUS_PASSWORD=1234
export NEXUS_ACCOUNT_NAME="Conta principal"
export NEXUS_AGENT_NAME="Agente principal"
export NEXUS_PROVIDER=OpenAI
export NEXUS_API_KEY="sua-chave"
export NEXUS_MODEL_NAME="gpt-4o-mini"
python3 ui/setup_cli.py
```

## Uso

### Iniciar

```bash
nexus start
```

Modo plain:

```bash
nexus start --plain
```

Com tarefa inicial:

```bash
nexus start --plain --task "organize meus arquivos de download"
```

### Comandos principais

```bash
nexus setup
nexus doctor
nexus accounts
nexus agents
nexus mcp list
nexus notebook list
nexus parallel list
```

### Dentro da sessao

Use comandos como:

- `/help`
- `/status`
- `/tools`
- `/memory`
- `/blocked`
- `/approve`
- `/cancel`

## MCP

Exemplo de cadastro:

```bash
nexus mcp add --name filesystem --command "npx -y @modelcontextprotocol/server-filesystem ~/projeto"
```

Comandos:

```bash
nexus mcp list
nexus mcp resources filesystem
nexus mcp read filesystem "file:///home/user/projeto/README.md"
nexus mcp tools filesystem
nexus mcp remove filesystem
```

## Notebooks

```bash
nexus notebook list
nexus notebook create demos/analise --title "Analise inicial"
nexus notebook add-cell demos/analise --type code --content "print('hello')"
nexus notebook read demos/analise
nexus notebook run demos/analise --timeout 300
```

## Agentes paralelos

```bash
nexus parallel list
nexus parallel run --task "compare duas abordagens para refatorar este modulo" --agent agente-a --agent agente-b
```

## Estrutura do projeto

```text
Nexus-Agent/
├── core/
├── ui/
├── pc_remote_agent/
├── tests/
├── main.py
├── install.sh
├── install.ps1
└── requirements.txt
```

## Troubleshooting

### `nexus: command not found`

Abra um novo terminal ou rode:

```bash
source ~/.bashrc
```

### Falha no setup sem interface visual

Use:

```bash
nexus start --plain
```

### Falha de provider local

Confira:

- se o runtime esta em `offline` ou `hybrid`
- se a `base URL` local esta correta
- se o modelo foi informado
- se o provider esta correto

### Recursos visuais nao funcionam no Linux

Instale:

```bash
sudo apt install scrot xdotool tesseract-ocr
```

### `install.sh` falha com `NO_PUBKEY` ou erro em repositório de terceiro

As releases novas do instalador tentam ignorar PPAs/repositórios externos quebrados para instalar apenas o que o Nexus precisa. Se a sua máquina ainda bloquear o `apt`, corrija ou desative o repositório com erro e rode o instalador novamente.

### `ensurepip is not available` ao criar o ambiente virtual

No Ubuntu/Zorin, instale o pacote genérico e o pacote versionado do seu Python. Exemplo para Python 3.10:

```bash
sudo apt install python3-venv python3.10-venv python3-pip
```

## Licenca

MIT
