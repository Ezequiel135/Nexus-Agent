from .. import runtime
import pyautogui


class KeyboardService:
    def __init__(self, actions):
        self.actions = actions

    def type_text(self, text, speed=0.03):
        runtime.type_text(text, speed=speed)
        print(f"  \033[1;32mTYPED: {text[:60]}{'...' if len(text) > 60 else ''}\033[0m")
        return True

    def press(self, key):
        runtime.press(key)
        print(f"  \033[1;32mKEY: {key}\033[0m")
        return True

    def hotkey(self, keys):
        runtime.hotkey(keys)
        if isinstance(keys, str):
            keys = keys.split("+")
        print(f"  \033[1;32mHOTKEY: {'+'.join(keys)}\033[0m")
        return True

    def copy(self):
        return self.hotkey("ctrl+c")

    def paste(self):
        return self.hotkey("ctrl+v")

    def undo(self):
        return self.hotkey("ctrl+z")

    def select_all(self):
        return self.hotkey("ctrl+a")

    def alt_tab(self, count=1):
        pyautogui.keyDown("alt")
        for _ in range(count):
            pyautogui.press("tab")
            runtime.time.sleep(0.2)
        pyautogui.keyUp("alt")
        print(f"  \033[1;32mALT+TAB x{count}\033[0m")
        return True
