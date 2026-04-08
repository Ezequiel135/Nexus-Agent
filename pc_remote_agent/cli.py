import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

from .bridge import read_session_consent, write_bridge_state, write_session_consent
from .errors import friendly_error_message
from .policy import command_allowed, raw_command_allowed


def build_parser():
    parser = argparse.ArgumentParser(prog="pc-remote", description="Desktop agent CLI")
    parser.add_argument("--headless", action="store_true", help="Disable on-screen indicator and use logs only")
    parser.add_argument("--trust-session", action="store_true", help="Trust this CLI session and avoid extra prompts in future runs")
    parser.add_argument("--indicator-width", type=int, default=70)
    parser.add_argument("--indicator-height", type=int, default=12)
    parser.add_argument("--indicator-x", type=int, default=12)
    parser.add_argument("--indicator-y", type=int, default=32)
    parser.add_argument("--indicator-label", default="AI ACTIVE")

    sub = parser.add_subparsers(dest="command", required=True)

    raw = sub.add_parser("raw", help="Run a legacy raw command line")
    raw.add_argument("line", help='Example: "click 400 300"')

    batch = sub.add_parser("batch", help="Run multiple CLI commands under one indicator session")
    batch.add_argument("commands", nargs="+", help='Example: "browser youtube" "text key tab" "text type oi"')

    session = sub.add_parser("session", help="Manage one-time trust for future CLI runs")
    session_sub = session.add_subparsers(dest="session_cmd", required=True)
    session_sub.add_parser("grant")
    session_sub.add_parser("revoke")
    session_sub.add_parser("status")

    mouse = sub.add_parser("mouse", help="Mouse actions")
    mouse_sub = mouse.add_subparsers(dest="mouse_cmd", required=True)

    click = mouse_sub.add_parser("click")
    click.add_argument("--x", type=int)
    click.add_argument("--y", type=int)
    click.add_argument("--button", default="left")

    move = mouse_sub.add_parser("move")
    move.add_argument("x", type=int)
    move.add_argument("y", type=int)
    move.add_argument("--duration", type=float, default=0.2)

    scroll = mouse_sub.add_parser("scroll")
    scroll.add_argument("amount", type=int)

    mouse_sub.add_parser("pos")

    text = sub.add_parser("text", help="Keyboard actions")
    text_sub = text.add_subparsers(dest="text_cmd", required=True)

    type_cmd = text_sub.add_parser("type")
    type_cmd.add_argument("value")
    type_cmd.add_argument("--speed", type=float, default=0.03)

    key_cmd = text_sub.add_parser("key")
    key_cmd.add_argument("value")

    hotkey_cmd = text_sub.add_parser("hotkey")
    hotkey_cmd.add_argument("value")

    text_sub.add_parser("copy")
    text_sub.add_parser("paste")
    text_sub.add_parser("undo")
    text_sub.add_parser("select-all")
    alt_tab_cmd = text_sub.add_parser("alt-tab")
    alt_tab_cmd.add_argument("--count", type=int, default=1)

    chat = sub.add_parser("chat", help="Chat-oriented actions")
    chat_sub = chat.add_subparsers(dest="chat_cmd", required=True)

    send = chat_sub.add_parser("send")
    send.add_argument("message")

    send_click = chat_sub.add_parser("send-click")
    send_click.add_argument("message")
    send_click.add_argument("--input-x", type=int, required=True)
    send_click.add_argument("--input-y", type=int, required=True)
    send_click.add_argument("--send-x", type=int)
    send_click.add_argument("--send-y", type=int)

    chat_sub.add_parser("read")
    chat_sub.add_parser("state")
    chat_sub.add_parser("new")

    frames = chat_sub.add_parser("read-frames")
    frames.add_argument("--frames", type=int, default=4)
    frames.add_argument("--delay", type=float, default=0.35)

    read_scroll = chat_sub.add_parser("read-scroll")
    read_scroll.add_argument("--direction", choices=["up", "down"], default="down")
    read_scroll.add_argument("--steps", type=int, default=3)
    read_scroll.add_argument("--delay", type=float, default=0.7)

    reply_new = chat_sub.add_parser("reply-new")
    reply_new.add_argument("message")
    reply_new.add_argument("--input-x", type=int)
    reply_new.add_argument("--input-y", type=int)
    reply_new.add_argument("--send-x", type=int)
    reply_new.add_argument("--send-y", type=int)

    window = sub.add_parser("window", help="Window actions")
    window_sub = window.add_subparsers(dest="window_cmd", required=True)

    focus = window_sub.add_parser("focus")
    focus.add_argument("name")

    window_sub.add_parser("list")

    browser = sub.add_parser("browser", help="Browser actions")
    browser_sub = browser.add_subparsers(dest="browser_cmd", required=True)
    browser_sub.add_parser("chatgpt")
    browser_sub.add_parser("youtube")
    browser_sub.add_parser("google")
    browser_open = browser_sub.add_parser("open")
    browser_open.add_argument("url")
    browser_search_google = browser_sub.add_parser("search-google")
    browser_search_google.add_argument("query")
    browser_search_youtube = browser_sub.add_parser("search-youtube")
    browser_search_youtube.add_argument("query")
    browser_sub.add_parser("focus")

    screen = sub.add_parser("screen", help="Screen actions")
    screen_sub = screen.add_subparsers(dest="screen_cmd", required=True)

    see = screen_sub.add_parser("see")
    see.add_argument("--colored", action="store_true")
    see.add_argument("--full", action="store_true")

    shot = screen_sub.add_parser("shot")
    shot.add_argument("--path")

    compat = sub.add_parser("compat", help="Compatibility helpers")
    compat_sub = compat.add_subparsers(dest="compat_cmd", required=True)
    compat_sub.add_parser("self-test")
    compat_sub.add_parser("auto-configure")

    return parser


