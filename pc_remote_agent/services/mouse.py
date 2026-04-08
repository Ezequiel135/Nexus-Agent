from .. import runtime


class MouseService:
    def __init__(self, module, actions):
        self.actions = actions

    def position(self):
        return runtime.mouse_position()

    def click(self, x=None, y=None, button="left"):
        cx, cy = runtime.click(x=x, y=y, button=button)
        print(f"  \033[1;32mCLICK {button} at ({cx},{cy})\033[0m")
        return True

    def double_click(self, x=None, y=None):
        cx, cy = runtime.click(x=x, y=y, clicks=2)
        print(f"  \033[1;32mDOUBLE-CLICK at ({cx},{cy})\033[0m")
        return True

    def right_click(self, x=None, y=None):
        cx, cy = runtime.click(x=x, y=y, button="right")
        print(f"  \033[1;32mRIGHT-CLICK at ({cx},{cy})\033[0m")
        return True

    def move_to(self, x, y, duration=0.2):
        runtime.move_to(x, y, duration=duration)
        print(f"  \033[1;32mMOVED to ({x},{y})\033[0m")
        return True

    def drag_to(self, x1, y1, x2, y2, duration=0.5):
        runtime.drag_to(x1, y1, x2, y2, duration=duration)
        print(f"  \033[1;32mDRAG ({x1},{y1}) -> ({x2},{y2})\033[0m")
        return True

    def scroll(self, amount):
        runtime.scroll(amount)
        print(f"  \033[1;32mSCROLL {amount}\033[0m")
        return True

    def scroll_down(self, steps=5, delay=0.15):
        runtime.scroll_down(steps=steps, delay=delay)
        print(f"  \033[1;32mSCROLLED DOWN {steps}\033[0m")
        return True

    def scroll_up(self, steps=5, delay=0.15):
        runtime.scroll_up(steps=steps, delay=delay)
        print(f"  \033[1;32mSCROLLED UP {steps}\033[0m")
        return True
