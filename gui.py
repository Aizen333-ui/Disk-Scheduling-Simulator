"""Tkinter interface for the disk scheduling simulator.

Run with:  python gui.py      (requires: pip install matplotlib)
"""

import random
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import engine
import experiment
import inputs
import plots
import stats
import workloads
from disk_scheduling import DOWN, UP

DEFAULT_QUEUE = "98 183 37 122 14 124 65 67"
TABLE_COLUMNS = (
    ("algorithm", "Algorithm", 100), ("total", "Head movement", 105), ("avg_seek", "Avg seek", 75),
    ("avg_resp", "Avg response (ms)", 120), ("avg_wait", "Avg wait (ms)", 100),
    ("max_wait", "Max wait (ms)", 100), ("fairness", "Fairness", 75), ("thru", "Throughput (req/s)", 125),
)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Disk Scheduling Simulator")
        self.geometry("1320x820")
        self.minsize(1100, 680)

        self.results = {}
        self.disk = None
        self._anim_job = None
        self.metric_keys = {label: key for key, label in experiment.METRICS}

        self._build_controls()
        self._build_tabs()
        self.run_simulation()

    # ------------------------------------------------------------------ layout
    def _field(self, parent, text, var, width=9) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=1)
        ttk.Label(row, text=text, width=24, anchor="w").pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=var, width=width).pack(side=tk.LEFT)

    def _build_controls(self) -> None:
        panel = ttk.Frame(self, padding=8)
        panel.pack(side=tk.LEFT, fill=tk.Y)

        self.requests_var = tk.StringVar(value=DEFAULT_QUEUE)
        self.head_var = tk.StringVar(value="53")
        self.dir_var = tk.StringVar(value=UP)
        self.jump_var = tk.BooleanVar(value=True)
        self.cyl_var = tk.StringVar(value="200")
        self.rpm_var = tk.StringVar(value="7200")
        self.t2t_var = tk.StringVar(value="1.0")
        self.full_var = tk.StringVar(value="15.0")
        self.xfer_var = tk.StringVar(value="0.05")
        self.rot_var = tk.StringVar(value="average")
        self.nstep_var = tk.StringVar(value="4")
        self.expire_var = tk.StringVar(value="100")
        self.wl_kind_var = tk.StringVar(value="uniform")
        self.wl_n_var = tk.StringVar(value="12")
        self.wl_gap_var = tk.StringVar(value="8")
        self.status_var = tk.StringVar()

        req = ttk.LabelFrame(panel, text="Requests", padding=8)
        req.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(req, text="Cylinders, or cylinder@arrival_ms\n(e.g. 98 183@5 37@12.5):").pack(anchor="w")
        ttk.Entry(req, textvariable=self.requests_var, width=38).pack(anchor="w", pady=(2, 6))
        self._field(req, "Initial head position:", self.head_var)
        row = ttk.Frame(req)
        row.pack(fill=tk.X, pady=1)
        ttk.Label(row, text="Initial direction:", width=24, anchor="w").pack(side=tk.LEFT)
        ttk.Combobox(row, textvariable=self.dir_var, values=[UP, DOWN], state="readonly",
                     width=7).pack(side=tk.LEFT)

        disk = ttk.LabelFrame(panel, text="Disk model", padding=8)
        disk.pack(fill=tk.X, pady=6)
        self._field(disk, "Cylinders:", self.cyl_var)
        self._field(disk, "Speed (RPM):", self.rpm_var)
        self._field(disk, "Track-to-track seek (ms):", self.t2t_var)
        self._field(disk, "Full-stroke seek (ms):", self.full_var)
        self._field(disk, "Transfer time (ms):", self.xfer_var)
        row = ttk.Frame(disk)
        row.pack(fill=tk.X, pady=1)
        ttk.Label(row, text="Rotational latency:", width=24, anchor="w").pack(side=tk.LEFT)
        ttk.Combobox(row, textvariable=self.rot_var, values=["average", "random"], state="readonly",
                     width=8).pack(side=tk.LEFT)
        ttk.Checkbutton(disk, text="Count C-SCAN / C-LOOK return jump",
                        variable=self.jump_var).pack(anchor="w", pady=(4, 0))

        opts = ttk.LabelFrame(panel, text="Algorithm options", padding=8)
        opts.pack(fill=tk.X, pady=6)
        self._field(opts, "N-step SCAN batch size N:", self.nstep_var)
        self._field(opts, "Deadline expiry (ms):", self.expire_var)

        wl = ttk.LabelFrame(panel, text="Workloads", padding=8)
        wl.pack(fill=tk.X, pady=6)
        row = ttk.Frame(wl)
        row.pack(fill=tk.X, pady=1)
        ttk.Label(row, text="Pattern:", width=24, anchor="w").pack(side=tk.LEFT)
        ttk.Combobox(row, textvariable=self.wl_kind_var, values=workloads.WORKLOAD_KINDS,
                     state="readonly", width=10).pack(side=tk.LEFT)
        self._field(wl, "Number of requests:", self.wl_n_var)
        self._field(wl, "Mean gap between arrivals (ms):", self.wl_gap_var)
        btns = ttk.Frame(wl)
        btns.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(btns, text="Generate", command=self.generate_workload).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btns, text="Starvation demo", command=self.starvation_demo).pack(side=tk.LEFT)
        btns = ttk.Frame(wl)
        btns.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(btns, text="Load CSV...", command=self.load_csv).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btns, text="Save CSV...", command=self.save_csv).pack(side=tk.LEFT)

        ttk.Button(panel, text="Run simulation", command=self.run_simulation).pack(fill=tk.X, pady=(8, 2))
        ttk.Button(panel, text="Reset to textbook example", command=self.reset_example).pack(fill=tk.X, pady=2)
        ttk.Label(panel, textvariable=self.status_var, foreground="#b03030",
                  wraplength=300, justify="left").pack(anchor="w", pady=(8, 0))

    def _build_tabs(self) -> None:
        right = ttk.Frame(self)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(0, 8), pady=8)

        bar = ttk.Frame(right)
        bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(bar, text="Algorithm:").pack(side=tk.LEFT)
        self.algo_var = tk.StringVar(value="FCFS")
        box = ttk.Combobox(bar, textvariable=self.algo_var, values=engine.POLICY_NAMES,
                           state="readonly", width=14)
        box.pack(side=tk.LEFT, padx=6)
        box.bind("<<ComboboxSelected>>", lambda e: self.show_selected())
        ttk.Button(bar, text="Animate head path", command=self.animate).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Show full path", command=self.show_selected).pack(side=tk.LEFT, padx=4)
        self.order_var = tk.StringVar()
        ttk.Label(right, textvariable=self.order_var, wraplength=900, justify="left",
                  foreground="#444444").pack(fill=tk.X, pady=(0, 4))

        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill=tk.BOTH, expand=True)

        # --- Head path tab
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text="Head path")
        self.path_fig = Figure(figsize=(7, 5), dpi=100)
        self.path_ax = self.path_fig.add_subplot(111)
        self.path_canvas = FigureCanvasTkAgg(self.path_fig, master=tab)
        self.path_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # --- Time view tab
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text="Time view")
        self.time_fig = Figure(figsize=(7, 5), dpi=100)
        self.time_ax = self.time_fig.add_subplot(111)
        self.time_canvas = FigureCanvasTkAgg(self.time_fig, master=tab)
        self.time_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # --- Comparison tab
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text="Comparison")
        self.table = ttk.Treeview(tab, columns=[c[0] for c in TABLE_COLUMNS], show="headings", height=9)
        for col, text, width in TABLE_COLUMNS:
            self.table.heading(col, text=text)
            self.table.column(col, width=width, anchor="center")
        self.table.pack(fill=tk.X, padx=6, pady=6)
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, padx=6)
        ttk.Label(row, text="Chart metric:").pack(side=tk.LEFT)
        self.metric_var = tk.StringVar(value=experiment.METRIC_LABELS["total_movement"])
        mbox = ttk.Combobox(row, textvariable=self.metric_var, values=list(self.metric_keys),
                            state="readonly", width=38)
        mbox.pack(side=tk.LEFT, padx=6)
        mbox.bind("<<ComboboxSelected>>", lambda e: self._draw_comparison())
        self.cmp_fig = Figure(figsize=(8, 4), dpi=100)
        self.cmp_canvas = FigureCanvasTkAgg(self.cmp_fig, master=tab)
        self.cmp_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # --- Experiment tab
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text="Random experiment")
        self.exp_workload_var = tk.StringVar(value="uniform")
        self.exp_trials_var = tk.StringVar(value="200")
        self.exp_n_var = tk.StringVar(value="30")
        self.exp_gap_var = tk.StringVar(value="8")
        self.exp_metric_var = tk.StringVar(value=experiment.METRIC_LABELS["avg_response_ms"])
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, padx=6, pady=6)
        ttk.Label(row, text="Workload:").pack(side=tk.LEFT)
        ttk.Combobox(row, textvariable=self.exp_workload_var, values=workloads.WORKLOAD_KINDS,
                     state="readonly", width=10).pack(side=tk.LEFT, padx=(4, 10))
        for text, var in (("Trials:", self.exp_trials_var), ("Requests/trial:", self.exp_n_var),
                          ("Mean gap (ms):", self.exp_gap_var)):
            ttk.Label(row, text=text).pack(side=tk.LEFT)
            ttk.Entry(row, textvariable=var, width=6).pack(side=tk.LEFT, padx=(4, 10))
        row2 = ttk.Frame(tab)
        row2.pack(fill=tk.X, padx=6)
        ttk.Label(row2, text="Metric:").pack(side=tk.LEFT)
        ttk.Combobox(row2, textvariable=self.exp_metric_var, values=list(self.metric_keys),
                     state="readonly", width=38).pack(side=tk.LEFT, padx=(4, 10))
        ttk.Button(row2, text="Run experiment", command=self.run_experiment).pack(side=tk.LEFT)
        self.exp_note_var = tk.StringVar(value="Uses the disk model and options from the left panel. "
                                               "Each trial runs every algorithm on the same random workload.")
        ttk.Label(tab, textvariable=self.exp_note_var, foreground="#444444",
                  wraplength=900, justify="left").pack(fill=tk.X, padx=6, pady=4)
        self.exp_fig = Figure(figsize=(8, 4.5), dpi=100)
        self.exp_canvas = FigureCanvasTkAgg(self.exp_fig, master=tab)
        self.exp_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self._exp_data = None

    # ------------------------------------------------------------------- input
    def _current_disk(self):
        return inputs.build_disk(self.cyl_var.get(), self.rpm_var.get(), self.t2t_var.get(),
                                 self.full_var.get(), self.xfer_var.get(), self.rot_var.get())

    def _policy_options(self) -> dict:
        return {"n": inputs.parse_number(self.nstep_var.get(), "N (N-step SCAN)", int, 1),
                "expire_ms": inputs.parse_number(self.expire_var.get(), "Deadline expiry", float, 0)}

    def _parse_all(self):
        requests = inputs.parse_requests(self.requests_var.get())
        head = inputs.parse_number(self.head_var.get(), "Head position", int)
        disk = self._current_disk()
        direction = self.dir_var.get()
        options = self._policy_options()
        engine.validate_inputs(requests, head, disk, direction)
        return requests, head, disk, direction, self.jump_var.get(), options

    # ----------------------------------------------------------------- actions
    def run_simulation(self) -> None:
        self._stop_animation()
        try:
            requests, head, disk, direction, jump, options = self._parse_all()
            results = engine.run_all(requests, head, disk, direction, jump, seed=0, **options)
        except ValueError as e:
            self.status_var.set(str(e))
            return
        self.status_var.set("")
        self.disk, self.results = disk, results
        self._fill_table()
        self._draw_comparison()
        self.show_selected()

    def reset_example(self) -> None:
        self.requests_var.set(DEFAULT_QUEUE)
        self.head_var.set("53")
        self.dir_var.set(UP)
        self.jump_var.set(True)
        self.cyl_var.set("200")
        self.rpm_var.set("7200")
        self.t2t_var.set("1.0")
        self.full_var.set("15.0")
        self.xfer_var.set("0.05")
        self.rot_var.set("average")
        self.nstep_var.set("4")
        self.expire_var.set("100")
        self.metric_var.set(experiment.METRIC_LABELS["total_movement"])
        self.run_simulation()

    def generate_workload(self) -> None:
        try:
            disk = self._current_disk()
            n = inputs.parse_number(self.wl_n_var.get(), "Number of requests", int, 1)
            gap = inputs.parse_number(self.wl_gap_var.get(), "Mean gap", float, 0)
            requests = workloads.generate(self.wl_kind_var.get(), n, disk.cylinders, gap)
        except ValueError as e:
            self.status_var.set(str(e))
            return
        self.requests_var.set(inputs.format_requests(requests))
        self.head_var.set(str(random.randrange(disk.cylinders)))
        self.run_simulation()

    def starvation_demo(self) -> None:
        try:
            disk = self._current_disk()
            requests, head = workloads.starvation_demo(disk.cylinders)
        except ValueError as e:
            self.status_var.set(str(e))
            return
        self.requests_var.set(inputs.format_requests(requests))
        self.head_var.set(str(head))
        self.dir_var.set(UP)
        self.metric_var.set(experiment.METRIC_LABELS["max_wait_ms"])
        self.run_simulation()
        self.algo_var.set("SSTF")
        self.show_selected()
        self.tabs.select(2)
        self.status_var.set("Starvation demo: request #0 (cylinder %d) is stuck behind a stream of nearby "
                            "requests under SSTF. Compare maximum wait across algorithms." % (disk.cylinders - 5))

    def load_csv(self) -> None:
        path = filedialog.askopenfilename(title="Open request trace",
                                          filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            requests = workloads.load_csv(path)
        except (OSError, ValueError) as e:
            self.status_var.set(str(e))
            return
        self.requests_var.set(inputs.format_requests(requests))
        self.run_simulation()

    def save_csv(self) -> None:
        try:
            requests = inputs.parse_requests(self.requests_var.get())
            if not requests:
                raise ValueError("There are no requests to save.")
        except ValueError as e:
            self.status_var.set(str(e))
            return
        path = filedialog.asksaveasfilename(title="Save request trace", defaultextension=".csv",
                                            filetypes=[("CSV files", "*.csv")])
        if path:
            try:
                workloads.save_csv(requests, path)
            except OSError as e:
                self.status_var.set(str(e))

    def _fill_table(self) -> None:
        self.table.delete(*self.table.get_children())
        for name, r in self.results.items():
            self.table.insert("", tk.END, values=(
                name, r.total_movement, f"{r.average_seek:.1f}", f"{r.avg_response_ms:.1f}",
                f"{r.avg_wait_ms:.1f}", f"{r.max_wait_ms:.1f}", f"{r.fairness:.3f}",
                f"{r.throughput_per_s:.0f}"))

    def _draw_comparison(self) -> None:
        if not self.results:
            return
        key = self.metric_keys[self.metric_var.get()]
        self.cmp_fig.clf()
        ax1, ax2 = self.cmp_fig.subplots(1, 2)
        names = list(self.results)
        values = [self.results[n].summary()[key] for n in names]
        plots.draw_bar(ax1, names, values, self.metric_var.get(), "")
        ax1.tick_params(axis="x", labelrotation=35)
        plots.draw_cdf(ax2, self.results)
        self.cmp_fig.tight_layout()
        self.cmp_canvas.draw()

    def show_selected(self) -> None:
        """Redraw the head-path and time-view tabs for the selected algorithm."""
        self._stop_animation()
        result = self.results.get(self.algo_var.get())
        if result is None:
            return
        self.order_var.set("Service order: " + " \u2192 ".join(map(str, result.service_order)))
        plots.draw_head_path(self.path_ax, result, self.disk.cylinders)
        self.path_canvas.draw()
        plots.draw_time_path(self.time_ax, result, self.disk.cylinders)
        self.time_canvas.draw()

    # --------------------------------------------------------------- animation
    def animate(self) -> None:
        result = self.results.get(self.algo_var.get())
        if result is None:
            return
        self._stop_animation()
        self.tabs.select(0)
        self._step(result, 0)

    def _step(self, result, step: int) -> None:
        plots.draw_head_path(self.path_ax, result, self.disk.cylinders, steps=step)
        self.path_canvas.draw()
        if step < len(result.head_path) - 1:
            delay = 600 if len(result.head_path) <= 30 else 150
            self._anim_job = self.after(delay, self._step, result, step + 1)
        else:
            self._anim_job = None

    def _stop_animation(self) -> None:
        if self._anim_job is not None:
            self.after_cancel(self._anim_job)
            self._anim_job = None

    # -------------------------------------------------------------- experiment
    def run_experiment(self) -> None:
        try:
            disk = self._current_disk()
            trials = inputs.parse_number(self.exp_trials_var.get(), "Trials", int, 1)
            n = inputs.parse_number(self.exp_n_var.get(), "Requests per trial", int, 1)
            gap = inputs.parse_number(self.exp_gap_var.get(), "Mean gap", float, 0)
            options = self._policy_options()
        except ValueError as e:
            messagebox.showerror("Experiment", str(e))
            return
        self.exp_note_var.set("Running %d trials..." % trials)
        self.update_idletasks()
        data = experiment.run_experiment(trials, n, disk, self.exp_workload_var.get(), gap,
                                         count_jump=self.jump_var.get(), policy_options=options)
        key = self.metric_keys[self.exp_metric_var.get()]
        label = self.exp_metric_var.get()
        summary = stats.summarize(data[key])
        self.exp_fig.clf()
        ax1, ax2 = self.exp_fig.subplots(1, 2)
        plots.draw_bar_ci(ax1, summary, "Mean with 95% confidence interval", label)
        plots.draw_boxplot(ax2, data[key], "Distribution across trials", label)
        self.exp_fig.tight_layout()
        self.exp_canvas.draw()
        best = min(summary, key=lambda a: summary[a][0]) if key != "fairness" else max(summary, key=lambda a: summary[a][0])
        self.exp_note_var.set(f"{trials} trials, {n} requests each, {self.exp_workload_var.get()} workload. "
                              f"Best mean for '{label}': {best}.")


if __name__ == "__main__":
    App().mainloop()
