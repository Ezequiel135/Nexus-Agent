import json
import os
import urllib.error
import urllib.request


SELECTORS = [
    "[data-message-author-role]",
    "[data-testid*='conversation-turn']",
    "main [role='article']",
]


def _json_get(url, timeout=1.5):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def discover_debug_endpoint():
    for port in (9222, 9223, 9333):
        try:
            data = _json_get(f"http://127.0.0.1:{port}/json/version")
            ws = data.get("webSocketDebuggerUrl")
            if ws:
                return ws
        except Exception:
            continue
    return None


def extract_dom_messages():
    if os.environ.get("PC_REMOTE_ENABLE_DOM", "0") != "1":
        return None
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None

    endpoint = discover_debug_endpoint()
    if not endpoint:
        return None

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(endpoint)
            contexts = browser.contexts
            if not contexts:
                browser.close()
                return None
            page = None
            for ctx in contexts:
                for candidate in ctx.pages:
                    try:
                        if candidate.is_closed():
                            continue
                        page = candidate
                        break
                    except Exception:
                        continue
                if page is not None:
                    break
            if page is None:
                browser.close()
                return None

            script = """
            () => {
              const selectors = %s;
              for (const selector of selectors) {
                const nodes = Array.from(document.querySelectorAll(selector));
                if (!nodes.length) continue;
                const items = nodes.map((node, index) => {
                  const text = (node.innerText || '').trim();
                  const role = node.getAttribute('data-message-author-role') || node.getAttribute('data-testid') || 'unknown';
                  const rect = node.getBoundingClientRect();
                  return {id: `${role}-${index}`, role, text, position: [Math.round(rect.x), Math.round(rect.y)]};
                }).filter(item => item.text);
                if (items.length) return items;
              }
              return [];
            }
            """ % json.dumps(SELECTORS)
            messages = page.evaluate(script)
            browser.close()
            return messages or None
    except Exception:
        return None