def indicator_command(args):
    return [
        sys.executable,
        "-m",
        "pc_remote_agent.indicator",
        "--width",
        str(args.indicator_width),
        "--height",
        str(args.indicator_height),
        "--x",
        str(args.indicator_x),
        "--y",
        str(args.indicator_y),
        "--label",
        args.indicator_label,
    ]


def start_indicator(args):
    if args.headless:
        return None
    env = os.environ.copy()
    project_root = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = project_root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    try:
        return subprocess.Popen(
            indicator_command(args),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
    except Exception:
        return None


def stop_indicator(proc):
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        proc.kill()


def command_label(args):
    if args.command == "raw":
        return f"raw {args.line}"
    if args.command == "batch":
        return f"batch {len(args.commands)}"
    parts = [args.command]
    for key in (
        "mouse_cmd",
        "text_cmd",
        "chat_cmd",
        "window_cmd",
        "browser_cmd",
        "screen_cmd",
        "compat_cmd",
        "session_cmd",
    ):
        value = getattr(args, key, None)
        if value:
            parts.append(value)
    return " ".join(parts)


def selected_subcommand(args):
    for key in (
        "mouse_cmd",
        "text_cmd",
        "chat_cmd",
        "window_cmd",
        "browser_cmd",
        "screen_cmd",
        "compat_cmd",
        "session_cmd",
    ):
        value = getattr(args, key, None)
        if value:
            return value
    if args.command == "batch":
        return "run"
    return None


def ensure_session_state(args):
    if args.trust_session:
        write_session_consent(True, detail="trusted by --trust-session")
    consent = read_session_consent()
    if os.environ.get("PC_REMOTE_REQUIRE_TRUST") == "1" and args.command not in {"session"} and not consent.get("trusted"):
        write_bridge_state("blocked", command_label(args), error="Trusted session required")
        print("Sessao ainda nao confiada. Rode: python3 -m pc_remote_agent session grant")
        return None
    return consent


def check_policy(args):
    subcommand = selected_subcommand(args)
    if not command_allowed(args.command, subcommand):
        write_bridge_state("blocked", command_label(args), error="Command blocked by whitelist")
        print("Comando bloqueado pela whitelist de seguranca.")
        return False
    if args.command == "raw" and not raw_command_allowed(args.line):
        write_bridge_state("blocked", f"raw {args.line}", error="Raw command blocked by whitelist")
        print("Comando bruto bloqueado pela whitelist de seguranca.")
        return False
    return True


def execute_parsed_command(args, agent, parser):
    label = command_label(args)

    if args.command == "session":
        if args.session_cmd == "grant":
            payload = write_session_consent(True, detail="trusted by session grant")
            print(f"Sessao confiada: {payload['trusted']}")
            return 0
        if args.session_cmd == "revoke":
            payload = write_session_consent(False, detail="revoked by session revoke")
            print(f"Sessao confiada: {payload['trusted']}")
            return 0
        if args.session_cmd == "status":
            payload = read_session_consent()
            print(f"trusted={payload.get('trusted', False)} updated_at={payload.get('updated_at', '')}")
            return 0

    if args.command == "batch":
        failed = []
        for index, command_line in enumerate(args.commands, start=1):
            tokens = shlex.split(command_line)
            nested_args = parser.parse_args(tokens)
            if not check_policy(nested_args):
                failed.append((index, command_line, 1))
                continue
            status = execute_parsed_command(nested_args, agent, parser)
            if status != 0:
                failed.append((index, command_line, status))
        if failed:
            joined = "; ".join(f"{index}:{line}" for index, line, _ in failed)
            write_bridge_state("failed", label, error=f"Batch failed on {joined}")
            print(f"Lote com falhas: {joined}")
            return 1
        write_bridge_state("completed", label, detail=f"Batch finished with {len(args.commands)} commands")
        return 0

    if args.command == "raw":
        result = agent.run_raw(args.line)
        write_bridge_state("completed", label, detail="Raw command finished")
        return 0 if result is not False else 1

    if args.command == "mouse":
        if args.mouse_cmd == "click":
            result = agent.mouse.click(args.x, args.y, button=args.button)
        elif args.mouse_cmd == "move":
            result = agent.mouse.move_to(args.x, args.y, duration=args.duration)
        elif args.mouse_cmd == "scroll":
            result = agent.mouse.scroll(args.amount)
        else:
            print(agent.mouse.position())
            result = True
        write_bridge_state("completed", label, detail="Mouse command finished")
        return 0 if result is not False else 1

    if args.command == "text":
        if args.text_cmd == "type":
            result = agent.keyboard.type_text(args.value, speed=args.speed)
        elif args.text_cmd == "key":
            result = agent.keyboard.press(args.value)
        elif args.text_cmd == "hotkey":
            result = agent.keyboard.hotkey(args.value)
        elif args.text_cmd == "copy":
            result = agent.keyboard.copy()
        elif args.text_cmd == "paste":
            result = agent.keyboard.paste()
        elif args.text_cmd == "undo":
            result = agent.keyboard.undo()
        elif args.text_cmd == "select-all":
            result = agent.keyboard.select_all()
        else:
            result = agent.keyboard.alt_tab(count=args.count)
        write_bridge_state("completed", label, detail="Keyboard command finished")
        return 0 if result is not False else 1

    if args.command == "chat":
        if args.chat_cmd == "send":
            result = agent.chat.send(args.message)
        elif args.chat_cmd == "send-click":
            result = agent.chat.send_via_click(
                args.message,
                input_x=args.input_x,
                input_y=args.input_y,
                send_x=args.send_x,
                send_y=args.send_y,
            )
        elif args.chat_cmd == "read":
            result = agent.chat.read()
        elif args.chat_cmd == "state":
            result = agent.chat.state()
        elif args.chat_cmd == "new":
            result = agent.chat.new()
        elif args.chat_cmd == "read-frames":
            result = agent.chat.read_frames(frames=args.frames, delay=args.delay)
        elif args.chat_cmd == "read-scroll":
            result = agent.chat.read_scroll(direction=args.direction, steps=args.steps, delay=args.delay)
        else:
            result = agent.chat.reply_new(
                args.message,
                input_x=args.input_x,
                input_y=args.input_y,
                send_x=args.send_x,
                send_y=args.send_y,
            )
        write_bridge_state("completed", label, detail="Chat command finished")
        return 0 if result is not False else 1

    if args.command == "window":
        if args.window_cmd == "focus":
            result = agent.windows.focus(args.name)
            write_bridge_state("completed", label, detail="Window focus finished")
            return 0 if result is not False else 1
        for wid, name in agent.windows.list():
            print(f"{wid}\t{name}")
        write_bridge_state("completed", label, detail="Window list finished")
        return 0

    if args.command == "browser":
        if args.browser_cmd == "chatgpt":
            result = agent.browser.open_chatgpt()
        elif args.browser_cmd == "youtube":
            result = agent.browser.open_youtube()
        elif args.browser_cmd == "google":
            result = agent.browser.open_google()
        elif args.browser_cmd == "open":
            result = agent.browser.open(args.url)
        elif args.browser_cmd == "search-google":
            result = agent.browser.search_google(args.query)
        elif args.browser_cmd == "search-youtube":
            result = agent.browser.search_youtube(args.query)
        else:
            result = agent.browser.focus_browser()
        write_bridge_state("completed", label, detail="Browser command finished")
        return 0 if result is not False else 1

    if args.command == "screen":
        if args.screen_cmd == "see":
            result = agent.screen.see(colored=args.colored, full=args.full)
        else:
            result = agent.screen.screenshot(args.path)
        write_bridge_state("completed", label, detail="Screen command finished")
        return 0 if result is not False else 1

    if args.command == "compat":
        if args.compat_cmd == "self-test":
            result = agent.legacy.self_test()
        else:
            result = agent.legacy.auto_configure()
        write_bridge_state("completed", label, detail="Compatibility command finished")
        return 0 if result is not False else 1

    return 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    label = command_label(args)

    if ensure_session_state(args) is None:
        return 1
    if not check_policy(args):
        return 1

    agent = None
    indicator = start_indicator(args)
    write_bridge_state("running", label, detail="CLI accepted command")
    try:
        if args.command != "session":
            from .controller import DesktopAgent

            agent = DesktopAgent()
        return execute_parsed_command(args, agent, parser)
    except Exception as exc:
        message = friendly_error_message(exc)
        write_bridge_state("failed", label, error=message)
        print(message)
        return 1
    finally:
        stop_indicator(indicator)
