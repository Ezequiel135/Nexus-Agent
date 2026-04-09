from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from dataclasses import asdict, dataclass, field
from pathlib import Path

KNOWN_PROVIDERS = ("OpenAI", "Anthropic", "Google", "Ollama", "Groq", "Custom")
RUNTIME_ENV_KEYS = (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "OLLAMA_API_KEY",
    "NEXUS_MODEL_NAME",
    "NEXUS_PROVIDER",
    "NEXUS_ACCOUNT_NAME",
    "NEXUS_AGENT_NAME",
    "NEXUS_CUSTOM_PROVIDER",
)


@dataclass(slots=True)
class NexusAccount:
    id: str
    name: str
    provider: str
    api_key: str
    model_name: str
    base_url: str = ""
    custom_provider: str = ""

    @property
    def provider_label(self) -> str:
        if self.is_custom and self.custom_provider:
            return self.custom_provider
        return self.provider

    @property
    def is_custom(self) -> bool:
        return normalize_provider(self.provider) == "Custom"

    def completion_kwargs(self) -> dict[str, str]:
        kwargs: dict[str, str] = {}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["base_url"] = self.base_url
        if self.is_custom and self.custom_provider:
            kwargs["custom_llm_provider"] = self.custom_provider.strip()
        return kwargs


@dataclass(slots=True)
class NexusAgentProfile:
    id: str
    name: str
    account_id: str
    system_prompt: str = ""


@dataclass(slots=True)
class NexusMcpServer:
    id: str
    name: str
    command: str
    enabled: bool = True


@dataclass(slots=True)
class NexusConfig:
    password_hash: str
    password_salt: str
    ui_mode: str = "auto"
    accounts: list[NexusAccount] = field(default_factory=list)
    active_account_id: str = ""
    agents: list[NexusAgentProfile] = field(default_factory=list)
    active_agent_id: str = ""
    mcp_servers: list[NexusMcpServer] = field(default_factory=list)

    @property
    def active_account(self) -> NexusAccount | None:
        if not self.active_account_id:
            return None
        for account in self.accounts:
            if account.id == self.active_account_id:
                return account
        return None

    @property
    def active_agent(self) -> NexusAgentProfile | None:
        if self.active_agent_id:
            for agent in self.agents:
                if agent.id == self.active_agent_id:
                    return agent
        if self.active_account_id:
            for agent in self.agents:
                if agent.account_id == self.active_account_id:
                    return agent
        return None

    @property
    def provider(self) -> str:
        account = self.active_account
        return account.provider if account else ""

    @property
    def api_key(self) -> str:
        account = self.active_account
        return account.api_key if account else ""

    @property
    def model_name(self) -> str:
        account = self.active_account
        return account.model_name if account else ""

    @property
    def base_url(self) -> str:
        account = self.active_account
        return account.base_url if account else ""

    @property
    def custom_provider(self) -> str:
        account = self.active_account
        return account.custom_provider if account else ""

    def runtime_label(self) -> str:
        account = self.active_account
        agent = self.active_agent
        model = self.model_name or "-"
        extras = []
        if account:
            extras.append(account.name)
        if agent:
            extras.append(agent.name)
        if extras:
            return f"{model} | {' | '.join(extras)}"
        return model

    def completion_kwargs(self) -> dict[str, str]:
        account = self.active_account
        if account is None:
            raise RuntimeError("Nenhuma conta ativa. Rode nexus login ou nexus setup.")
        return account.completion_kwargs()

    def export_runtime_env(self) -> None:
        for key in RUNTIME_ENV_KEYS:
            os.environ.pop(key, None)

        account = self.active_account
        if account is None:
            return

        provider = normalize_provider(account.provider).lower()
        if provider == "openai":
            os.environ["OPENAI_API_KEY"] = account.api_key
            if account.base_url:
                os.environ["OPENAI_BASE_URL"] = account.base_url
        elif provider == "anthropic":
            os.environ["ANTHROPIC_API_KEY"] = account.api_key
        elif provider == "google":
            os.environ["GEMINI_API_KEY"] = account.api_key
        elif provider == "groq":
            os.environ["GROQ_API_KEY"] = account.api_key
        elif provider == "ollama":
            os.environ["OLLAMA_API_KEY"] = account.api_key or "local"
            if account.base_url:
                os.environ["OPENAI_BASE_URL"] = account.base_url
        else:
            if account.api_key:
                os.environ["OPENAI_API_KEY"] = account.api_key
            if account.base_url:
                os.environ["OPENAI_BASE_URL"] = account.base_url
            if account.custom_provider:
                os.environ["NEXUS_CUSTOM_PROVIDER"] = account.custom_provider

        os.environ["NEXUS_MODEL_NAME"] = account.model_name
        os.environ["NEXUS_PROVIDER"] = account.provider_label
        os.environ["NEXUS_ACCOUNT_NAME"] = account.name
        if self.active_agent is not None:
            os.environ["NEXUS_AGENT_NAME"] = self.active_agent.name


