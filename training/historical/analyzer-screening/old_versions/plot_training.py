import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_trainer_history(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        state = json.load(file)
    return state.get("log_history", [])


def load_samples(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def numeric(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def window_series(
    xs: list[float],
    ys: list[float],
    rolling_window: int = 1,
    recent_steps: int | None = None,
) -> tuple[list[float], list[float]]:
    """Apply an optional recent-step view and pandas rolling mean.

    rolling_window is a point-based trailing window. For example, 10 means each
    plotted point is the mean of the current point and previous 9 points.
    recent_steps keeps only the last N training steps on the x-axis.
    """
    if not xs or not ys:
        return xs, ys

    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit(
            "pandas is not installed. Install it in your environment with: pip install pandas"
        ) from exc

    frame = pd.DataFrame({"step": xs, "value": ys}).sort_values("step")

    if recent_steps is not None and recent_steps > 0:
        latest_step = frame["step"].max()
        frame = frame[frame["step"] >= latest_step - recent_steps]

    if rolling_window > 1:
        frame["value"] = frame["value"].rolling(
            window=rolling_window, min_periods=1
        ).mean()

    return frame["step"].tolist(), frame["value"].tolist()


def series(history: list[dict], key: str) -> tuple[list[float], list[float]]:
    xs = []
    ys = []
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


def sample_step_stats(samples: list[dict]) -> dict[str, dict[int, float]]:
    by_step = defaultdict(list)
    for row in samples:
        step = numeric(row.get("step"))
        if step is None:
            continue
        by_step[int(step)].append(row)

    stats = {
        "compile_ok": {},
        "runtime_ok": {},
        "test_passed": {},
        "format_ok": {},
        "mean_compile_reward": {},
        "mean_test_reward": {},
        "mean_total_reward": {},
    }

    for step, rows in by_step.items():
        count = len(rows)
        compile_rewards = [numeric(row.get("reward_compile")) for row in rows]
        test_rewards = [numeric(row.get("reward_tests")) for row in rows]
        total_rewards = [numeric(row.get("reward_total")) for row in rows]
        compile_rewards = [value for value in compile_rewards if value is not None]
        test_rewards = [value for value in test_rewards if value is not None]
        total_rewards = [value for value in total_rewards if value is not None]

        stats["compile_ok"][step] = sum(row.get("compile_status") == "ok" for row in rows) / count
        stats["runtime_ok"][step] = sum(row.get("runtime_status") == "ok" for row in rows) / count
        stats["test_passed"][step] = sum(row.get("test_status") == "passed" for row in rows) / count
        stats["format_ok"][step] = sum(row.get("format_status") == "ok" for row in rows) / count
        if compile_rewards:
            stats["mean_compile_reward"][step] = sum(compile_rewards) / len(compile_rewards)
        if test_rewards:
            stats["mean_test_reward"][step] = sum(test_rewards) / len(test_rewards)
        if total_rewards:
            stats["mean_total_reward"][step] = sum(total_rewards) / len(total_rewards)

    return stats


def failure_counts(samples: list[dict]) -> Counter:
    counts = Counter()
    for row in samples:
        reason = row.get("failure_reason") or "none"
        counts[reason] += 1
    return counts


def add_line(
    fig,
    row: int,
    col: int,
    history: list[dict],
    key: str,
    name: str,
    rolling_window: int = 1,
    recent_steps: int | None = None,
) -> None:
    xs, ys = series(history, key)
    xs, ys = window_series(xs, ys, rolling_window, recent_steps)
    if xs and ys:
        import plotly.graph_objects as go

        suffix = f" ({rolling_window}-pt rolling avg)" if rolling_window > 1 else ""
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=f"{name}{suffix}"), row=row, col=col)


def add_step_stat_line(
    fig,
    row: int,
    col: int,
    stats: dict[int, float],
    name: str,
    rolling_window: int = 1,
    recent_steps: int | None = None,
) -> None:
    if not stats:
        return
    import plotly.graph_objects as go

    xs = sorted(stats)
    ys = [stats[x] for x in xs]
    xs, ys = window_series(xs, ys, rolling_window, recent_steps)
    suffix = f" ({rolling_window}-pt rolling avg)" if rolling_window > 1 else ""
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=f"{name}{suffix}"), row=row, col=col)


