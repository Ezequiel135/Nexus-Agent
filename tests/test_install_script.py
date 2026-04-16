from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SCRIPT = REPO_ROOT / "install.sh"


class InstallScriptTests(unittest.TestCase):
    def test_installer_retries_with_official_apt_sources_and_versioned_venv(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir) / "home"
            fakebin = Path(tmpdir) / "fakebin"
            source = Path(tmpdir) / "source"
            home.mkdir()
            fakebin.mkdir()
            source.mkdir()
            (source / "main.py").write_text("print('nexus test')\n", encoding="utf-8")
            (source / "requirements.txt").write_text("", encoding="utf-8")
            (home / ".bashrc").write_text("", encoding="utf-8")

            python_version_pkg = f"python{sys.version_info.major}.{sys.version_info.minor}-venv"
            real_python = sys.executable

            self._write_executable(
                fakebin / "sudo",
                """#!/usr/bin/env bash
exec "$@"
""",
            )
            self._write_executable(
                fakebin / "dpkg",
                """#!/usr/bin/env bash
if [ "$1" = "-s" ]; then
    exit 1
fi
exit 0
""",
            )
            self._write_executable(
                fakebin / "apt-get",
                """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$HOME/apt-log.txt"
for arg in "$@"; do
    if [ "$arg" = "update" ]; then
        if printf '%s\\n' "$*" | grep -Fq 'Dir::Etc::sourceparts=/dev/null'; then
            exit 0
        fi
        echo "NO_PUBKEY test" >&2
        exit 100
    fi
    if [ "$arg" = "install" ]; then
        : > "$HOME/.apt_install_done"
        exit 0
    fi
done
exit 0
""",
            )
            self._write_executable(
                fakebin / "python3",
                f"""#!/usr/bin/env bash
set -euo pipefail
REAL_PYTHON="{real_python}"
if [ "${{1:-}}" = "-c" ]; then
    exec "$REAL_PYTHON" "$@"
fi
if [ "${{1:-}}" = "-m" ] && [ "${{2:-}}" = "venv" ]; then
    target="${{3:-}}"
    if [[ "$target" == *"nexus-venv-check."* ]] && [ ! -f "$HOME/.apt_install_done" ]; then
        echo "ensurepip is not available" >&2
        exit 1
    fi
    mkdir -p "$target/bin"
    cat > "$target/bin/pip" <<'EOF'
#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$HOME/pip-log.txt"
exit 0
EOF
    chmod +x "$target/bin/pip"
    cat > "$target/bin/python" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
    chmod +x "$target/bin/python"
    exit 0
fi
exec "$REAL_PYTHON" "$@"
""",
            )

            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "PATH": f"{fakebin}{os.pathsep}{env['PATH']}",
                    "NEXUS_LOCAL_SRC": str(source),
                    "NEXUS_AUTO_INSTALL_DEPS": "1",
                    "OSTYPE": "linux-gnu",
                }
            )
            result = subprocess.run(
                ["bash", str(INSTALL_SCRIPT)],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            apt_log = (home / "apt-log.txt").read_text(encoding="utf-8")
            self.assertIn("update", apt_log)
            self.assertIn("Dir::Etc::sourceparts=/dev/null", apt_log)
            self.assertIn(python_version_pkg, apt_log)
            self.assertTrue((home / ".nexus" / "env" / "bin" / "pip").exists())

    def _write_executable(self, path: Path, content: str) -> None:
        path.write_text(textwrap.dedent(content), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)


if __name__ == "__main__":
    unittest.main()
