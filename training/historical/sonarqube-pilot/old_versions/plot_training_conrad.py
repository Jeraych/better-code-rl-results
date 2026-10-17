import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


# Dashboard adapted for train_conrad.py / train_mvp_tests.py logs.
# It visualises:
# - trainer_state.json metrics from TRL/GRPO
# - samples.csv produced by log_completion()
# - optional eval_*.csv files produced by evaluate_model()
#
# Required packages:
#   pip install plotly pandas


STATUS_COLUMNS = [
    "format_status",
    "compile_status",
    "runtime_status",
    "test_status",
]

REWARD_COLUMNS = [
    "reward_format",
    "reward_compile",
    "reward_tests",
    "reward_total",
]

TOKEN_COLUMNS = [
    "prompt_token_length",
    "completion_token_length",
]


# ── Loading helpers ────────────────────────────────────────────────────────────

def load_trainer_history(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        state = json.load(file)
    return state.get("log_history", [])


def load_csv(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def numeric(value):
    try:
        if value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def latest_file(pattern: str) -> Path | None:
    files = sorted(Path(".").glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return files[0] if files else None


def latest_log_dir() -> Path | None:
    dirs = [path for path in Path("grpo_mvp_logs").glob("*") if path.is_dir()]
    if not dirs:
        return None
    return sorted(dirs, key=lambda path: path.stat().st_mtime, reverse=True)[0]


def discover_eval_files(log_dir: Path | None) -> list[Path]:
    files: list[Path] = []
    if log_dir and log_dir.exists():
        files.extend(sorted(log_dir.glob("eval_*.csv")))
    files.extend(sorted(Path(".").glob("grpo_mvp_logs/*/eval_*.csv")))
    seen = set()
    unique = []
    for file in files:
        resolved = file.resolve()
        if resolved not in seen and file.exists():
            unique.append(file)
            seen.add(resolved)
    return unique


# ── Pandas windowing ───────────────────────────────────────────────────────────

def window_xy(
    xs: Iterable[float],
    ys: Iterable[float],
    rolling_window: int = 1,
    recent_steps: int | None = None,
) -> tuple[list[float], list[float]]:
    xs = list(xs)
    ys = list(ys)
    if not xs or not ys:
        return xs, ys

    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit("pandas is not installed. Install it with: pip install pandas") from exc

    frame = pd.DataFrame({"step": xs, "value": ys}).dropna().sort_values("step")

    if recent_steps is not None and recent_steps > 0 and not frame.empty:
        latest_step = frame["step"].max()
        frame = frame[frame["step"] >= latest_step - recent_steps]

    if rolling_window > 1 and not frame.empty:
        frame["value"] = frame["value"].rolling(window=rolling_window, min_periods=1).mean()

    return frame["step"].tolist(), frame["value"].tolist()


# ── Trainer history ────────────────────────────────────────────────────────────

def history_series(history: list[dict], key: str) -> tuple[list[float], list[float]]:
    xs, ys = [], []
    for row in history:
        x = numeric(row.get("step"))
        y = numeric(row.get(key))
        if x is not None and y is not None:
            xs.append(x)
            ys.append(y)
    return xs, ys


def available_reward_keys(history: list[dict]) -> list[str]:
    keys = set()
    for row in history:
        for key in row:
            if key.startswith("rewards/") and key.endswith("/mean"):
                keys.add(key)
    return sorted(keys)


# ── Sample log aggregations from train_conrad.py ───────────────────────────────

def group_by_step(samples: list[dict]) -> dict[int, list[dict]]:
    by_step: dict[int, list[dict]] = defaultdict(list)
    for row in samples:
        step = numeric(row.get("step"))
        if step is not None:
            by_step[int(step)].append(row)
    return by_step


def mean(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def sample_step_stats(samples: list[dict]) -> dict[str, dict[int, float]]:
    by_step = group_by_step(samples)
    stats: dict[str, dict[int, float]] = defaultdict(dict)

    for step, rows in by_step.items():
        count = len(rows)
        if count == 0:
            continue

        # Status rates that directly reflect train_conrad.py diagnostics.
        stats["format_ok_rate"][step] = sum(row.get("format_status") == "ok" for row in rows) / count
        stats["compile_ok_rate"][step] = sum(row.get("compile_status") == "ok" for row in rows) / count
        stats["runtime_ok_rate"][step] = sum(row.get("runtime_status") == "ok" for row in rows) / count
        stats["test_pass_rate"][step] = sum(row.get("test_status") == "passed" for row in rows) / count
        stats["score_6_rate"][step] = sum(numeric(row.get("reward_total")) == 6.0 for row in rows) / count
        stats["no_code_rate"][step] = sum(row.get("failure_reason") == "no_code_extracted" for row in rows) / count
        stats["syntax_error_rate"][step] = sum(row.get("failure_reason") == "syntax_error" for row in rows) / count
        stats["timeout_rate"][step] = sum(row.get("failure_reason") == "timeout" or row.get("test_status") == "timeout" for row in rows) / count

        # Reward components from total_reward_from_diagnostic():
        # total = 0.2*format + 0.8*compile + 5.0*tests.
        for column in REWARD_COLUMNS:
            value = mean([numeric(row.get(column)) for row in rows])
            if value is not None:
                stats[f"mean_{column}"][step] = value

        # Token lengths from log_completion().
        for column in TOKEN_COLUMNS:
            value = mean([numeric(row.get(column)) for row in rows])
            if value is not None:
                stats[f"mean_{column}"][step] = value

        # Useful spread signal: are generations diverse enough to give GRPO a learning signal?
        totals = [numeric(row.get("reward_total")) for row in rows]
        totals = [v for v in totals if v is not None]
        if len(totals) >= 2:
            avg = sum(totals) / len(totals)
            variance = sum((v - avg) ** 2 for v in totals) / len(totals)
            stats["reward_total_std_by_step"][step] = variance ** 0.5

    return stats


def value_counts(rows: list[dict], column: str) -> Counter:
    counts = Counter()
    for row in rows:
        value = row.get(column) or "none"
        counts[value] += 1
    return counts


def final_summary(samples: list[dict]) -> dict[str, float | int | str]:
    if not samples:
        return {}
    total = len(samples)
    reward_values = [numeric(row.get("reward_total")) for row in samples]
    reward_values = [v for v in reward_values if v is not None]
    return {
        "samples": total,
        "avg_reward_total": round(sum(reward_values) / len(reward_values), 4) if reward_values else 0,
        "format_ok_rate": round(sum(row.get("format_status") == "ok" for row in samples) / total, 4),
        "compile_ok_rate": round(sum(row.get("compile_status") == "ok" for row in samples) / total, 4),
        "runtime_ok_rate": round(sum(row.get("runtime_status") == "ok" for row in samples) / total, 4),
        "test_pass_rate": round(sum(row.get("test_status") == "passed" for row in samples) / total, 4),
        "score_6_rate": round(sum(numeric(row.get("reward_total")) == 6.0 for row in samples) / total, 4),
    }


# ── Eval aggregations ──────────────────────────────────────────────────────────

def load_eval_rows(eval_files: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for file in eval_files:
        for row in load_csv(file):
            row["eval_file"] = str(file)
            row["eval_name"] = row.get("label") or file.stem
            rows.append(row)
    return rows


def eval_summary_rows(eval_rows: list[dict]) -> list[dict]:
    by_name: dict[str, list[dict]] = defaultdict(list)
    for row in eval_rows:
        by_name[row.get("eval_name", "eval")].append(row)

    summaries = []
    for name, rows in sorted(by_name.items()):
        total = len(rows)
        if total == 0:
            continue
        rewards = [numeric(row.get("reward_total")) for row in rows]
        rewards = [v for v in rewards if v is not None]
        summaries.append({
            "name": name,
            "rows": total,
            "avg_reward": sum(rewards) / len(rewards) if rewards else 0,
            "format_ok_rate": sum(row.get("format_status") == "ok" for row in rows) / total,
            "compile_ok_rate": sum(row.get("compile_status") == "ok" for row in rows) / total,
            "runtime_ok_rate": sum(row.get("runtime_status") == "ok" for row in rows) / total,
            "test_pass_rate": sum(row.get("test_status") == "passed" for row in rows) / total,
        })
    return summaries


# ── Plot helpers ───────────────────────────────────────────────────────────────

def add_xy_line(fig, row: int, col: int, xs, ys, name: str, rolling_window: int, recent_steps: int | None) -> None:
    if not xs or not ys:
        return
    import plotly.graph_objects as go

    xs, ys = window_xy(xs, ys, rolling_window, recent_steps)
    if not xs or not ys:
        return
    suffix = f" ({rolling_window}-pt avg)" if rolling_window > 1 else ""
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=f"{name}{suffix}"), row=row, col=col)


def add_history_line(fig, row: int, col: int, history: list[dict], key: str, name: str, rolling_window: int, recent_steps: int | None) -> None:
    xs, ys = history_series(history, key)
    add_xy_line(fig, row, col, xs, ys, name, rolling_window, recent_steps)


def add_stat_line(fig, row: int, col: int, stats: dict[str, dict[int, float]], key: str, name: str, rolling_window: int, recent_steps: int | None) -> None:
    values = stats.get(key, {})
    if not values:
        return
    xs = sorted(values)
    ys = [values[x] for x in xs]
    add_xy_line(fig, row, col, xs, ys, name, rolling_window, recent_steps)


def add_bar(fig, row: int, col: int, counts: Counter, name: str, top_n: int = 12) -> None:
    if not counts:
        return
    import plotly.graph_objects as go

    items = counts.most_common(top_n)
    fig.add_trace(go.Bar(x=[item[0] for item in items], y=[item[1] for item in items], name=name), row=row, col=col)


# ── Dashboard ─────────────────────────────────────────────────────────────────

def build_dashboard(
    history: list[dict],
    samples: list[dict],
    eval_rows: list[dict],
    output: Path,
    rolling_window: int = 10,
    recent_steps: int | None = None,
) -> None:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError as exc:
        raise SystemExit("Plotly is not installed. Install it with: pip install plotly") from exc

    stats = sample_step_stats(samples)
    eval_summaries = eval_summary_rows(eval_rows)

    fig = make_subplots(
        rows=5,
        cols=2,
        specs=[
            [{}, {}],
            [{}, {}],
            [{}, {}],
            [{}, {}],
            [{"type": "table"}, {"type": "table"}],
        ],
        subplot_titles=[
            "Reward components from train_conrad.py",
            "Core success rates",
            "Failure rates to debug",
            "Trainer GRPO signals",
            "Completion/token lengths",
            "Reward spread / clipping",
            "Failure reasons",
            "Test status counts",
            "Training summary",
            "Evaluation summaries",
        ],
    )

    # 1. Raw reward components and weighted total.
    add_stat_line(fig, 1, 1, stats, "mean_reward_total", "mean reward_total / 6", rolling_window, recent_steps)
    add_stat_line(fig, 1, 1, stats, "mean_reward_format", "format reward", rolling_window, recent_steps)
    add_stat_line(fig, 1, 1, stats, "mean_reward_compile", "compile reward", rolling_window, recent_steps)
    add_stat_line(fig, 1, 1, stats, "mean_reward_tests", "tests reward", rolling_window, recent_steps)

    # 2. Main outcome rates.
    add_stat_line(fig, 1, 2, stats, "format_ok_rate", "format ok", rolling_window, recent_steps)
    add_stat_line(fig, 1, 2, stats, "compile_ok_rate", "compile ok", rolling_window, recent_steps)
    add_stat_line(fig, 1, 2, stats, "runtime_ok_rate", "runtime ok", rolling_window, recent_steps)
    add_stat_line(fig, 1, 2, stats, "test_pass_rate", "tests passed", rolling_window, recent_steps)
    add_stat_line(fig, 1, 2, stats, "score_6_rate", "perfect 6.0", rolling_window, recent_steps)

    # 3. Common failure mode rates.
    add_stat_line(fig, 2, 1, stats, "no_code_rate", "no code extracted", rolling_window, recent_steps)
    add_stat_line(fig, 2, 1, stats, "syntax_error_rate", "syntax error", rolling_window, recent_steps)
    add_stat_line(fig, 2, 1, stats, "timeout_rate", "timeout", rolling_window, recent_steps)

    # 4. Trainer-level GRPO/TRL signals.
    add_history_line(fig, 2, 2, history, "reward", "trainer reward", rolling_window, recent_steps)
    add_history_line(fig, 2, 2, history, "loss", "loss", rolling_window, recent_steps)
    add_history_line(fig, 2, 2, history, "kl", "kl", rolling_window, recent_steps)
    add_history_line(fig, 2, 2, history, "grad_norm", "grad_norm", rolling_window, recent_steps)
    add_history_line(fig, 2, 2, history, "learning_rate", "learning_rate", rolling_window, recent_steps)
    for key in available_reward_keys(history):
        add_history_line(
            fig,
            2,
            2,
            history,
            key,
            key.removeprefix("rewards/").removesuffix("/mean"),
            rolling_window,
            recent_steps,
        )

    # 5. Length metrics from both trainer_state and sample diagnostics.
    add_history_line(fig, 3, 1, history, "completion_length", "trainer completion_length", rolling_window, recent_steps)
    add_history_line(fig, 3, 1, history, "completions/mean_length", "trainer mean_length", rolling_window, recent_steps)
    add_history_line(fig, 3, 1, history, "completions/max_length", "trainer max_length", rolling_window, recent_steps)
    add_stat_line(fig, 3, 1, stats, "mean_completion_token_length", "logged completion tokens", rolling_window, recent_steps)
    add_stat_line(fig, 3, 1, stats, "mean_prompt_token_length", "logged prompt tokens", rolling_window, recent_steps)

    # 6. Reward spread and clipping. Low std means generations are too similar / no useful ranking signal.
    add_stat_line(fig, 3, 2, stats, "reward_total_std_by_step", "logged reward_total std", rolling_window, recent_steps)
    add_history_line(fig, 3, 2, history, "reward_std", "trainer reward_std", rolling_window, recent_steps)
    add_history_line(fig, 3, 2, history, "frac_reward_zero_std", "frac_reward_zero_std", rolling_window, recent_steps)
    add_history_line(fig, 3, 2, history, "completions/clipped_ratio", "clipped_ratio", rolling_window, recent_steps)

    # 7/8. Counts.
    add_bar(fig, 4, 1, value_counts(samples, "failure_reason"), "failure reasons")
    add_bar(fig, 4, 2, value_counts(samples, "test_status"), "test status")
    add_bar(fig, 4, 2, value_counts(samples, "compile_status"), "compile status")

    # 9. Table summary for quick read.
    summary = final_summary(samples)
    if summary:
        fig.add_trace(
            go.Table(
                header=dict(values=["metric", "value"]),
                cells=dict(values=[list(summary.keys()), list(summary.values())]),
            ),
            row=5,
            col=1,
        )

    # 10. Eval comparison table if eval csvs exist.
    if eval_summaries:
        fig.add_trace(
            go.Table(
                header=dict(values=["eval", "rows", "avg_reward", "format_ok", "compile_ok", "runtime_ok", "test_pass"]),
                cells=dict(values=[
                    [r["name"] for r in eval_summaries],
                    [r["rows"] for r in eval_summaries],
                    [round(r["avg_reward"], 4) for r in eval_summaries],
                    [round(r["format_ok_rate"], 4) for r in eval_summaries],
                    [round(r["compile_ok_rate"], 4) for r in eval_summaries],
                    [round(r["runtime_ok_rate"], 4) for r in eval_summaries],
                    [round(r["test_pass_rate"], 4) for r in eval_summaries],
                ]),
            ),
            row=5,
            col=2,
        )

    fig.update_layout(
        title=(
            "Conrad GRPO Coding Training Dashboard "
            f"| rolling_window={rolling_window}, recent_steps={recent_steps or 'all'}"
        ),
        height=1700,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=-0.08, xanchor="left", x=0),
    )
    fig.update_xaxes(title_text="step")
    fig.write_html(str(output), include_plotlyjs="cdn")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a Plotly dashboard adapted for train_conrad.py GRPO coding logs."
    )
    parser.add_argument(
        "--trainer-state",
        type=Path,
        default=None,
        help="Path to trainer_state.json. Defaults to latest grpo_mvp_output/**/trainer_state.json.",
    )
    parser.add_argument(
        "--samples",
        type=Path,
        default=None,
        help="Path to samples.csv. Defaults to latest grpo_mvp_logs/*/samples.csv.",
    )
    parser.add_argument(
        "--eval-file",
        action="append",
        type=Path,
        default=[],
        help="Optional eval CSV file. Can be passed multiple times. Defaults to eval_*.csv in grpo_mvp_logs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("conrad_training_dashboard.html"),
        help="Output HTML file.",
    )
    parser.add_argument(
        "--rolling-window",
        type=int,
        default=10,
        help="Pandas trailing rolling mean window size in plotted points. Use 1 for raw values.",
    )
    parser.add_argument(
        "--recent-steps",
        type=int,
        default=None,
        help="Only plot the most recent N training steps. Omit to show all steps.",
    )
    args = parser.parse_args()

    trainer_state = args.trainer_state or latest_file("grpo_mvp_output/**/trainer_state.json")
    log_dir = latest_log_dir()
    samples = args.samples or latest_file("grpo_mvp_logs/*/samples.csv")
    eval_files = args.eval_file or discover_eval_files(log_dir)

    history = load_trainer_history(trainer_state)
    sample_rows = load_csv(samples)
    eval_rows = load_eval_rows(eval_files)

    print(f"Trainer state: {trainer_state if trainer_state else 'not found'}")
    print(f"Sample diagnostics: {samples if samples else 'not found'}")
    print(f"Eval files: {', '.join(str(f) for f in eval_files) if eval_files else 'none found'}")
    print(f"Trainer log rows: {len(history)}")
    print(f"Sample rows: {len(sample_rows)}")
    print(f"Eval rows: {len(eval_rows)}")

    build_dashboard(
        history=history,
        samples=sample_rows,
        eval_rows=eval_rows,
        output=args.output,
        rolling_window=max(1, args.rolling_window),
        recent_steps=args.recent_steps,
    )

    print(f"Wrote {args.output}")
    print("Key panels to watch:")
    print("- reward_total / tests reward / test_pass_rate should trend upward")
    print("- no_code_extracted, syntax_error, timeout should trend downward")
    print("- reward_total_std should not collapse to zero too early")
    print("- holdout eval test_pass_rate matters more than train-only improvement")


if __name__ == "__main__":
    main()
