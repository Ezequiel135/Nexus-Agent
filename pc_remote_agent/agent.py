from .compat import LegacyCompat
from .services import BrowserService, ChatService, KeyboardService, MouseService, ScreenService, WindowService


class DesktopAgent:
    """Organized desktop agent facade built on the modular runtime."""

    def __init__(self):
        self.module = None
        self.actions = None
        self.mouse = MouseService(None, None)
        self.keyboard = KeyboardService(None)
        self.screen = ScreenService(None, None)
        self.windows = WindowService(None, None)
        self.browser = BrowserService(self.keyboard, self.windows)
        self.chat = ChatService(self.screen, self.mouse, self.keyboard)
        self.legacy = LegacyCompat(self)
        self.run_raw = self.legacy.parse_and_run
