# Legacy Entry Points

Esta pasta guarda launchers e arquivos de compatibilidade.

O arquivo da raiz:
- `/home/ezequiel/pc_remote_unified.py`

foi mantido porque ainda e o ponto de entrada mais seguro para quem ja chama o CLI antigo direto.

O projeto novo mora em:
- `/home/ezequiel/pc_remote_project/pc_remote_agent`

Se no futuro todas as automacoes passarem a usar apenas `python3 -m pc_remote_agent`, o launcher da raiz pode ser removido.
