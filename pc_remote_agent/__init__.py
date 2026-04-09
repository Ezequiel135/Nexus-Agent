from core.version import APP_VERSION

__version__ = APP_VERSION

__all__ = ["DesktopAgent", "__version__"]


def __getattr__(name):
    if name == "DesktopAgent":
        from .agent import DesktopAgent

        return DesktopAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
