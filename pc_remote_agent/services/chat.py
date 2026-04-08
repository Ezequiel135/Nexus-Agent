from .. import runtime
from ..resilience import execute_with_verification, has_ready_anchor
from ..vision import capture_chat_snapshot, mark_replied, unreplied_messages


class ChatService:
    def __init__(self, screen, mouse, keyboard):
        self.screen = screen
        self.mouse = mouse
        self.keyboard = keyboard

    def read(self):
        return self.screen.read_chat()

    def state(self):
        return self.screen.chat_state()

    def read_frames(self, frames=4, delay=0.35):
        return self.screen.read_chat_frames(frames=frames, delay=delay)

    def read_scroll(self, direction="down", steps=3, delay=0.7):
        return self.screen.read_scroll(direction=direction, steps=steps, delay=delay)

    def send(self, text):
        self.keyboard.type_text(text)
        return self.keyboard.press("enter")

    def send_via_click(self, text, input_x, input_y, send_x=None, send_y=None):
        self.mouse.click(input_x, input_y)
        self.keyboard.type_text(text)
        if send_x is not None and send_y is not None:
            return self.mouse.click(send_x, send_y)
        return self.keyboard.press("enter")

    def new(self):
        items = unreplied_messages()
        for item in items:
            print(f"[{item['role']}] {item['text']}")
        return items

    def reply_new(self, text, input_x=None, input_y=None, send_x=None, send_y=None):
        pending = unreplied_messages()
        if not pending:
            print("Nenhuma mensagem nova pendente.")
            return {"ok": True, "sent": False, "reason": "no_new_messages"}

        def action():
            if input_x is not None and input_y is not None:
                self.mouse.click(input_x, input_y)
            self.keyboard.type_text(text)
            runtime.human_delay(0.35, 0.8)
            if send_x is not None and send_y is not None:
                self.mouse.click(send_x, send_y)
            else:
                self.keyboard.press("enter")

        result = execute_with_verification(
            "chat reply-new",
            action,
            capture_chat_snapshot,
            ready_fn=has_ready_anchor,
        )
        if result["ok"]:
            mark_replied([item["id"] for item in pending])
        return result
