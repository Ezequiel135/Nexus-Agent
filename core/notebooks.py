from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .config import NexusPaths
from .logging_utils import log_event

DEFAULT_NOTEBOOK_KERNEL = "python3"


def notebook_root() -> Path:
    NexusPaths.ensure()
    return NexusPaths.notebooks_dir


def resolve_notebook_path(path: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = notebook_root() / candidate
    if candidate.suffix.lower() != ".ipynb":
        candidate = candidate.with_suffix(".ipynb")
    return candidate


def list_notebooks(root: str | None = None) -> list[dict[str, Any]]:
    base = Path(root).expanduser() if root else notebook_root()
    if not base.is_absolute():
        base = notebook_root() / base
    if not base.exists():
        return []

    items = []
    for notebook in sorted(base.rglob("*.ipynb")):
        stat = notebook.stat()
        items.append(
            {
                "path": str(notebook),
                "relative_path": str(notebook.relative_to(base)),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            }
        )
    return items


def create_notebook(path: str, title: str = "", kernel_name: str = DEFAULT_NOTEBOOK_KERNEL) -> dict[str, Any]:
    nbformat = _import_nbformat()
    target = resolve_notebook_path(path)
    if target.exists():
        raise FileExistsError(f"Notebook ja existe: {target}")

    notebook = nbformat.v4.new_notebook()
    notebook.metadata["kernelspec"] = {
        "display_name": kernel_name,
        "language": "python",
        "name": kernel_name,
    }
    notebook.metadata["language_info"] = {"name": "python"}
    if title.strip():
        notebook.cells.append(nbformat.v4.new_markdown_cell(f"# {title.strip()}"))

    _write_notebook(nbformat, target, notebook)
    log_event("NOTEBOOK", f"criado {target}")
    return {
        "ok": True,
        "path": str(target),
        "kernel_name": kernel_name,
        "cells": len(notebook.cells),
    }


def append_cell(path: str, content: str, cell_type: str = "code") -> dict[str, Any]:
    nbformat = _import_nbformat()
    target = resolve_notebook_path(path)
    notebook = _load_notebook(nbformat, target)
    normalized_type = (cell_type or "code").strip().lower()
    if normalized_type == "markdown":
        notebook.cells.append(nbformat.v4.new_markdown_cell(content))
    else:
        notebook.cells.append(nbformat.v4.new_code_cell(content))
        normalized_type = "code"
    _write_notebook(nbformat, target, notebook)
    log_event("NOTEBOOK", f"celula {normalized_type} adicionada em {target}")
    return {
        "ok": True,
        "path": str(target),
        "cell_type": normalized_type,
        "cells": len(notebook.cells),
    }


def read_notebook(path: str) -> dict[str, Any]:
    nbformat = _import_nbformat()
    target = resolve_notebook_path(path)
    notebook = _load_notebook(nbformat, target)
    kernel_name = (
        notebook.metadata.get("kernelspec", {}).get("name")
        or notebook.metadata.get("kernelspec", {}).get("display_name")
        or DEFAULT_NOTEBOOK_KERNEL
    )
    cells = []
    for index, cell in enumerate(notebook.cells, start=1):
        source = (cell.get("source", "") or "").strip()
        preview = " ".join(source.splitlines())
        cells.append(
            {
                "index": index,
                "type": cell.get("cell_type", "unknown"),
                "preview": preview[:160] or "-",
                "outputs": len(cell.get("outputs", [])) if cell.get("cell_type") == "code" else 0,
            }
        )
    return {
        "ok": True,
        "path": str(target),
        "kernel_name": kernel_name,
        "cells": cells,
        "cell_count": len(cells),
    }


def execute_notebook(
    path: str,
    *,
    kernel_name: str = "",
    timeout: int = 300,
    cwd: str = "",
) -> dict[str, Any]:
    nbformat = _import_nbformat()
    NotebookClient = _import_nbclient()
    target = resolve_notebook_path(path)
    notebook = _load_notebook(nbformat, target)
    chosen_kernel = (
        kernel_name.strip()
        or notebook.metadata.get("kernelspec", {}).get("name")
        or DEFAULT_NOTEBOOK_KERNEL
    )
    run_dir = Path(cwd).expanduser() if cwd.strip() else target.parent
    run_dir.mkdir(parents=True, exist_ok=True)

    client = NotebookClient(
        notebook,
        timeout=timeout,
        kernel_name=chosen_kernel,
        resources={"metadata": {"path": str(run_dir)}},
    )
    client.execute()
    _write_notebook(nbformat, target, notebook)

    outputs: list[str] = []
    executed_cells = 0
    for cell in notebook.cells:
        if cell.get("cell_type") != "code":
            continue
        executed_cells += 1
        for output in cell.get("outputs", []):
            rendered = _render_output(output)
            if rendered:
                outputs.append(rendered[:240])
    log_event("NOTEBOOK", f"executado {target} kernel={chosen_kernel}")
    return {
        "ok": True,
        "path": str(target),
        "kernel_name": chosen_kernel,
        "cwd": str(run_dir),
        "executed_cells": executed_cells,
        "output_preview": outputs[:8],
    }


def _import_nbformat():
    try:
        import nbformat
    except ImportError as exc:
        raise RuntimeError("Dependencias de notebook indisponiveis. Rode pip install -r requirements.txt.") from exc
    return nbformat


def _import_nbclient():
    try:
        from nbclient import NotebookClient
    except ImportError as exc:
        raise RuntimeError("Execucao de notebook indisponivel. Rode pip install -r requirements.txt.") from exc
    return NotebookClient


def _load_notebook(nbformat, target: Path):
    if not target.exists():
        raise FileNotFoundError(f"Notebook nao encontrado: {target}")
    with target.open("r", encoding="utf-8") as fh:
        return nbformat.read(fh, as_version=4)


def _write_notebook(nbformat, target: Path, notebook) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        nbformat.write(notebook, fh)


def _render_output(output: Any) -> str:
    if not isinstance(output, dict):
        return str(output)
    output_type = output.get("output_type", "")
    if output_type == "stream":
        return (output.get("text", "") or "").strip()
    if output_type in {"execute_result", "display_data"}:
        data = output.get("data", {})
        if "text/plain" in data:
            return str(data["text/plain"]).strip()
    if output_type == "error":
        traceback = output.get("traceback", []) or []
        return "\n".join(traceback).strip() or str(output.get("ename", "erro"))
    return ""