def build_dashboard(
    history: list[dict],
    samples: list[dict],
    output: Path,
    rolling_window: int = 10,
    recent_steps: int | None = None,
) -> None:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError as exc:
        raise SystemExit(
            "Plotly is not installed. Install it in your environment with: pip install plotly"
        ) from exc

    fig = make_subplots(
        rows=3,
        cols=2,
        subplot_titles=[
            "Trainer reward/loss",
            "Reward function means",
            "Completion lengths",
            "Clipping and reward variance",
            "Sample diagnostics by step",
            "Failure reasons",
        ],
    )

    add_line(fig, 1, 1, history, "reward", "trainer reward", rolling_window, recent_steps)
    add_line(fig, 1, 1, history, "loss", "loss", rolling_window, recent_steps)
    add_line(fig, 1, 1, history, "kl", "kl", rolling_window, recent_steps)

    for key in available_reward_keys(history):
        add_line(fig, 1, 2, history, key, key.removeprefix("rewards/").removesuffix("/mean"), rolling_window, recent_steps)

    add_line(fig, 2, 1, history, "completion_length", "completion_length", rolling_window, recent_steps)
    add_line(fig, 2, 1, history, "completions/mean_length", "mean_length", rolling_window, recent_steps)
    add_line(fig, 2, 1, history, "completions/max_length", "max_length", rolling_window, recent_steps)
    add_line(fig, 2, 1, history, "completions/mean_terminated_length", "mean_terminated_length", rolling_window, recent_steps)

    add_line(fig, 2, 2, history, "completions/clipped_ratio", "clipped_ratio", rolling_window, recent_steps)
    add_line(fig, 2, 2, history, "frac_reward_zero_std", "frac_reward_zero_std", rolling_window, recent_steps)
    add_line(fig, 2, 2, history, "reward_std", "reward_std", rolling_window, recent_steps)

    stats = sample_step_stats(samples)
    add_step_stat_line(fig, 3, 1, stats["format_ok"], "format_ok_rate", rolling_window, recent_steps)
    add_step_stat_line(fig, 3, 1, stats["compile_ok"], "compile_ok_rate", rolling_window, recent_steps)
    add_step_stat_line(fig, 3, 1, stats["runtime_ok"], "runtime_ok_rate", rolling_window, recent_steps)
    add_step_stat_line(fig, 3, 1, stats["test_passed"], "test_pass_rate", rolling_window, recent_steps)
    add_step_stat_line(fig, 3, 1, stats["mean_compile_reward"], "mean_compile_reward", rolling_window, recent_steps)
    add_step_stat_line(fig, 3, 1, stats["mean_test_reward"], "mean_test_reward", rolling_window, recent_steps)
    add_step_stat_line(fig, 3, 1, stats["mean_total_reward"], "mean_total_reward", rolling_window, recent_steps)

    failures = failure_counts(samples)
    if failures:
        fig.add_trace(
            go.Bar(x=list(failures.keys()), y=list(failures.values()), name="failure reasons"),
            row=3,
            col=2,
        )

    fig.update_layout(
        title=f"GRPO Training Diagnostics | rolling_window={rolling_window}, recent_steps={recent_steps or 'all'}",
        height=1100,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=-0.12, xanchor="left", x=0),
    )
    fig.update_xaxes(title_text="step")
    fig.write_html(str(output), include_plotlyjs="cdn")


def latest_file(pattern: str) -> Path | None:
    files = sorted(Path(".").glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return files[0] if files else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Plotly dashboard from GRPO trainer logs.")
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
        help="Path to samples.csv. Defaults to latest grpo_mvp_logs/*/samples.csv if present.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("training_dashboard.html"),
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
    if trainer_state is None:
        raise SystemExit("Could not find trainer_state.json. Pass --trainer-state explicitly.")

    samples = args.samples or latest_file("grpo_mvp_logs/*/samples.csv")
    history = load_trainer_history(trainer_state)
    sample_rows = load_samples(samples)

    print(f"Trainer state: {trainer_state}")
    print(f"Sample diagnostics: {samples if samples else 'not found'}")
    print(f"Trainer log rows: {len(history)}")
    print(f"Sample rows: {len(sample_rows)}")

    build_dashboard(
        history,
        sample_rows,
        args.output,
        rolling_window=max(1, args.rolling_window),
        recent_steps=args.recent_steps,
    )
    print(f"Wrote {args.output}")
    print(f"Rolling window: {max(1, args.rolling_window)} plotted points")
    print(f"Recent steps shown: {args.recent_steps if args.recent_steps else 'all'}")


if __name__ == "__main__":
    main()
