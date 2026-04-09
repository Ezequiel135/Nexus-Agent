import os
import platform
import random
import shutil
import subprocess
import time
from pathlib import Path

import mss
import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.02

SYSTEM = platform.system().lower()
DEFAULT_CMD_TIMEOUT = 3
DEFAULT_OCR_TIMEOUT = 4
CHAT_REGION = (0.28, 0.16, 0.90, 0.88)
HUMAN_MOVE_BASE = 0.16
HUMAN_MOVE_VAR = 0.18
HUMAN_CLICK_PAUSE = (0.03, 0.09)
HUMAN_TYPE_BASE = (0.018, 0.055)
HUMAN_ACTION_DELAY = (0.35, 0.95)
BROWSER_ALIASES = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "google-chrome": "chrome",
    "google-chrome-stable": "chrome",
    "chromium": "chromium",
    "chromium-browser": "chromium",
    "firefox": "firefox",
    "mozilla firefox": "firefox",
    "edge": "edge",
    "microsoft edge": "edge",
    "microsoft-edge": "edge",
    "microsoft-edge-stable": "edge",
}
BROWSER_WINDOW_TITLES = {
    "chrome": ("google chrome", "chrome"),
    "chromium": ("chromium",),
    "firefox": ("firefox",),
    "edge": ("microsoft edge", "edge"),
}
BROWSER_COMMANDS = {
    "linux": {
        "chrome": [["google-chrome-stable"], ["google-chrome"], ["chrome"]],
        "chromium": [["chromium-browser"], ["chromium"]],
        "firefox": [["firefox"]],
        "edge": [["microsoft-edge"], ["microsoft-edge-stable"]],
    },
    "windows": {
        "chrome": [
            ["chrome"],
            [r"C:\Program Files\Google\Chrome\Application\chrome.exe"],
            [r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"],
        ],
        "firefox": [
            ["firefox"],
            [r"C:\Program Files\Mozilla Firefox\firefox.exe"],
            [r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"],
        ],
        "edge": [
            ["msedge"],
            [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"],
            [r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"],
        ],
    },
    "darwin": {
        "chrome": [["open", "-a", "Google Chrome"]],
        "firefox": [["open", "-a", "Firefox"]],
        "edge": [["open", "-a", "Microsoft Edge"]],
    },
}
BROWSER_ORDER = ("chrome", "chromium", "firefox", "edge")
BLOCKED_BROWSER_VALUES = {"default", "system", "brave", "brave-browser", "brave.exe"}


def run_command(cmd, timeout=DEFAULT_CMD_TIMEOUT, check=False):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
    )


def platform_name():
    return SYSTEM


def visible_windows(limit=30):
    if SYSTEM == "windows":
        return _windows_visible_windows(limit=limit)
    if SYSTEM == "linux":
        return _linux_visible_windows(limit=limit)
    return []


def _linux_visible_windows(limit=30):
    try:
        result = run_command(["xdotool", "search", "--onlyvisible", "--name", ".*"])
    except Exception:
        return []

    windows = []
    seen = set()
    for wid in result.stdout.strip().splitlines()[-limit:]:
        wid = wid.strip()
        if not wid or wid in seen:
            continue
        seen.add(wid)
        try:
            name = run_command(["xdotool", "getwindowname", wid]).stdout.strip()
        except Exception:
            continue
        if name:
            windows.append((wid, name))
    return windows


def _windows_visible_windows(limit=30):
    try:
        import ctypes
        user32 = ctypes.windll.user32
        windows = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def enum_proc(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()
            if title:
                windows.append((str(int(hwnd)), title))
            return True

        user32.EnumWindows(enum_proc, 0)
        return windows[-limit:]
    except Exception:
        return []


def focus_window(name):
    if SYSTEM == "windows":
        return _windows_focus_window(name)
    if SYSTEM == "linux":
        return _linux_focus_window(name)
    return False


def _linux_focus_window(name):
    for wid, wname in visible_windows():
        if name.lower() in wname.lower():
            run_command(["xdotool", "windowactivate", wid])
            run_command(["xdotool", "windowfocus", wid])
            time.sleep(0.3)
            return True
    return False


def _windows_focus_window(name):
    try:
        import ctypes
        user32 = ctypes.windll.user32

        target = None

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def enum_proc(hwnd, _lparam):
            nonlocal target
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()
            if name.lower() in title.lower():
                target = hwnd
                return False
            return True

        user32.EnumWindows(enum_proc, 0)
        if target:
            user32.SetForegroundWindow(target)
            time.sleep(0.3)
            return True
    except Exception:
        return False
    return False


def focused_window_name():
    if SYSTEM == "windows":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            return buffer.value.strip()
        except Exception:
            return ""
    try:
        return run_command(["xdotool", "getwindowfocus", "getwindowname"]).stdout.strip()
    except Exception:
        return ""


def mouse_position():
    return pyautogui.position()


def _human_sleep(low, high):
    time.sleep(random.uniform(low, high))


def human_delay(low=None, high=None):
    low = HUMAN_ACTION_DELAY[0] if low is None else low
    high = HUMAN_ACTION_DELAY[1] if high is None else high
    _human_sleep(low, high)


def _human_move_duration(src_x, src_y, dst_x, dst_y, duration=None):
    if duration is not None:
        return duration
    distance = ((dst_x - src_x) ** 2 + (dst_y - src_y) ** 2) ** 0.5
    scaled = HUMAN_MOVE_BASE + min(distance / 900.0, 0.35)
    return scaled + random.uniform(0.0, HUMAN_MOVE_VAR)


def move_to(x, y, duration=None):
    px, py = mouse_position()
    pyautogui.moveTo(x, y, duration=_human_move_duration(px, py, x, y, duration))


def click(x=None, y=None, button="left", clicks=1):
    px, py = mouse_position()
    cx = x if x is not None else px
    cy = y if y is not None else py
    move_to(cx, cy)
    _human_sleep(*HUMAN_CLICK_PAUSE)
    pyautogui.click(cx, cy, button=button, clicks=clicks, interval=0.12 if clicks > 1 else 0.0)
    return cx, cy


def drag_to(x1, y1, x2, y2, duration=0.5):
    move_to(x1, y1)
    _human_sleep(0.12, 0.24)
    pyautogui.dragTo(x2, y2, duration=max(duration, 0.25), button="left")


def scroll(amount):
    pyautogui.scroll(amount)


def type_text(text, speed=0.03):
    human_delay(0.2, 0.5)
    interval = speed if speed != 0.03 else random.uniform(*HUMAN_TYPE_BASE)
    pyautogui.typewrite(text, interval=interval)


def press(key):
    _human_sleep(0.02, 0.07)
    pyautogui.press(key)


def hotkey(keys):
    _human_sleep(0.03, 0.08)
    if isinstance(keys, str):
        keys = keys.split("+")
    pyautogui.hotkey(*keys)


def _normalize_browser_name(value):
    return BROWSER_ALIASES.get((value or "").strip().lower(), (value or "").strip().lower())


def _browser_search_order():
    requested = os.environ.get("NEXUS_BROWSER", "").strip().lower()
    if requested in BLOCKED_BROWSER_VALUES:
        raise RuntimeError("NEXUS_BROWSER nao pode usar navegador padrao nem Brave. Use chrome, chromium, firefox ou edge.")
    alias = _normalize_browser_name(requested)
    if not alias:
        return list(BROWSER_ORDER)
    if alias not in BROWSER_ORDER:
        raise RuntimeError("Browser nao suportado. Use chrome, chromium, firefox ou edge.")
    return [alias]


def _command_exists(command):
    executable = command[0]
    if executable == "open":
        return shutil.which("open") is not None
    return Path(executable).exists() or shutil.which(executable) is not None


def resolve_browser_command():
    commands = BROWSER_COMMANDS.get(SYSTEM, {})
    for alias in _browser_search_order():
        for command in commands.get(alias, []):
            if _command_exists(command):
                return alias, command
    return None, None


def browser_window_candidates():
    preferred_aliases = _browser_search_order()
    names = []
    for alias in preferred_aliases:
        names.extend(BROWSER_WINDOW_TITLES.get(alias, ()))
    for alias in BROWSER_ORDER:
        if alias in preferred_aliases:
            continue
        names.extend(BROWSER_WINDOW_TITLES.get(alias, ()))
    return tuple(dict.fromkeys(names))


def open_url(url):
    alias, command = resolve_browser_command()
    if not command:
        raise RuntimeError(
            "Nenhum navegador suportado foi encontrado. Instale Chrome, Chromium, Firefox ou Edge, ou defina NEXUS_BROWSER."
        )
    subprocess.Popen(command + [url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return alias


def open_application(command_or_url):
    if command_or_url.startswith(("http://", "https://")):
        return open_url(command_or_url)
    if SYSTEM == "windows":
        subprocess.Popen(command_or_url, shell=True)
        return True
    subprocess.Popen(command_or_url.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def save_error_capture(prefix="visual_error"):
    img, _, _ = screen_image()
    out_dir = Path(__file__).resolve().parents[1] / "runtime" / "errors"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = int(time.time() * 1000)
    path = out_dir / f"{prefix}_{stamp}.png"
    img.save(path)
    return str(path)


def screen_image():
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[-1] if len(sct.monitors) > 2 else sct.monitors[0])
    import PIL.Image

    img = PIL.Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    return img, raw.size[0], raw.size[1]


def detect_chat_region_from_image(img):
    width, height = img.size
    gray = img.convert("L")

    # Look for the input bar near the lower center-right area.
    y_start = int(height * 0.72)
    y_end = int(height * 0.96)
    x_start = int(width * 0.22)
    x_end = int(width * 0.94)

    best_row = None
    best_score = -1
    for y in range(y_start, y_end, 4):
        row = [gray.getpixel((x, y)) for x in range(x_start, x_end, 6)]
        if not row:
            continue
        darkness = sum(255 - px for px in row) / len(row)
        smoothness = 255 - max(row) + min(row)
        score = darkness + smoothness
        if score > best_score:
            best_score = score
            best_row = y

    if best_row is None:
        return (
            int(width * 0.28),
            int(height * 0.14),
            int(width * 0.90),
            int(height * 0.88),
        )

    top = max(int(height * 0.10), best_row - int(height * 0.63))
    bottom = min(int(height * 0.93), best_row + int(height * 0.05))
    left = int(width * 0.28)
    right = int(width * 0.90)
    return (left, top, right, bottom)


def pixel_grid(grid_w=32, grid_h=18):
    img, width, height = screen_image()
    small = img.resize((grid_w, grid_h))
    grid = []
    for y in range(grid_h):
        row = []
        for x in range(grid_w):
            row.append(small.getpixel((x, y)))
        grid.append(row)
    return grid, width, height


def render_ascii(grid, width=None):
    chars = " .:-+%O@"
    out = ""
    for row in grid:
        for r, g, b in row[:width]:
            br = (r + g + b) // 3
            out += chars[min(br * 6 // 255, 6)]
        out += "\n"
    return out


def render_colored_ascii(grid, width=None):
    chars = " .:-+%O@"
    out = ""
    for row in grid:
        for r, g, b in row[:width]:
            br = (r + g + b) // 3
            c = chars[min(br * 6 // 255, 6)]
            out += f"\033[38;2;{r};{g};{b}m{c}"
        out += "\033[0m\n"
    return out


def analyze_regions(grid=None):
    if grid is None:
        grid, _, _ = pixel_grid()
    gh = len(grid)
    gw = len(grid[0]) if grid else 0
    results = {}
    for name, (r1, c1, r2, c2) in [
        ("top_bar", (0, 0, max(1, gh // 6), gw)),
        ("top_left", (0, 0, gh // 3, gw // 3)),
        ("top_right", (0, 2 * gw // 3, gh // 3, gw)),
        ("center", (gh // 4, gw // 4, 3 * gh // 4, 3 * gw // 4)),
        ("bottom_left", (2 * gh // 3, 0, gh, gw // 3)),
        ("bottom_right", (2 * gh // 3, 2 * gw // 3, gh, gw)),
        ("bottom_bar", (5 * gh // 6, 0, gh, gw)),
    ]:
        tr = tg = tb = cnt = max_sat = 0
        for y in range(r1, min(r2, gh)):
            for x in range(c1, min(c2, gw)):
                r, g, b = grid[y][x]
                tr += r
                tg += g
                tb += b
                cnt += 1
                mx = max(r, g, b)
                mn = min(r, g, b)
                sat = (mx - mn) * 255 // max(mx, 1)
                if sat > max_sat:
                    max_sat = sat
        if cnt == 0:
            results[name] = (0, 0, 0, "preto", 0)
            continue
        br = (tr + tg + tb) // (3 * cnt)
        label = "preto" if br < 30 else "escuro" if br < 80 else "medio" if br < 150 else "claro" if br < 220 else "branco"
        results[name] = (tr // cnt, tg // cnt, tb // cnt, label, max_sat)
    return results


def resolve_region(region, width, height):
    if not region:
        return (0, 0, width, height)
    x1, y1, x2, y2 = region
    if all(isinstance(v, float) and 0.0 <= v <= 1.0 for v in region):
        return (
            int(width * x1),
            int(height * y1),
            int(width * x2),
            int(height * y2),
        )
    return tuple(int(v) for v in region)


def region_image(region=None):
    img, width, height = screen_image()
    bounds = resolve_region(region, width, height)
    return img.crop(bounds), bounds, width, height


def preprocess_for_ocr(img, invert="auto", scale=2):
    import PIL.ImageFilter
    import PIL.ImageOps
    import PIL.ImageStat

    gray = img.convert("L")
    if scale and scale > 1:
        gray = gray.resize((gray.width * scale, gray.height * scale))
    gray = gray.filter(PIL.ImageFilter.SHARPEN)
    mean = PIL.ImageStat.Stat(gray).mean[0]
    if invert == "auto":
        invert = mean < 128
    if invert:
        gray = PIL.ImageOps.invert(gray)
    threshold = 165 if mean < 90 else 145 if mean < 150 else 135
    return gray.point(lambda px: 255 if px > threshold else 0)


def image_to_text(img, timeout=DEFAULT_OCR_TIMEOUT, psm=6):
    try:
        import pytesseract

        config = f"--psm {psm}"
        text = pytesseract.image_to_string(img, lang="por+eng", config=config, timeout=timeout)
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line)
    except Exception:
        return ""


def best_ocr_text(img, timeout=DEFAULT_OCR_TIMEOUT):
    candidates = [
        image_to_text(img, timeout=min(timeout, 2), psm=11),
        image_to_text(preprocess_for_ocr(img, invert=False), timeout=min(timeout, 2), psm=6),
        image_to_text(preprocess_for_ocr(img, invert=True), timeout=min(timeout, 2), psm=6),
        image_to_text(preprocess_for_ocr(img, invert="auto", scale=3), timeout=min(timeout, 2), psm=11),
    ]
    segmented = segmented_ocr_text(img, timeout=min(timeout, 2), segments=5, overlap=0.18)
    if segmented:
        candidates.append(segmented)
    scored = []
    for text in candidates:
        score = sum(ch.isalnum() for ch in text)
        scored.append((score, len(text), text))
    scored.sort(reverse=True)
    return scored[0][2] if scored else ""


def segmented_ocr_text(img, timeout=2, segments=4, overlap=0.15):
    width, height = img.size
    if height < 120:
        return ""

    chunk_h = max(height // segments, 80)
    step = max(int(chunk_h * (1.0 - overlap)), 40)
    texts = []
    seen = set()
    top = 0
    while top < height:
        bottom = min(height, top + chunk_h)
        crop = img.crop((0, top, width, bottom))
        chunk_texts = [
            image_to_text(crop, timeout=timeout, psm=6),
            image_to_text(preprocess_for_ocr(crop, invert="auto", scale=2), timeout=timeout, psm=6),
        ]
        for chunk_text in chunk_texts:
            for line in [line.strip() for line in chunk_text.splitlines() if line.strip()]:
                key = line.lower()
                if key not in seen:
                    seen.add(key)
                    texts.append(line)
        if bottom >= height:
            break
        top += step
    return "\n".join(texts)


def read_chat_region(timeout=DEFAULT_OCR_TIMEOUT, region=CHAT_REGION):
    img, bounds, _, _ = region_image(region)
    return best_ocr_text(img, timeout=timeout), bounds


def capture_frame_sequence(frames=4, delay=0.35, region=CHAT_REGION, out_dir=None):
    import PIL.ImageChops

    out_path = Path(out_dir or "/tmp/pc_remote_frames")
    out_path.mkdir(parents=True, exist_ok=True)
    results = []
    previous = None
    for index in range(frames):
        img, bounds, _, _ = region_image(region)
        frame_path = out_path / f"frame_{index + 1:02d}.png"
        img.save(frame_path)
        text = image_to_text(preprocess_for_ocr(img), timeout=2, psm=6)
        changed = None
        if previous is not None:
            a = preprocess_for_ocr(previous, scale=1)
            b = preprocess_for_ocr(img, scale=1)
            diff_img = PIL.ImageChops.difference(a, b)
            changed = sum(diff_img.histogram()[1:])
        results.append((frame_path, bounds, text, changed))
        previous = img
        if index < frames - 1:
            time.sleep(delay)
    return results


def scroll_down(steps=5, delay=0.15):
    for _ in range(steps):
        pyautogui.scroll(-120)
        time.sleep(delay + 0.04)


def scroll_up(steps=5, delay=0.15):
    for _ in range(steps):
        pyautogui.scroll(120)
        time.sleep(delay + 0.04)
