from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class Tool:
    name: str
    description: str
    func: Callable
    parameters: dict[str, Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def registrar(self, name: str, description: str, parameters: dict[str, Any]) -> Callable:
        def decorator(func: Callable) -> Callable:
            self._tools[name] = Tool(
                name=name,
                description=description,
                func=func,
                parameters=parameters,
            )
            return func
        return decorator

    def register(self, name: str, description: str, parameters: dict[str, Any], func: Callable) -> None:
        self._tools[name] = Tool(
            name=name,
            description=description,
            func=func,
            parameters=parameters,
        )

    def executar(self, nome: str, argumentos: dict[str, Any]) -> Any:
        if nome not in self._tools:
            raise ValueError(f"Ferramenta desconhecida: {nome}")
        return self._tools[nome].func(**argumentos)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def tool_schemas(self) -> list[dict[str, Any]]:
        schemas: list[dict[str, Any]] = []
        for tool in self._tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.parameters,
                        "required": list(tool.parameters.keys()),
                    },
                },
            })
        return schemas

    def capabilities_summary(self) -> str:
        lines = ["Ferramentas disponiveis:"]
        for tool in self._tools.values():
            lines.append(f"  - {tool.name}: {tool.description}")
        return "\n".join(lines)
