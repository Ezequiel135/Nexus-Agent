from .. import runtime
from ..vision import capture_chat_snapshot, capture_frame_sequence, export_state, read_scroll_history


class ScreenService:
    def __init__(self, module, actions):
        self.module = module
        self.actions = actions

    def see(self, colored=False, full=False):
        grid, width, height = runtime.pixel_grid(40 if full else 32, 20 if full else 18)
        mx, my = runtime.mouse_position()
        regions = runtime.analyze_regions(grid)

        print(f"\033[1;36m=== SCREEN ({width}x{height}) | Mouse: ({mx},{my}) ===\033[0m")
        for name, (r, g, b, label, sat) in regions.items():
            print(f"  \033[38;2;{r};{g};{b}m{name:14s} RGB({r},{g},{b}) {label} sat={sat}\033[0m")

        gw = 50 if full else None
        renderer = runtime.render_colored_ascii if colored else runtime.render_ascii
        print(f"\n\033[0;37m{renderer(grid, gw)}\033[0m")
        return grid, width, height

    def screenshot(self, where=None):
        img, width, height = runtime.screen_image()
        if where:
            img.save(where)
            print(f"  \033[1;32mSAVED screenshot to {where}\033[0m")
        else:
            print(f"  \033[1;32mScreenshot captured ({width}x{height})\033[0m")
        return img

    def get_windows(self):
        return runtime.visible_windows()

    def read_chat(self):
        snapshot = capture_chat_snapshot(timeout=2)
        print(f"\033[1;36m=== CHAT READ {snapshot['bounds']} source={snapshot['source']} ===\033[0m")
        print(f"  new_messages={len(snapshot.get('new_messages', []))} frame_hash={snapshot['frame_hash']}")
        if snapshot["messages"]:
            for item in snapshot["messages"][:30]:
                print(f"  [{item['role']}] {item['text']}")
        else:
            print("  \033[1;33mNo chat text detected\033[0m")
        return snapshot

    def read_chat_frames(self, frames=4, delay=0.35):
        print(f"\033[1;36m=== CHAT FRAMES ({frames}) ===\033[0m")
        results = capture_frame_sequence(frames=frames, delay=delay)
        for item in results:
            print(
                f"  Frame {item['index']}: hash={item['frame_hash']} repeated={item['repeated']} "
                f"new={len(item['new_ids'])} region={item['bounds']} source={item['source']}"
            )
            if item["messages"]:
                for message in item["messages"][:6]:
                    print(f"    [{message['role']}] {message['text']}")
            else:
                print("    <no text>")
        return results

    def read_scroll(self, direction="down", steps=3, delay=0.7):
        print(f"\033[1;36m=== READ SCROLL {direction} x{steps} ===\033[0m")
        history = read_scroll_history(direction=direction, steps=steps, delay=delay)
        for index, snapshot in enumerate(history, start=1):
            print(f"\n--- Step {index}/{steps} region={snapshot['bounds']} source={snapshot['source']} ---")
            if snapshot["messages"]:
                for item in snapshot["messages"][:8]:
                    print(f"  [{item['role']}] {item['text']}")
            else:
                print("  \033[1;33mNo text detected\033[0m")
        return history

    def chat_state(self):
        state = export_state()
        print(f"\033[1;36m=== CHAT STATE source={state['source']} ===\033[0m")
        print(
            f"  messages={len(state['messages'])} anchors={len(state['anchors'])} "
            f"replied={len(state['replied_ids'])} last_seen={state['last_seen_screen']}"
        )
        for item in state["messages"][-8:]:
            print(f"  [{item['role']}] {item['text']}")
        return state
