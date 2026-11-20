"""Matplotlib drawing helpers, independent of Tkinter so they can be tested alone."""

from typing import Dict, List, Optional, Tuple

COLORS = {"FCFS": "#d6604d", "SSTF": "#4393c3", "SCAN": "#5aae61", "C-SCAN": "#8e6bbf",
          "LOOK": "#2e8b57", "C-LOOK": "#17a2b8", "N-STEP-SCAN": "#e08214",
          "FSCAN": "#c51b7d", "DEADLINE": "#4d4d4d"}


def _color(name: str) -> str:
    return COLORS.get(name, "#333333")


def draw_head_path(ax, result, disk_size: int, steps: Optional[int] = None) -> None:
    """Head path: cylinder on the x axis, move number going down.

    steps limits how many moves are drawn (used by the animation).
    Dashed lines are return jumps.
    """
    ax.clear()
    path = result.head_path
    last = len(path) - 1 if steps is None else max(0, min(steps, len(path) - 1))
    color = _color(result.algorithm)

    for i in range(1, last + 1):
        is_jump = (i - 1) in result.jump_moves
        ax.plot([path[i - 1], path[i]], [i - 1, i],
                linestyle="--" if is_jump else "-", color=color, linewidth=1.8)
    show_labels = len(path) <= 40
    for i in range(last + 1):
        ax.plot(path[i], i, "o", color=color, markersize=5)
        if show_labels:
            ax.annotate(str(path[i]), (path[i], i), textcoords="offset points",
                        xytext=(0, 7), ha="center", fontsize=8)
    ax.plot(path[0], 0, "s", color="black", markersize=7, label="start")

    ax.set_xlim(-5, disk_size + 4)
    ax.set_ylim(len(path) - 0.2, -1)          # time runs downwards
    ax.set_xlabel("Cylinder")
    ax.set_ylabel("Move number")
    ax.set_title(f"{result.algorithm}: total head movement = {result.total_movement} cylinders")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", fontsize=8)


def draw_time_path(ax, result, disk_size: int) -> None:
    """Head position over time, with request arrivals and completions marked."""
    ax.clear()
    color = _color(result.algorithm)
    ax.plot([p[0] for p in result.time_path], [p[1] for p in result.time_path],
            color=color, linewidth=1.4, zorder=2)
    comps = result.completions
    ax.scatter([c.request.arrival_ms for c in comps], [c.request.cylinder for c in comps],
               facecolors="none", edgecolors="#555555", s=30, label="request arrives", zorder=3)
    ax.scatter([c.finish_ms for c in comps], [c.request.cylinder for c in comps],
               color=color, s=22, label="request served", zorder=4)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Cylinder")
    ax.set_ylim(-5, disk_size + 4)
    ax.set_title(f"{result.algorithm}: head position over time "
                 f"(avg response {result.avg_response_ms:.1f} ms, max wait {result.max_wait_ms:.1f} ms)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", fontsize=8)


def draw_bar(ax, labels: List[str], values: List[float], title: str, ylabel: str) -> None:
    """Labelled bar chart."""
    ax.clear()
    bars = ax.bar(labels, values, color=[_color(l) for l in labels])
    if all(float(v).is_integer() for v in values):
        fmt = "%d"
    else:
        fmt = "%.2f" if max(values) < 10 else "%.1f"
    ax.bar_label(bars, fmt=fmt, padding=3, fontsize=8)
    ax.set_title(title, fontsize=10)
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, (max(values) if values else 1) * 1.15 or 1)
    ax.grid(True, axis="y", alpha=0.3)


def draw_comparison(ax, results: Dict[str, object]) -> None:
    names = list(results)
    draw_bar(ax, names, [results[n].total_movement for n in names],
             "Total head movement (same input)", "Cylinders")


def draw_cdf(ax, results: Dict[str, object]) -> None:
    """Cumulative distribution of per-request response times for each algorithm."""
    ax.clear()
    for name, res in results.items():
        xs = sorted(res.responses)
        ys = [(i + 1) / len(xs) for i in range(len(xs))]
        ax.step(xs, ys, where="post", label=name, color=_color(name), linewidth=1.5)
    ax.set_xlabel("Response time (ms)")
    ax.set_ylabel("Fraction of requests")
    ax.set_title("Response time distribution (CDF)", fontsize=10)
    ax.set_ylim(0, 1.02)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, loc="lower right")


def draw_bar_ci(ax, summary: Dict[str, Tuple[float, float, float]], title: str, ylabel: str) -> None:
    """Bars of the mean with 95% confidence-interval error bars. summary: name -> (mean, ci, std)."""
    ax.clear()
    labels = list(summary)
    means = [summary[l][0] for l in labels]
    cis = [summary[l][1] for l in labels]
    ax.bar(labels, means, yerr=cis, capsize=4, color=[_color(l) for l in labels])
    ax.set_title(title, fontsize=10)
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, max(m + c for m, c in zip(means, cis)) * 1.15 or 1)
    ax.tick_params(axis="x", labelrotation=35)
    ax.grid(True, axis="y", alpha=0.3)


def draw_boxplot(ax, data: Dict[str, List[float]], title: str, ylabel: str) -> None:
    """Distribution of a metric across trials, one box per algorithm."""
    ax.clear()
    labels = list(data)
    box = ax.boxplot([data[l] for l in labels], patch_artist=True, showfliers=False)
    for patch, label in zip(box["boxes"], labels):
        patch.set_facecolor(_color(label))
        patch.set_alpha(0.7)
    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels)
    ax.tick_params(axis="x", labelrotation=35)
    ax.set_title(title, fontsize=10)
    ax.set_ylabel(ylabel)
    ax.grid(True, axis="y", alpha=0.3)