class NexusPaths:
    base_dir = Path.home() / ".nexus"
    config_path = base_dir / "config.json"
    log_path = base_dir / "nexus.log"
    trash_dir = base_dir / "trash"
    history_path = base_dir / "history.json"
    activity_path = base_dir / "activity.json"
    repo_path = base_dir / "repo.txt"
    memory_path = base_dir / "memory.json"

    @classmethod
    def ensure(cls) -> None:
        cls.base_dir.mkdir(parents=True, exist_ok=True)
        cls.trash_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(cls.base_dir, 0o700)


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def create_password_hash(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    return _hash_password(password, salt), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    return secrets.compare_digest(_hash_password(password, salt), password_hash)


def normalize_ui_mode(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"visual", "plain"}:
        return normalized
    return "auto"


def normalize_provider(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "OpenAI"
    for provider in KNOWN_PROVIDERS:
        if raw.lower() == provider.lower():
            return provider
    return "Custom"


def sanitize_base_url(value: str | None) -> str:
    return (value or "").strip().rstrip("/")


def slugify_name(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    normalized = normalized.strip("-")
    return normalized or fallback


def unique_id(name: str, fallback: str, existing_ids: set[str]) -> str:
    base = slugify_name(name, fallback)
    candidate = base
    counter = 2
    while candidate in existing_ids:
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def make_account(
    name: str,
    provider: str,
    api_key: str,
    model_name: str,
    base_url: str = "",
    custom_provider: str = "",
    existing_ids: set[str] | None = None,
) -> NexusAccount:
    existing_ids = existing_ids or set()
    normalized_provider = normalize_provider(provider)
    return NexusAccount(
        id=unique_id(name, "conta", existing_ids),
        name=name.strip() or "Conta",
        provider=normalized_provider,
        api_key=api_key.strip(),
        model_name=model_name.strip(),
        base_url=sanitize_base_url(base_url),
        custom_provider=custom_provider.strip(),
    )


def make_agent(
    name: str,
    account_id: str,
    system_prompt: str = "",
    existing_ids: set[str] | None = None,
) -> NexusAgentProfile:
    existing_ids = existing_ids or set()
    return NexusAgentProfile(
        id=unique_id(name, "agente", existing_ids),
        name=name.strip() or "Agente",
        account_id=account_id,
        system_prompt=system_prompt.strip(),
    )


def build_initial_config(
    password_hash: str,
    password_salt: str,
    ui_mode: str,
    account: NexusAccount,
    agent: NexusAgentProfile,
) -> NexusConfig:
    return NexusConfig(
        password_hash=password_hash,
        password_salt=password_salt,
        ui_mode=normalize_ui_mode(ui_mode),
        accounts=[account],
        active_account_id=account.id,
        agents=[agent],
        active_agent_id=agent.id,
    )


def find_account(config: NexusConfig, query: str) -> NexusAccount | None:
    needle = query.strip().lower()
    for account in config.accounts:
        if account.id == query or account.name.lower() == needle:
            return account
    return None


def find_agent(config: NexusConfig, query: str) -> NexusAgentProfile | None:
    needle = query.strip().lower()
    for agent in config.agents:
        if agent.id == query or agent.name.lower() == needle:
            return agent
    return None


def find_mcp_server(config: NexusConfig, query: str) -> NexusMcpServer | None:
    needle = query.strip().lower()
    for server in config.mcp_servers:
        if server.id == query or server.name.lower() == needle:
            return server
    return None


def add_account(config: NexusConfig, account: NexusAccount, activate: bool = True) -> None:
    config.accounts.append(account)
    if activate:
        activate_account(config, account.id)


def add_agent(config: NexusConfig, agent: NexusAgentProfile, activate: bool = True) -> None:
    config.agents.append(agent)
    if activate:
        config.active_agent_id = agent.id
        if agent.account_id:
            config.active_account_id = agent.account_id


def add_mcp_server(config: NexusConfig, server: NexusMcpServer) -> None:
    config.mcp_servers.append(server)


def remove_mcp_server(config: NexusConfig, server_query: str) -> NexusMcpServer:
    server = find_mcp_server(config, server_query)
    if server is None:
        raise ValueError(f"Servidor MCP nao encontrado: {server_query}")
    config.mcp_servers = [item for item in config.mcp_servers if item.id != server.id]
    return server


def ensure_agent_for_account(config: NexusConfig, account_id: str) -> NexusAgentProfile:
    for agent in config.agents:
        if agent.account_id == account_id:
            return agent

    account = find_account(config, account_id)
    if account is None:
        raise ValueError("Conta nao encontrada para criar agente padrao.")
    agent = make_agent(
        name=f"Agente {account.name}",
        account_id=account.id,
        existing_ids={item.id for item in config.agents},
    )
    config.agents.append(agent)
    return agent


def activate_account(config: NexusConfig, account_query: str) -> NexusAccount:
    account = find_account(config, account_query)
    if account is None:
        raise ValueError(f"Conta nao encontrada: {account_query}")
    config.active_account_id = account.id
    agent = ensure_agent_for_account(config, account.id)
    config.active_agent_id = agent.id
    return account


def activate_agent(config: NexusConfig, agent_query: str) -> NexusAgentProfile:
    agent = find_agent(config, agent_query)
    if agent is None:
        raise ValueError(f"Agente nao encontrado: {agent_query}")
    config.active_agent_id = agent.id
    if agent.account_id:
        config.active_account_id = agent.account_id
    return agent


def logout_account(config: NexusConfig) -> None:
    config.active_account_id = ""
    config.active_agent_id = ""


def normalize_config(config: NexusConfig) -> NexusConfig:
    config.ui_mode = normalize_ui_mode(config.ui_mode)
    for account in config.accounts:
        account.provider = normalize_provider(account.provider)
        account.base_url = sanitize_base_url(account.base_url)
        account.name = account.name.strip() or "Conta"
        account.model_name = account.model_name.strip()
        account.custom_provider = account.custom_provider.strip()
    for agent in config.agents:
        agent.name = agent.name.strip() or "Agente"
        agent.system_prompt = agent.system_prompt.strip()
    for server in config.mcp_servers:
        server.name = server.name.strip() or "MCP"
        server.command = server.command.strip()

    known_account_ids = {account.id for account in config.accounts}
    config.agents = [
        agent
        for agent in config.agents
        if not agent.account_id or agent.account_id in known_account_ids
    ]

    if config.active_account_id and config.active_account is None:
        config.active_account_id = ""
    if config.active_agent_id and find_agent(config, config.active_agent_id) is None:
        config.active_agent_id = ""
    return config


def config_exists() -> bool:
    return NexusPaths.config_path.exists()


def _load_legacy_config(payload: dict) -> NexusConfig:
    account = make_account(
        name=payload.get("account_name", "Conta principal"),
        provider=payload.get("provider", "OpenAI"),
        api_key=payload.get("api_key", ""),
        model_name=payload.get("model_name", ""),
        base_url=payload.get("base_url", ""),
        custom_provider=payload.get("custom_provider", ""),
    )
    agent = make_agent(
        name=payload.get("agent_name", "Agente principal"),
        account_id=account.id,
        system_prompt=payload.get("agent_system_prompt", ""),
    )
    config = build_initial_config(
        password_hash=payload["password_hash"],
        password_salt=payload["password_salt"],
        ui_mode=payload.get("ui_mode", "auto"),
        account=account,
        agent=agent,
    )
    return normalize_config(config)


def load_config() -> NexusConfig:
    NexusPaths.ensure()
    payload = json.loads(NexusPaths.config_path.read_text(encoding="utf-8"))
    if "accounts" not in payload:
        return _load_legacy_config(payload)

    config = NexusConfig(
        password_hash=payload["password_hash"],
        password_salt=payload["password_salt"],
        ui_mode=payload.get("ui_mode", "auto"),
        accounts=[NexusAccount(**item) for item in payload.get("accounts", [])],
        active_account_id=payload.get("active_account_id", ""),
        agents=[NexusAgentProfile(**item) for item in payload.get("agents", [])],
        active_agent_id=payload.get("active_agent_id", ""),
        mcp_servers=[NexusMcpServer(**item) for item in payload.get("mcp_servers", [])],
    )
    return normalize_config(config)


def save_config(config: NexusConfig) -> None:
    NexusPaths.ensure()
    normalized = normalize_config(config)
    payload = asdict(normalized)
    NexusPaths.config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.chmod(NexusPaths.config_path, 0o600)
