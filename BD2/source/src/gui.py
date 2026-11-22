"""Memory Lab 2: one allocator, inspectable steps and non-mutating previews."""
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from .allocator import Allocator, AllocationError, execute
from .preview import compare_request
from .scenarios import SCENARIOS

VERSION = "2.0.0"
BG, INK, MUTED, TEAL = "#eef2f5", "#162d42", "#536778", "#087e8b"
PALETTE = ["#087e8b", "#376e9d", "#715b8e", "#8e5d69", "#967044", "#4b8072"]


class App:
    def __init__(self, root):
        self.root = root
        root.title("Memory Lab 2 | II-4-14")
        root.geometry("1340x880")
        root.minsize(1000, 800)
        root.configure(bg=BG)
        self.model, self.history, self.colors = Allocator(1000), [], {}
        self.demo_index, self.timer, self.running = None, None, False
        self.scenario_key = "fragmentation"
        self.preview_rows = []
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK, font=("DejaVu Sans", 10))
        style.configure("TButton", font=("DejaVu Sans", 10), padding=(8, 4))
        style.configure("Accent.TButton", background=TEAL, foreground="white")
        style.map("Accent.TButton", background=[("active", "#066571")])
        style.configure("Treeview", rowheight=29, font=("DejaVu Sans", 10), background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("DejaVu Sans", 10, "bold"), padding=7)
        style.configure("TNotebook.Tab", padding=(14, 8), font=("DejaVu Sans", 10))
        style.configure("TProgressbar", background=TEAL)
        head = tk.Frame(root, bg=INK, padx=22, pady=13)
        head.pack(fill="x")
        tk.Label(head, text="MEMORY LAB  /  02", bg=INK, fg="#78d7dc", font=("DejaVu Sans", 11, "bold")).pack(anchor="w")
        tk.Label(head, text="Залгаа санах ой хуваарилалт", bg=INK, fg="white", font=("DejaVu Sans", 22, "bold")).pack(side="left", pady=(4, 0))
        body = ttk.Frame(root, padding=16)
        body.pack(fill="both", expand=True)
        side = ttk.Frame(body, width=278)
        side.pack(side="left", fill="y", padx=(0, 16))
        side.pack_propagate(False)
        main = ttk.Frame(body)
        main.pack(side="left", fill="both", expand=True)
        self.total = tk.StringVar(value="1000")
        self.pid, self.size = tk.StringVar(value="P3"), tk.StringVar(value="400")
        self.strategy = tk.StringVar(value="F  First Fit")
        self.scenario = tk.StringVar(value=SCENARIOS[self.scenario_key]["name"])
        self.speed = tk.StringVar(value="900 ms")
        self.command = tk.StringVar(value="STAT")

        def title(text):
            ttk.Label(side, text=text, font=("DejaVu Sans", 10, "bold")).pack(anchor="w", pady=(8, 5))
        title("01   САНАХ ОЙ")
        row = ttk.Frame(side); row.pack(fill="x")
        ttk.Entry(row, textvariable=self.total, width=12).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Reset", command=self.reset).pack(side="right", padx=(6, 0))
        ttk.Label(side, text="Bytes • Reset нь төлөв, түүхийг цэвэрлэнэ.", font=("DejaVu Sans", 9), foreground=MUTED).pack(anchor="w", pady=4)
        title("02   ХҮСЭЛТ ТУРШИХ")
        row = ttk.Frame(side); row.pack(fill="x")
        for text, var, width in [("PID", self.pid, 9), ("Bytes", self.size, 9)]:
            col = ttk.Frame(row); col.pack(side="left", fill="x", expand=True, padx=(0, 6))
            ttk.Label(col, text=text, foreground=MUTED).pack(anchor="w")
            ttk.Entry(col, textvariable=var, width=width).pack(fill="x", pady=(3, 7))
        ttk.Combobox(side, textvariable=self.strategy, values=["F  First Fit", "B  Best Fit", "W  Worst Fit"], state="readonly").pack(fill="x")
        ttk.Button(side, text="RQ  •  Хуваарилах", style="Accent.TButton", command=lambda: self.manual_command(f"RQ {self.pid.get()} {self.size.get()} {self.strategy.get()[0]}")).pack(fill="x", pady=(8, 5))
        row = ttk.Frame(side); row.pack(fill="x")
        ttk.Button(row, text="RL • Чөлөөлөх", command=lambda: self.manual_command(f"RL {self.pid.get()}")).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ttk.Button(row, text="C • Нягтруулах", command=lambda: self.manual_command("C")).pack(side="left", fill="x", expand=True)
        self.preview_label = tk.Label(side, wraplength=272, height=3, bg=BG, fg=MUTED, anchor="nw", justify="left", font=("DejaVu Sans", 9))
        self.preview_label.pack(fill="x", pady=(8, 4))
        title("03   АЛХАМТ ЖИШЭЭ")
        ttk.Combobox(side, textvariable=self.scenario, values=[s["name"] for s in SCENARIOS.values()], state="readonly").pack(fill="x")
        ttk.Button(side, text="Жишээ ачаалах", command=self.load_demo).pack(fill="x", pady=6)
        row = ttk.Frame(side); row.pack(fill="x")
        self.back_button = ttk.Button(row, text="← Буцах", command=self.back_demo)
        self.back_button.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.step_button = ttk.Button(row, text="Алхам →", command=self.step_demo)
        self.step_button.pack(side="left", fill="x", expand=True)
        row = ttk.Frame(side); row.pack(fill="x", pady=5)
        self.play_button = ttk.Button(row, text="Тоглуулах", command=self.play_demo)
        self.play_button.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.pause_button = ttk.Button(row, text="Түр зогсоох", command=self.stop_demo)
        self.pause_button.pack(side="left", fill="x", expand=True)
        row = ttk.Frame(side); row.pack(fill="x")
        ttk.Label(row, text="Алхамын зай", foreground=MUTED).pack(side="left")
        ttk.Combobox(row, textvariable=self.speed, values=["300 ms", "900 ms", "1800 ms"], state="readonly", width=9).pack(side="right")
        self.progress_label = ttk.Label(side, foreground=MUTED, font=("DejaVu Sans", 9))
        self.progress_label.pack(anchor="w", pady=(4, 3))
        self.progress = ttk.Progressbar(side, maximum=1)
        self.progress.pack(fill="x")
        ttk.Label(side, text="Esc: түр зогсоох\nCtrl + Enter: команд ажиллуулах", foreground=MUTED, font=("DejaVu Sans", 9)).pack(anchor="w", pady=6)

        metrics = ttk.Frame(main); metrics.pack(fill="x")
        self.metric_labels = {}
        for i, (key, name) in enumerate([("used", "АШИГЛАСАН"), ("free", "СУЛ BYTES"), ("largest_hole", "ТОМ HOLE"), ("holes", "HOLE ТОО"), ("fragmentation", "БУТРАЛ")]):
            metrics.columnconfigure(i, weight=1, uniform="metric")
            card = tk.Frame(metrics, bg="white", padx=10, pady=10)
            card.grid(row=0, column=i, sticky="nsew", padx=(0, 6 if i < 4 else 0))
            tk.Label(card, text=name, bg="white", fg=MUTED, font=("DejaVu Sans", 9)).pack(anchor="w")
            value = tk.Label(card, text="0", bg="white", fg=INK, font=("DejaVu Sans", 20, "bold"))
            value.pack(anchor="w", pady=(3, 0)); self.metric_labels[key] = value
        ttk.Label(main, text="САНАХ ОЙН ЗУРАГЛАЛ", font=("DejaVu Sans", 10, "bold")).pack(anchor="w", pady=(16, 6))
        self.canvas = tk.Canvas(main, bg="white", height=116, highlightthickness=0)
        self.canvas.pack(fill="x")
        self.canvas.bind("<Configure>", lambda e: self.draw())
        self.canvas.bind("<Motion>", self.hover_block)
        self.canvas.bind("<Button-1>", self.click_block)
        self.hover = ttk.Label(main, text="Өнгөт: процесс • Саарал: сул • Тасархай хүрээ: хүсэлтийн урьдчилсан байрлал", foreground=MUTED, font=("DejaVu Sans", 9))
        self.hover.pack(fill="x", pady=(5, 7))
        self.lesson = ttk.Label(main, text="Жишээ ачаалж алхам бүрийн шалтгааныг ажиглаарай.", wraplength=900, font=("DejaVu Sans", 11, "bold"))
        self.lesson.pack(fill="x", pady=(2, 12))
        self.tabs = ttk.Notebook(main); self.tabs.pack(fill="both", expand=True)
        self.table = self.make_table("Хаягийн хүснэгт", ("pid", "start", "end", "size", "state"), ("Процесс", "Эхлэл", "Төгсгөл", "Bytes", "Төлөв"))
        self.compare_table = self.make_table("F / B / W харьцуулалт", ("strategy", "range", "hole", "remainder", "result"), ("Стратеги", "Сонгосон хаяг", "Hole bytes", "Үлдэгдэл", "Үр дүн"))
        self.history_table = self.make_table("Командын түүх", ("n", "command", "status", "free", "largest"), ("№", "Команд", "Төлөв", "Сул bytes", "Том hole"))
        self.history_table.tag_configure("error", foreground="#a33131")
        self.table.bind("<<TreeviewSelect>>", self.select_pid)
        self.history_table.bind("<<TreeviewSelect>>", self.select_history)
        self.compare_note = ttk.Label(main, text="Харьцуулалт нь нэг төлөвийн хуулбар дээр хийгдэнэ. Санах ойд өөрчлөлт оруулахгүй.", foreground=MUTED, font=("DejaVu Sans", 9), wraplength=900)
        self.compare_note.pack(fill="x", pady=7)
        row = ttk.Frame(main); row.pack(fill="x", pady=(5, 0))
        ttk.Label(row, text="allocator>").pack(side="left", padx=(0, 7))
        entry = ttk.Entry(row, textvariable=self.command)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda e: self.manual_command(self.command.get()))
        ttk.Button(row, text="Ажиллуулах", command=lambda: self.manual_command(self.command.get())).pack(side="left", padx=5)
        ttk.Button(row, text="JSON хадгалах", command=self.export).pack(side="left")
        self.feedback = ttk.Label(main, text="Бэлэн. Жишээ сонгоод «Жишээ ачаалах» дарна уу.", wraplength=900)
        self.feedback.pack(fill="x", pady=(10, 0))
        main.bind("<Configure>", lambda e: self.resize_text(e.width))
        for var in (self.pid, self.size, self.strategy):
            var.trace_add("write", lambda *_: self.update_preview())
        root.bind("<Escape>", lambda e: self.stop_demo())
        def shortcut(_event):
            self.manual_command(self.command.get())
            return "break"
        entry.bind("<Control-Return>", shortcut)
        root.bind("<Control-Return>", shortcut)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.render()

    def make_table(self, title, columns, labels):
        frame = ttk.Frame(self.tabs)
        self.tabs.add(frame, text=title)
        table = ttk.Treeview(frame, columns=columns, show="headings", height=5)
        for key, label in zip(columns, labels):
            table.heading(key, text=label)
            table.column(key, width=130, minwidth=75, anchor="center")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y"); table.pack(fill="both", expand=True)
        return table

    def resize_text(self, width):
        for label in (self.lesson, self.hover, self.feedback, self.compare_note):
            label.configure(wraplength=max(400, width - 8))

    def select_pid(self, _event):
        selected = self.table.selection()
        if selected:
            value = self.table.item(selected[0], "values")[0]
            if value != "—": self.pid.set(value)

    def select_history(self, _event):
        selected = self.history_table.selection()
        if selected:
            row = self.history[int(selected[0])]
            self.feedback.configure(text=row["message"].splitlines()[0], foreground=TEAL if row["ok"] else "#a33131")

    def reset(self):
        try:
            model = Allocator(int(self.total.get()))
        except (ValueError, AllocationError) as exc:
            self.feedback.configure(text=f"Алдаа: {exc}", foreground="#a33131")
            return False
        self.stop_demo()
        self.demo_index = None
        self.model, self.history, self.colors = model, [], {}
        self.lesson.configure(text="Санах ой шинэчлэгдлээ. Хүсэлт оруулах эсвэл жишээ ачаална уу.")
        self.feedback.configure(text=f"Reset: {model.total:,} bytes. Бүх зай сул.", foreground=TEAL)
        self.render()
        return True

    def manual_command(self, command):
        self.stop_demo()
        self.demo_index = None
        self.lesson.configure(text="Гар командын горим • Алхамт жишээг үргэлжлүүлэхийн тулд дахин ачаална.")
        return self.run_command(command)

    def run_command(self, command):
        before = self.model.snapshot()
        try:
            message, stop = execute(self.model, command)
            ok = True
        except AllocationError as exc:
            message, stop, ok = str(exc), False, False
        self.history.append({"command": command, "ok": ok, "message": message,
                             "before": before, "after": self.model.snapshot()})
        self.feedback.configure(text=message.splitlines()[0], foreground=TEAL if ok else "#a33131")
        self.render()
        if stop: self.close()
        return ok

    def render(self):
        stats = self.model.stats()
        for key, label in self.metric_labels.items():
            label.configure(text=f"{stats[key]:.1%}" if key == "fragmentation" else f"{stats[key]:,}")
        self.table.delete(*self.table.get_children())
        for b in self.model.blocks:
            self.table.insert("", "end", values=(b.pid or "—", b.start, b.end, b.size, "Эзэмшсэн" if b.pid else "Сул"))
        self.history_table.delete(*self.history_table.get_children())
        for i, row in enumerate(self.history):
            s = row["after"]["stats"] if "stats" in row["after"] else row["after"]
            self.history_table.insert("", "end", iid=str(i), values=(i + 1, row["command"], "OK" if row["ok"] else "Татгалзсан", s["free"], s["largest_hole"]), tags=() if row["ok"] else ("error",))
        if self.history: self.history_table.see(str(len(self.history) - 1))
        self.update_preview()
        self.update_controls()

    def update_preview(self):
        try: size = int(self.size.get())
        except ValueError: size = 0
        self.preview_rows = compare_request(self.model, self.pid.get(), size)
        self.compare_table.delete(*self.compare_table.get_children())
        for row in self.preview_rows:
            values = (row["strategy"], f"{row['start']}–{row['end']}", row["hole_size"], row["remainder"], "Боломжтой") if row["ok"] else (row["strategy"], "—", "—", "—", "Татгалзана")
            self.compare_table.insert("", "end", values=values)
        selected = next(r for r in self.preview_rows if r["strategy"] == self.strategy.get()[0])
        text = f"Урьдчилсан байрлал: [{selected['start']}:{selected['end']}]. RQ дарвал хэрэгжинэ." if selected["ok"] else "Урьдчилсан шалгалт: " + selected["message"]
        self.preview_label.configure(text=text)
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 100) - 32
        for b in self.model.blocks:
            if b.pid and b.pid not in self.colors: self.colors[b.pid] = PALETTE[len(self.colors) % len(PALETTE)]
            x0, x1 = 16 + width*b.start/self.model.total, 16 + width*(b.end+1)/self.model.total
            self.canvas.create_rectangle(x0, 20, x1, 80, fill=self.colors[b.pid] if b.pid else "#d8e2e9", outline="white", width=2)
            if x1 - x0 > 65:
                self.canvas.create_text((x0+x1)/2, 50, text=f"{b.pid or 'HOLE'}\n{b.size:,}", fill="white" if b.pid else INK, font=("DejaVu Sans", 10, "bold"))
        for row in self.preview_rows:
            if row["strategy"] == self.strategy.get()[0] and row["ok"]:
                self.canvas.create_rectangle(16+width*row["start"]/self.model.total, 16, 16+width*(row["end"]+1)/self.model.total, 84, outline=INK, width=2, dash=(5, 4))
        self.canvas.create_text(16, 99, text="0", anchor="w", fill=MUTED)
        self.canvas.create_text(width+16, 99, text=f"{self.model.total-1:,}", anchor="e", fill=MUTED)

    def block_at(self, event):
        width = self.canvas.winfo_width() - 32
        if width <= 0 or not (16 <= event.x < width+16 and 20 <= event.y <= 80): return None
        address = int((event.x-16)*self.model.total/width)
        return next((b for b in self.model.blocks if b.start <= address <= b.end), None)

    def hover_block(self, event):
        b = self.block_at(event)
        self.hover.configure(text=f"{b.pid or 'HOLE'}  •  [{b.start}:{b.end}]  •  {b.size:,} bytes  •  Хаягийн хоёр зах багтана." if b else "Өнгөт: процесс • Саарал: сул • Тасархай хүрээ: хүсэлтийн урьдчилсан байрлал")

    def click_block(self, event):
        b = self.block_at(event)
        if b and b.pid: self.pid.set(b.pid)

    def load_demo(self):
        self.scenario_key = next(key for key, value in SCENARIOS.items() if value["name"] == self.scenario.get())
        scenario = SCENARIOS[self.scenario_key]
        self.total.set(str(scenario["total"]))
        self.reset()
        self.demo_index = 0
        self.pid.set("Q" if self.scenario_key == "strategies" else "P3")
        self.size.set("150" if self.scenario_key == "strategies" else "400" if self.scenario_key == "fragmentation" else "1")
        self.tabs.select(0)
        self.lesson.configure(text="Жишээ бэлэн. «Алхам →» дарж үйлдэл, үр дүнг хамт ажиглаарай.")
        self.feedback.configure(text="Жишээ ачаалахад өмнөх төлөв, түүх шинэчлэгдэнэ.", foreground=MUTED)
        self.render()

    def step_demo(self):
        self.stop_demo()
        self.advance_demo()

    def advance_demo(self):
        steps = SCENARIOS[self.scenario_key]["steps"]
        if self.demo_index is None or self.demo_index >= len(steps): return False
        command, lesson = steps[self.demo_index]
        self.command.set(command)
        self.run_command(command)
        self.demo_index += 1
        self.lesson.configure(text=lesson)
        self.update_controls()
        if self.scenario_key == "strategies" and self.demo_index == len(steps): self.tabs.select(1)
        return self.demo_index < len(steps)

    def back_demo(self):
        self.stop_demo()
        if self.demo_index is None or self.demo_index == 0: return
        target = self.demo_index - 1
        self.model = Allocator(SCENARIOS[self.scenario_key]["total"])
        self.history, self.colors, self.demo_index = [], {}, 0
        for _ in range(target): self.advance_demo()
        if target == 0:
            self.lesson.configure(text="Жишээний эхлэлд буцлаа. Бүх санах ой сул.")
            self.feedback.configure(text="Алхам 0. Команд хараахан ажиллуулаагүй.", foreground=MUTED)
        self.render()

    def update_controls(self):
        count = len(SCENARIOS[self.scenario_key]["steps"])
        active = self.demo_index is not None
        more = active and self.demo_index < count
        self.back_button.configure(state="normal" if active and self.demo_index > 0 and not self.running else "disabled")
        self.step_button.configure(state="normal" if more and not self.running else "disabled")
        self.play_button.configure(state="normal" if more and not self.running else "disabled")
        self.pause_button.configure(state="normal" if self.running else "disabled")
        self.progress.configure(maximum=count, value=self.demo_index or 0)
        self.progress_label.configure(text=f"Алхам {self.demo_index} / {count}" if active else "Жишээ ачаалаагүй • гар командын горим")

    def play_demo(self):
        if self.running or self.demo_index is None: return
        self.running = True
        self.tick()

    def tick(self):
        self.timer = None
        if self.running and self.advance_demo(): self.timer = self.root.after(int(self.speed.get().split()[0]), self.tick)
        else: self.running = False
        self.update_controls()

    def stop_demo(self):
        self.running = False
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        if hasattr(self, "play_button"): self.update_controls()

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile="memory-lab-history.json", filetypes=[("JSON", "*.json")])
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"version": VERSION, "scenario": self.scenario_key if self.demo_index is not None else None, "step": self.demo_index, "state": self.model.snapshot(), "history": self.history}, f, ensure_ascii=False, indent=2)
        except OSError as exc: messagebox.showerror("Хадгалж чадсангүй", str(exc))
        else: self.feedback.configure(text="Төлөв, командын түүх JSON файлд хадгалагдлаа.", foreground=TEAL)

    def close(self):
        self.stop_demo()
        self.root.destroy()


if __name__ == "__main__":
    App(tk.Tk()).root.mainloop()
