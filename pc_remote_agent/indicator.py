import argparse
import sys
import signal
import time


def show_indicator(width=70, height=12, x=12, y=32, color="#2cff66", label="AI ACTIVE"):
    import tkinter as tk

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.lift()
    try:
        root.attributes("-type", "dock")
    except Exception:
        pass
    try:
        root.attributes("-alpha", 0.95)
    except Exception:
        pass
    if sys.platform.startswith("win"):
        try:
            root.wm_attributes("-toolwindow", True)
        except Exception:
            pass
    root.configure(bg=color)
    root.geometry(f"{width}x{height}+{x}+{y}")
    canvas = tk.Canvas(root, width=width, height=height, bg=color, highlightthickness=1, highlightbackground="#0e3b1a", bd=0)
    canvas.pack(fill="both", expand=True)
    canvas.create_rectangle(0, 0, width, height, fill=color, outline="#0e3b1a", width=1)
    canvas.create_oval(4, 2, 12, 10, fill="#eaffee", outline="")
    canvas.create_text(18, height // 2, anchor="w", text=label, fill="#063311", font=("TkDefaultFont", 7, "bold"))
    root.update_idletasks()

    def shutdown(*_args):
        if root.winfo_exists():
            root.after(0, root.destroy)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    root.mainloop()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--width", type=int, default=70)
    parser.add_argument("--height", type=int, default=12)
    parser.add_argument("--x", type=int, default=12)
    parser.add_argument("--y", type=int, default=32)
    parser.add_argument("--color", default="#2cff66")
    parser.add_argument("--label", default="AI ACTIVE")
    args = parser.parse_args(argv)
    if args.sleep > 0:
        time.sleep(args.sleep)
    show_indicator(
        width=args.width,
        height=args.height,
        x=args.x,
        y=args.y,
        color=args.color,
        label=args.label,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
