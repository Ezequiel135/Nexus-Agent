from __future__ import annotations

import hashlib
import json
import os
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(slots=True)
class NexusConfig:
    provider: str
    api_key: str
    model_name: str
    password_hash: str
    password_salt: str

    def export_runtime_env(self) -> None:
        provider = self.provider.lower()
        if provider == "openai":
            os.environ["OPENAI_API_KEY"] = self.api_key
        elif provider == "anthropic":
            os.environ["ANTHROPIC_API_KEY"] = self.api_key
        elif provider == "google":
            os.environ["GEMINI_API_KEY"] = self.api_key
        elif provider == "groq":
            os.environ["GROQ_API_KEY"] = self.api_key
        elif provider == "ollama":
            os.environ.setdefault("OLLAMA_API_KEY", self.api_key or "local")
        os.environ["NEXUS_MODEL_NAME"] = self.model_name
        os.environ["NEXUS_PROVIDER"] = self.provider


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


def config_exists() -> bool:
    return NexusPaths.config_path.exists()


def load_config() -> NexusConfig:
    NexusPaths.ensure()
    payload = json.loads(NexusPaths.config_path.read_text(encoding="utf-8"))
    return NexusConfig(**payload)


def save_config(config: NexusConfig) -> None:
    NexusPaths.ensure()
    NexusPaths.config_path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
    os.chmod(NexusPaths.config_path, 0o600)
