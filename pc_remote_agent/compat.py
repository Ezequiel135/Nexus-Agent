import shlex
import os
import subprocess
import sys
from pathlib import Path

from .bridge import BRIDGE_DIR, write_bridge_state
from .errors import friendly_error_message
from . import runtime


class LegacyCompat:
    """Compatibility facade implemented on top of the modular runtime."""

    def __init__(self, agent):
        self.agent = agent

    def self_test(self):
        print("\n\033[1;36m=== SELF TEST ===\033[0m")
        tests_passed = 0
        tests_failed = 0

        try:
            _, width, height = runtime.pixel_grid()
            assert width > 0 and height > 0
            print(f"  \033[1;32m[PASS]\033[0m Screen capture: {width}x{height}")
            tests_passed += 1
        except Exception as e:
            print(f"  \033[1;31m[FAIL]\033[0m Screen capture: {e}")
            tests_failed += 1

        try:
            grid, _, _ = runtime.pixel_grid(32, 18)
            assert len(grid) == 18 and len(grid[0]) == 32
            print("  \033[1;32m[PASS]\033[0m Pixel grid: 32x18")
            tests_passed += 1
        except Exception as e:
            print(f"  \033[1;31m[FAIL]\033[0m Pixel grid: {e}")
            tests_failed += 1

        try:
            mx, my = runtime.mouse_position()
            assert isinstance(mx, int) and isinstance(my, int)
            print(f"  \033[1;32m[PASS]\033[0m Mouse position: ({mx},{my})")
            tests_passed += 1
        except Exception as e:
            print(f"  \033[1;31m[FAIL]\033[0m Mouse position: {e}")
            tests_failed += 1

        try:
            regions = runtime.analyze_regions()
            assert regions
            print(f"  \033[1;32m[PASS]\033[0m Region analysis: {len(regions)} regions")
            tests_passed += 1
        except Exception as e:
            print(f"  \033[1;31m[FAIL]\033[0m Region analysis: {e}")
            tests_failed += 1

        try:
            windows = runtime.visible_windows()
            print(f"  \033[1;32m[PASS]\033[0m Windows: {len(windows)} found")
            tests_passed += 1
        except Exception as e:
            print(f"  \033[1;31m[FAIL]\033[0m Windows: {e}")
            tests_failed += 1

        try:
            platform_name = runtime.platform_name()
            print(f"  \033[1;32m[PASS]\033[0m Platform: {platform_name}")
            tests_passed += 1
        except Exception as e:
            print(f"  \033[1;31m[FAIL]\033[0m Platform detect: {e}")
            tests_failed += 1

        try:
            text, _ = runtime.read_chat_region(timeout=2)
            print(f"  \033[1;32m[PASS]\033[0m OCR: {'working' if text else 'no text found (OK)'}")
            tests_passed += 1
        except Exception as e:
            print(f"  \033[1;31m[FAIL]\033[0m OCR: {e}")
            tests_failed += 1

        try:
            BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
            write_bridge_state("running", "self-test", detail="Bridge write test")
            print(f"  \033[1;32m[PASS]\033[0m Bridge files: {BRIDGE_DIR}")
            tests_passed += 1
        except Exception as e:
            print(f"  \033[1;31m[FAIL]\033[0m Bridge files: {e}")
            tests_failed += 1

        try:
            env = os.environ.copy()
            project_root = str(Path(__file__).resolve().parents[1])
            env["PYTHONPATH"] = project_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
            proc = subprocess.Popen(
                [sys.executable, "-m", "pc_remote_agent.indicator", "--sleep", "0.1"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
            runtime.time.sleep(0.4)
            proc.terminate()
            proc.wait(timeout=1)
            print("  \033[1;32m[PASS]\033[0m Safety indicator process")
            tests_passed += 1
        except Exception as e:
            print(f"  \033[1;31m[FAIL]\033[0m Safety indicator process: {e}")
            tests_failed += 1

        print(f"\n\033[1;36m=== RESULT: {tests_passed} passed, {tests_failed} failed ===\033[0m")
        return tests_failed == 0

    def auto_configure(self):
        print("\n\033[1;36m=== AUTO CONFIGURE ===\033[0m")
        _, width, height = runtime.pixel_grid()
        print(f"  Screen: {width}x{height}")
        print(f"  Center: ({width//2}, {height//2})")
        print(f"  Platform: {runtime.platform_name()}")
        print(f"  DISPLAY: {os.environ.get('DISPLAY', 'NOT SET')}")
        print(f"  Windows visible: {len(runtime.visible_windows())}")
        return True

    def parse_and_run(self, line):
        try:
            parts = shlex.split(line.strip())
        except ValueError as e:
            print(f"  \033[1;31mParse error: {e}\033[0m")
            return True

        if not parts:
            return True

        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("quit", "exit"):
            return False
        if cmd in ("help", "list"):
            print("Commands: see pos windows click move drag type key hotkey scroll screenshot read_chat chat_state chat_new read_frames read_scroll reply_new browser_youtube browser_google browser_chatgpt browser_open browser_search_google browser_search_youtube self_test auto_configure")
            return True
        if cmd == "see":
            return self.agent.screen.see(colored="--color" in args, full="--full" in args)
        if cmd == "pos":
            print(f"  Mouse at {runtime.mouse_position()}")
            return True
        if cmd == "windows":
            for wid, name in self.agent.windows.list():
                print(f"  {wid}: {name}")
            return True
        if cmd == "click":
            x = int(args[0]) if len(args) >= 1 else None
            y = int(args[1]) if len(args) >= 2 else None
            button = args[2] if len(args) >= 3 else "left"
            return self.agent.mouse.click(x, y, button=button)
        if cmd == "double":
            x = int(args[0]) if args else None
            y = int(args[1]) if len(args) > 1 else None
            return self.agent.mouse.double_click(x, y)
        if cmd == "right":
            x = int(args[0]) if args else None
            y = int(args[1]) if len(args) > 1 else None
            return self.agent.mouse.right_click(x, y)
        if cmd == "move":
            return self.agent.mouse.move_to(int(args[0]), int(args[1]))
        if cmd == "drag":
            return self.agent.mouse.drag_to(int(args[0]), int(args[1]), int(args[2]), int(args[3]))
        if cmd == "type":
            return self.agent.keyboard.type_text(" ".join(args))
        if cmd == "key":
            return self.agent.keyboard.press(args[0])
        if cmd == "hotkey":
            return self.agent.keyboard.hotkey(" ".join(args))
        if cmd == "scroll":
            return self.agent.mouse.scroll(int(args[0]) if args else 5)
        if cmd == "screenshot":
            where = args[0] if args else None
            return self.agent.screen.screenshot(where)
        if cmd == "read_chat":
            return self.agent.chat.read()
        if cmd in ("chat_state", "state"):
            return self.agent.chat.state()
        if cmd in ("chat_new", "new"):
            return self.agent.chat.new()
        if cmd == "read_frames":
            frames = int(args[0]) if args else 4
            return self.agent.chat.read_frames(frames=frames)
        if cmd == "read_scroll":
            direction = args[0] if args else "down"
            steps = int(args[1]) if len(args) > 1 else 3
            return self.agent.chat.read_scroll(direction=direction, steps=steps)
        if cmd == "reply_new":
            return self.agent.chat.reply_new(" ".join(args))
        if cmd == "browser_youtube":
            return self.agent.browser.open_youtube()
        if cmd == "browser_google":
            return self.agent.browser.open_google()
        if cmd == "browser_chatgpt":
            return self.agent.browser.open_chatgpt()
        if cmd == "browser_open":
            return self.agent.browser.open(" ".join(args))
        if cmd == "browser_search_google":
            return self.agent.browser.search_google(" ".join(args))
        if cmd == "browser_search_youtube":
            return self.agent.browser.search_youtube(" ".join(args))
        if cmd == "self_test":
            return self.self_test()
        if cmd == "auto_configure":
            return self.auto_configure()

        print(f"  {friendly_error_message(ValueError(f'Unknown command: {cmd}'))}")
        return True
