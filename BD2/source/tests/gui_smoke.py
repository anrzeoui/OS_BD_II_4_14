"""Optional desktop smoke test: python -m tests.gui_smoke [--screenshots].

Use a real desktop or Xvfb. Pillow is needed only for --screenshots.
"""
import argparse
import json
import os
from pathlib import Path
import tempfile
import tkinter as tk
from unittest.mock import patch
from src.gui import App


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", action="store_true")
    parser.add_argument("--show", action="store_true", help="Keep the validated app open for a live demonstration")
    parser.add_argument("--small", action="store_true", help="Show the 1000x800 layout")
    args = parser.parse_args()
    root = tk.Tk()
    app = App(root)
    root.update()
    checks = 0

    def check(value):
        nonlocal checks
        assert value
        checks += 1

    def capture(name):
        root.update()
        if args.screenshots:
            from PIL import ImageGrab
            bbox = (root.winfo_rootx(), root.winfo_rooty(),
                    root.winfo_rootx() + root.winfo_width(), root.winfo_rooty() + root.winfo_height())
            image = ImageGrab.grab(bbox=bbox, xdisplay=os.environ.get("DISPLAY"))
            image.save(Path("docs") / name)

    try:
        app.load_demo()
        for _ in range(4):
            app.step_demo()
        check(app.model.stats()["free"] == 500)
        check(len(app.table.get_children()) == len(app.model.blocks))
        capture("memory-fragmented.png")
        before = app.model.snapshot()
        app.step_demo()
        check(not app.history[-1]["ok"])
        check(app.model.snapshot() == before)
        capture("memory-rejected.png")
        app.step_demo()
        check(app.model.stats()["holes"] == 1)
        capture("memory-compacted.png")
        app.step_demo()
        check(app.model.stats()["used"] == 900)
        capture("memory-final.png")
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "history.json")
            with patch("src.gui.filedialog.asksaveasfilename", return_value=path):
                app.export()
            data = json.loads(Path(path).read_text())
            check(data["state"] == app.model.snapshot())
            check(len(data["history"]) == 7)
        app.total.set("bad")
        before = app.model.snapshot()
        app.reset()
        check(app.model.snapshot() == before)
        app.total.set("1500")
        app.reset()
        check(app.model.stats()["free"] == 1500 and not app.history)
        app.load_demo()
        app.play_demo()
        check(app.timer is not None and app.running)
        app.stop_demo()
        check(app.timer is None and not app.running)
        app.manual_command("RQ P9 50 B")
        check(app.demo_index is None)
        app.root.geometry("1000x800")
        capture("memory-minimum-window.png")
        check(app.canvas.winfo_width() > 600)
        # New functionality: deterministic back step, preview isolation and modes.
        app.load_demo()
        for _ in range(5): app.step_demo()
        failed_state = app.model.snapshot()
        app.back_demo()
        check(app.demo_index == 4 and app.model.snapshot() == failed_state)
        check(len(app.history) == 4)
        app.step_demo()
        check(not app.history[-1]["ok"])
        app.step_demo()
        check(app.model.stats()["largest_hole"] == 500)
        app.back_demo()
        check(app.model.snapshot() == failed_state)
        app.scenario.set("02  Гурван стратегийн ялгаа")
        app.load_demo()
        for _ in range(6): app.step_demo()
        before = app.model.snapshot()
        check([r["start"] for r in app.preview_rows] == [0, 500, 900])
        check(app.tabs.index(app.tabs.select()) == 1)
        app.strategy.set("B  Best Fit")
        check(app.model.snapshot() == before)
        check("500" in app.preview_label.cget("text"))
        app.size.set("bad")
        check(all(not r["ok"] for r in app.preview_rows))
        check(app.model.snapshot() == before)
        app.size.set("150")
        app.manual_command("RQ Q 150 B")
        check(next(b.start for b in app.model.blocks if b.pid == "Q") == 500)
        check(app.demo_index is None)
        app.scenario.set("03  Бүрэн дүүрэх ба чөлөөлөх")
        app.load_demo()
        app.step_demo(); app.step_demo()
        check(app.model.stats()["free"] == 0)
        app.step_demo()
        check(not app.history[-1]["ok"])
        app.speed.set("300 ms")
        app.play_demo()
        timer = app.timer
        app.play_demo()
        check(app.timer == timer)  # No second timer from repeated play.
        app.stop_demo()
        check(app.timer is None and not app.running)
        app.load_demo()
        app.step_demo()
        app.back_demo()
        check(app.demo_index == 0 and not app.history)
        check(app.model.stats()["used"] == 0)
        print(f"GUI smoke: {checks} checks passed (demo, failure, compaction, export, reset, timer, minimum window, back step, comparison, preview, boundary).", flush=True)
        if args.show:
            app.scenario.set("01  Бутрал ба нягтруулалт")
            app.load_demo()
            app.strategy.set("F  First Fit")
            for _ in range(4): app.step_demo()
            root.geometry("1000x800" if args.small else "1340x880")
            root.mainloop()
    finally:
        try: app.close()
        except tk.TclError: pass


if __name__ == "__main__":
    main()
