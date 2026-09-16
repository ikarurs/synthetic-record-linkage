"""Three inspectable figures; every chart is explicitly synthetic."""
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter, MaxNLocator

BLUE, GOLD, GREY = "#22577A", "#B56B11", "#D8DEE5"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "figure.facecolor": "white"})


def plot_scores(pairs, truth):
    """Post hoc diagnosis, not a basis for tuning on held-out labels."""
    gold = {(r["left_id"], r["right_id"]) for r in truth if r["right_id"]}
    allowed = {r["left_id"] for r in truth}
    data = {True: [], False: []}
    for pair in pairs:
        if pair["left_id"] in allowed:
            data[(pair["left_id"], pair["right_id"]) in gold].append(float(pair["score"]))
    fig, ax = plt.subplots(figsize=(8.4, 4.8), layout="constrained")
    for match, color, style in ((True, BLUE, "-"), (False, GOLD, "--")):
        if data[match]:
            label = ("True link" if match else "Different people") + f" (n={len(data[match])})"
            ax.hist(data[match], bins=[i / 20 for i in range(21)], histtype="step",
                    linewidth=2, color=color, linestyle=style, label=label)
    ax.set(title="Candidate scores · synthetic development towns", xlabel="Heuristic score (not a probability)",
           ylabel="Candidate pairs", xlim=(0, 1))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(frameon=False)
    return fig


def plot_thresholds(sweep):
    fig, ax = plt.subplots(figsize=(8.4, 4.8), layout="constrained")
    for field, color, marker, style in (("precision", BLUE, "o", "-"),
                                      ("recall", GOLD, "s", "--"),
                                      ("coverage", "#535D6C", "^", ":")):
        ax.plot([r["threshold"] for r in sweep],
                [float(r[field]) if r[field] is not None else float("nan") for r in sweep],
                marker=marker, linestyle=style, color=color, label=field.title())
    ax.axvline(.86, color="#333333", lw=1, linestyle="--", label="Default threshold 0.86")
    ax.set(title="Threshold trade-offs · synthetic development towns", xlabel="Acceptance threshold",
           ylabel="Share (denominators differ; see README)", ylim=(0, 1.06), xlim=(.53, 1.02))
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.grid(axis="y", alpha=.2)
    ax.legend(frameon=False, loc="lower left")
    return fig


def plot_decisions(decisions):
    towns = sorted({r["town"] for r in decisions})
    counts = Counter((r["town"], r["status"]) for r in decisions)
    fig, ax = plt.subplots(figsize=(8.4, 5.2), layout="constrained")
    offsets = [0] * len(towns)
    for status, color, hatch in (("accepted", BLUE, ""), ("review", GOLD, "///"), ("unmatched", GREY, "..")):
        values = [counts[town, status] for town in towns]
        bars = ax.barh(towns, values, left=offsets, color=color, hatch=hatch,
                       edgecolor="white", label=status.title())
        ax.bar_label(bars, labels=[str(v) if v else "" for v in values], label_type="center",
                     color="#17212C" if status == "unmatched" else "white", fontsize=10)
        offsets = [a + b for a, b in zip(offsets, values)]
    ax.set(title="Matching decisions · all synthetic towns", xlabel="Baseline people (1920)", xlim=(0, max(offsets) + 1))
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.15), ncol=3, frameon=False)
    return fig


def save_figures(directory, pairs, truth, decisions, sweep):
    directory = Path(directory)
    for name, fig in (("score_distribution", plot_scores(pairs, [r for r in truth if r["split"] == "development"])),
                      ("threshold_tradeoffs", plot_thresholds(sweep)), ("decisions_by_town", plot_decisions(decisions))):
        fig.savefig(directory / f"{name}.png", dpi=150)
        plt.close(fig)
