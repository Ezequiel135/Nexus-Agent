from urllib.parse import quote_plus

from .. import runtime


class BrowserService:
    def __init__(self, keyboard, windows):
        self.keyboard = keyboard
        self.windows = windows

    def open(self, url):
        runtime.open_url(url)
        print(f"  \033[1;32mOPEN URL: {url}\033[0m")
        return True

    def open_chatgpt(self):
        return self.open("https://chatgpt.com/")

    def open_youtube(self):
        return self.open("https://www.youtube.com/")

    def open_google(self):
        return self.open("https://www.google.com/")

    def search_google(self, query):
        return self.open(f"https://www.google.com/search?q={quote_plus(query)}")

    def search_youtube(self, query):
        return self.open(f"https://www.youtube.com/results?search_query={quote_plus(query)}")

    def focus_browser(self):
        for candidate in ("chrome", "google chrome", "brave", "firefox", "edge"):
            if self.windows.focus(candidate):
                return True
        return False

    def goto_url_bar_and_type(self, url):
        if runtime.platform_name() in ("linux", "windows"):
            self.keyboard.hotkey("ctrl+l")
        else:
            self.keyboard.hotkey("ctrl+l")
        self.keyboard.type_text(url)
        self.keyboard.press("enter")
        return True
