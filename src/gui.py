"""Tk desktop UI; all commands go through the shared allocator model."""
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from .allocator import Allocator, AllocationError, execute

DEMO = ["RQ P0 300 F", "RQ P1 200 F", "RQ P2 300 F", "RL P0",
        "RQ P3 400 F", "C", "RQ P3 400 F", "STAT"]
PALETTE = ["#0f766e", "#2563eb", "#7c3aed", "#be185d", "#c2410c", "#0369a1"]


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Memory Lab | Contiguous Memory Allocation")
        self.root.geometry("1160x800")
        self.root.minsize(960, 800)
        self.root.configure(bg="#f1f5f9")
        self.model = Allocator(1000)
        self.history = []
        self.colors = {}
        self.demo_index = None
        self.timer = None
        self.running = False
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#f1f5f9")
        style.configure("TLabel", background="#f1f5f9", font=("DejaVu Sans", 10))
        style.configure("TButton", font=("DejaVu Sans", 10), padding=7)
        style.configure("Treeview", rowheight=27, font=("DejaVu Sans", 10))
        style.configure("Treeview.Heading", font=("DejaVu Sans", 10, "bold"))
        header = tk.Frame(root, bg="#0f172a", padx=24, pady=15)
        header.pack(fill="x")
        tk.Label(header, text="MEMORY LAB", bg="#0f172a", fg="#5eead4",
                 font=("DejaVu Sans", 11, "bold")).pack(anchor="w")
        tk.Label(header, text="Залгаа санах ой хуваарилалт", bg="#0f172a", fg="white",
                 font=("DejaVu Sans", 22, "bold")).pack(anchor="w", pady=(3, 0))
        tk.Label(header, text="F / First fit     B / Best fit     W / Worst fit     •     Симулятор",
                 bg="#0f172a", fg="#cbd5e1", font=("DejaVu Sans", 10)).pack(anchor="w", pady=4)
        body = ttk.Frame(root, padding=18)
        body.pack(fill="both", expand=True)
        config = ttk.Frame(body)
        config.pack(fill="x")
        ttk.Label(config, text="Нийт bytes").pack(side="left")
        self.total = tk.StringVar(value="1000")
        ttk.Entry(config, textvariable=self.total, width=13).pack(side="left", padx=8)
        ttk.Button(config, text="Reset", command=self.reset).pack(side="left")
        ttk.Button(config, text="Демо бэлтгэх", command=self.load_demo).pack(side="left", padx=(18, 4))
        ttk.Button(config, text="Алхам", command=self.step_demo).pack(side="left", padx=4)
        ttk.Button(config, text="Тоглуулах", command=self.play_demo).pack(side="left", padx=4)
        ttk.Button(config, text="Зогсоох", command=self.stop_demo).pack(side="left", padx=4)
        self.stats_label = ttk.Label(body, font=("DejaVu Sans", 11, "bold"), wraplength=900)
        self.stats_label.pack(fill="x", pady=(18, 6))
        self.canvas = tk.Canvas(body, bg="white", height=105, highlightthickness=0)
        self.canvas.pack(fill="x")
        self.canvas.bind("<Configure>", lambda e: self.draw())
        ttk.Label(body, text="Өнгөт: процесс  |  Саарал: сул hole  |  Өргөн нь хэмжээтэй пропорционал; хаягууд inclusive.",
                  foreground="#475569").pack(anchor="w", pady=(5, 12))
        controls = ttk.Frame(body)
        controls.pack(fill="x")
        self.pid = tk.StringVar(value="P0")
        self.size = tk.StringVar(value="300")
        self.strategy = tk.StringVar(value="F")
        for title, var, width in [("PID", self.pid, 10), ("Bytes", self.size, 10)]:
            ttk.Label(controls, text=title).pack(side="left", padx=(0, 6))
            ttk.Entry(controls, textvariable=var, width=width).pack(side="left", padx=(0, 12))
        ttk.Combobox(controls, textvariable=self.strategy, values=["F", "B", "W"],
                     state="readonly", width=4).pack(side="left", padx=(0, 10))
        ttk.Button(controls, text="RQ • Хуваарилах", command=lambda: self.manual_command(
            f"RQ {self.pid.get()} {self.size.get()} {self.strategy.get()}")).pack(side="left", padx=3)
        ttk.Button(controls, text="RL • Чөлөөлөх", command=lambda: self.manual_command(
            f"RL {self.pid.get()}")).pack(side="left", padx=3)
        ttk.Button(controls, text="C • Нягтруулах", command=lambda: self.manual_command("C")).pack(side="left", padx=3)
        cols = ("pid", "start", "end", "size", "state")
        table_frame = ttk.Frame(body)
        table_frame.pack(fill="both", expand=True, pady=12)
        self.table = ttk.Treeview(table_frame, columns=cols, show="headings", height=6)
        for col, label in zip(cols, ("Процесс", "Эхлэх хаяг", "Төгсөх хаяг", "Bytes", "Төлөв")):
            self.table.heading(col, text=label)
            self.table.column(col, width=150, anchor="center")
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.table.pack(side="left", fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self.select_pid)
        command_frame = ttk.Frame(body)
        command_frame.pack(fill="x")
        ttk.Label(command_frame, text="allocator>").pack(side="left", padx=(0, 10))
        self.command = tk.StringVar(value="STAT")
        entry = ttk.Entry(command_frame, textvariable=self.command)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda e: self.manual_command(self.command.get()))
        ttk.Button(command_frame, text="Ажиллуулах", command=lambda: self.manual_command(
            self.command.get())).pack(side="left", padx=(8, 0))
        ttk.Button(command_frame, text="JSON хадгалах", command=self.export).pack(side="left", padx=(8, 0))
        self.feedback = ttk.Label(body, text="Бэлэн. Демо бэлтгэх → Алхам дарж туршаарай.", wraplength=900)
        self.feedback.pack(fill="x", pady=(10, 6))
        self.log = tk.Text(body, height=5, bg="#0f172a", fg="#e2e8f0", insertbackground="white",
                           font=("DejaVu Sans Mono", 10), relief="flat", padx=10, pady=8)
        self.log.pack(fill="x")
        self.log.configure(state="disabled")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.render()

    def select_pid(self, _event):
        selection = self.table.selection()
        if selection:
            value = self.table.item(selection[0], "values")[0]
            if value != "-":
                self.pid.set(value)

    def reset(self):
        try:
            total = int(self.total.get())
            model = Allocator(total)
        except (ValueError, AllocationError) as exc:
            self.feedback.configure(text=f"Алдаа: {exc}", foreground="#b91c1c")
            return
        self.stop_demo()
        self.demo_index = None
        self.model, self.history, self.colors = model, [], {}
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.feedback.configure(text=f"Reset: {total} bytes, бүх зай сул.", foreground="#0f766e")
        self.render()

    def manual_command(self, command):
        self.stop_demo()
        self.demo_index = None
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
        self.feedback.configure(text=message.splitlines()[0], foreground="#0f766e" if ok else "#b91c1c")
        self.log.configure(state="normal")
        self.log.insert("end", f"> {command}\n{'OK' if ok else 'ERROR'}: {message}\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        self.render()
        if stop:
            self.close()
        return ok

    def render(self):
        s = self.model.stats()
        self.stats_label.configure(text=f"Нийт {s['total']:,}   •   Ашигласан {s['used']:,}   •   Сул {s['free']:,}   •   "
                                   f"Hole {s['holes']}   •   Хамгийн том {s['largest_hole']:,}   •   F = {s['fragmentation']:.1%}")
        self.table.delete(*self.table.get_children())
        for b in self.model.blocks:
            self.table.insert("", "end", values=(b.pid or "-", b.start, b.end, b.size,
                              "Эзэмшсэн" if b.pid else "Сул"))
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 100) - 40
        for b in self.model.blocks:
            if b.pid and b.pid not in self.colors:
                self.colors[b.pid] = PALETTE[len(self.colors) % len(PALETTE)]
            color = self.colors[b.pid] if b.pid else "#cbd5e1"
            x0 = 20 + width * (b.start / self.model.total)
            x1 = 20 + width * ((b.end + 1) / self.model.total)
            self.canvas.create_rectangle(x0, 22, x1, 77, fill=color, outline="white")
            if x1 - x0 > 75:
                self.canvas.create_text((x0 + x1) / 2, 49, text=f"{b.pid or 'HOLE'}\n{b.size:,}",
                                        fill="white" if b.pid else "#334155", font=("DejaVu Sans", 10, "bold"))
        self.canvas.create_text(20, 91, text="0", anchor="w", fill="#475569")
        self.canvas.create_text(width + 20, 91, text=f"{self.model.total - 1:,}", anchor="e", fill="#475569")

    def load_demo(self):
        self.total.set("1000")
        self.reset()
        self.demo_index = 0
        self.feedback.configure(text="Демо бэлэн: 8 алхам. 5-р алхам зориудаар бүтэлгүйтнэ; дараа нь нягтруулна.")

    def step_demo(self):
        self.stop_demo()
        self.advance_demo()

    def advance_demo(self):
        if self.demo_index is None:
            self.feedback.configure(text="Эхлээд Демо бэлтгэх дарна уу.")
            return False
        if self.demo_index >= len(DEMO):
            self.feedback.configure(text="Демо дууссан. Дахин туршихдаа Демо бэлтгэх дарна уу.")
            return False
        self.command.set(DEMO[self.demo_index])
        self.run_command(DEMO[self.demo_index])
        self.demo_index += 1
        return self.demo_index < len(DEMO)

    def play_demo(self):
        if self.running:
            return
        self.running = True
        self.tick()

    def tick(self):
        self.timer = None
        if self.running and self.advance_demo():
            self.timer = self.root.after(1200, self.tick)
        else:
            self.running = False

    def stop_demo(self):
        self.running = False
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"state": self.model.snapshot(), "history": self.history}, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            messagebox.showerror("Хадгалж чадсангүй", str(exc))
        else:
            self.feedback.configure(text="Төлөв болон командын түүх JSON файлд хадгалагдлаа.")

    def close(self):
        self.stop_demo()
        self.root.destroy()


if __name__ == "__main__":
    App(tk.Tk()).root.mainloop()
