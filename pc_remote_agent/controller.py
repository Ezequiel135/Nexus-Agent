from .agent import DesktopAgent as _DesktopAgent


class DesktopAgent(_DesktopAgent):
    """Backward-compatible controller facade."""

    def mouse_position(self):
        return self.mouse.position()

    def see(self, colored=False, full=False):
        return self.screen.see(colored=colored, full=full)

    def click(self, x=None, y=None, button="left"):
        return self.mouse.click(x=x, y=y, button=button)

    def double_click(self, x=None, y=None):
        return self.mouse.double_click(x=x, y=y)

    def right_click(self, x=None, y=None):
        return self.mouse.right_click(x=x, y=y)

    def move_to(self, x, y, duration=0.2):
        return self.mouse.move_to(x, y, duration=duration)

    def drag_to(self, x1, y1, x2, y2, duration=0.5):
        return self.mouse.drag_to(x1, y1, x2, y2, duration=duration)

    def type_text(self, text, speed=0.03):
        return self.keyboard.type_text(text, speed=speed)

    def press(self, key):
        return self.keyboard.press(key)

    def hotkey(self, keys):
        return self.keyboard.hotkey(keys)

    def scroll(self, amount):
        return self.mouse.scroll(amount)

    def scroll_down(self, steps=5, delay=0.15):
        return self.mouse.scroll_down(steps, delay=delay)

    def scroll_up(self, steps=5, delay=0.15):
        return self.mouse.scroll_up(steps, delay=delay)

    def focus_window(self, name):
        return self.windows.focus(name)

    def list_windows(self):
        return self.windows.list()

    def screenshot(self, where=None):
        return self.screen.screenshot(where)

    def read_chat(self):
        return self.chat.read()

    def chat_state(self):
        return self.chat.state()

    def chat_new(self):
        return self.chat.new()

    def chat_reply_new(self, text, input_x=None, input_y=None, send_x=None, send_y=None):
        return self.chat.reply_new(text, input_x=input_x, input_y=input_y, send_x=send_x, send_y=send_y)

    def read_chat_frames(self, frames=4, delay=0.35):
        return self.chat.read_frames(frames=frames, delay=delay)

    def read_scroll(self, direction="down", steps=3, delay=0.7):
        return self.chat.read_scroll(direction=direction, steps=steps, delay=delay)

    def send_chat_message(self, text):
        return self.chat.send(text)

    def open_url(self, url):
        return self.browser.open(url)

    def open_youtube(self):
        return self.browser.open_youtube()

    def search_google(self, query):
        return self.browser.search_google(query)

    def search_youtube(self, query):
        return self.browser.search_youtube(query)
