from .. import runtime


class WindowService:
    def __init__(self, module, actions):
        self.actions = actions

    def focus(self, name):
        if runtime.focus_window(name):
            print(f"  \033[1;32mFOCUSED window: {name}\033[0m")
            return True
        print(f"  \033[1;31mWindow '{name}' not found\033[0m")
        return False

    def list(self):
        return runtime.visible_windows()
