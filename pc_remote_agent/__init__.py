__version__ = "2.2.0"

__all__ = ["DesktopAgent", "__version__"]


def __getattr__(name):
    if name == "DesktopAgent":
        from .agent import DesktopAgent

        return DesktopAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
