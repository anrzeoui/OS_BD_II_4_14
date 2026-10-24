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
        app.root.geometry("960x800")
        capture("memory-minimum-window.png")
        check(app.canvas.winfo_width() > 900)
        print(f"GUI smoke: {checks} checks passed (demo, failure, compaction, export, reset, timer, minimum window).")
    finally:
        app.close()


if __name__ == "__main__":
    main()
