#!/usr/bin/env python3
import curses
import subprocess
import time
from collections import deque
import math

import matplotlib.pyplot as plt


def list_processes(limit=400):
    """
    Returns list of (pid:int, comm:str, args:str) for running processes.
    """
    out = subprocess.check_output(
        ["ps", "-A", "-o", "pid=,comm=,args="],
        text=True,
        stderr=subprocess.DEVNULL,
    )
    procs = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        pid = int(parts[0])
        comm = parts[1]
        args = parts[2] if len(parts) >= 3 else comm
        procs.append((pid, comm, args))
    procs.sort(key=lambda x: x[0], reverse=True)
    return procs[:limit]


def get_metrics(pid: int):
    """
    Returns (cpu_percent, rss_mb) for a pid using macOS `ps`.
    """
    try:
        out = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "%cpu=,rss="],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if not out:
            return None
        cpu_s, rss_s = out.split()
        cpu = float(cpu_s)
        rss_kb = int(rss_s)
        return cpu, rss_kb / 1024.0
    except Exception:
        return None


def prompt_label(stdscr, default):
    curses.echo()
    stdscr.clear()
    stdscr.addstr(0, 0, f"Label (default: {default}): ")
    stdscr.refresh()
    s = stdscr.getstr(1, 0).decode("utf-8", errors="ignore").strip()
    curses.noecho()
    return s or default


def process_selector(stdscr):
    curses.curs_set(0)
    procs = list_processes()
    filter_text = ""
    idx = 0
    selected = []

    while True:
        ft = filter_text.lower()
        view = [
            p for p in procs
            if ft in p[1].lower() or ft in p[2].lower() or ft in str(p[0])
        ]
        if not view:
            idx = 0
        else:
            idx = max(0, min(idx, len(view) - 1))

        stdscr.clear()
        h, w = stdscr.getmaxyx()
        stdscr.addstr(0, 0, "Select 2 processes  (type to filter, ↑/↓ move, Enter select, q quit)")
        stdscr.addstr(1, 0, f"Filter: {filter_text}")
        stdscr.addstr(2, 0, f"Selected: {', '.join([f'{p[0]}' for p in selected])}")

        start_row = 4
        max_rows = h - start_row - 1
        top = max(0, idx - max_rows // 2)
        bottom = min(len(view), top + max_rows)
        top = max(0, bottom - max_rows)

        for row, i in enumerate(range(top, bottom), start=start_row):
            pid, comm, args = view[i]
            line = f"{pid:>6}  {comm:<18}  {args[:max(0, w - 30)]}"
            if i == idx:
                stdscr.addstr(row, 0, line[:w - 1], curses.A_REVERSE)
            else:
                stdscr.addstr(row, 0, line[:w - 1])

        stdscr.refresh()
        ch = stdscr.getch()

        if ch in (ord("q"), ord("Q")):
            raise SystemExit(0)
        elif ch == curses.KEY_UP:
            idx -= 1
        elif ch == curses.KEY_DOWN:
            idx += 1
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            filter_text = filter_text[:-1]
            idx = 0
        elif ch in (10, 13):  # Enter
            if view:
                chosen = view[idx]
                if chosen not in selected:
                    selected.append(chosen)
                if len(selected) == 2:
                    return selected
        elif 32 <= ch <= 126:
            filter_text += chr(ch)
            idx = 0


def main():
    selected = curses.wrapper(process_selector)

    def label_wrapper(stdscr):
        (pid1, comm1, _args1), (pid2, comm2, _args2) = selected
        label1 = prompt_label(stdscr, f"{comm1} ({pid1})")
        label2 = prompt_label(stdscr, f"{comm2} ({pid2})")

        stdscr.clear()
        stdscr.addstr(0, 0, "Sample interval seconds (default 1.0): ")
        curses.echo()
        interval_s = stdscr.getstr(1, 0).decode("utf-8", errors="ignore").strip() or "1.0"
        stdscr.addstr(3, 0, "Keep last N samples (default 120): ")
        window_s = stdscr.getstr(4, 0).decode("utf-8", errors="ignore").strip() or "120"
        curses.noecho()
        return pid1, pid2, label1, label2, float(interval_s), int(window_s)

    pid1, pid2, name1, name2, interval, window = curses.wrapper(label_wrapper)

    t = deque(maxlen=window)
    cpu1 = deque(maxlen=window)
    cpu2 = deque(maxlen=window)
    mem1 = deque(maxlen=window)
    mem2 = deque(maxlen=window)

    plt.ion()
    fig, (ax_cpu, ax_mem) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)

    (line_cpu1,) = ax_cpu.plot([], [], label=name1)
    (line_cpu2,) = ax_cpu.plot([], [], label=name2)
    ax_cpu.set_ylabel("CPU (%)")
    ax_cpu.set_title("CPU usage over time")
    ax_cpu.legend()
    ax_cpu.grid(True)

    (line_mem1,) = ax_mem.plot([], [], label=name1)
    (line_mem2,) = ax_mem.plot([], [], label=name2)
    ax_mem.set_ylabel("RSS (MB)")
    ax_mem.set_title("Memory usage (RSS) over time")
    ax_mem.set_xlabel("Time (seconds)")
    ax_mem.legend()
    ax_mem.grid(True)

    start = time.time()
    print("Sampling... Ctrl+C to stop.")

    try:
        while True:
            now = time.time() - start

            m1 = get_metrics(pid1)
            m2 = get_metrics(pid2)

            c1, r1 = m1 if m1 else (math.nan, math.nan)
            c2, r2 = m2 if m2 else (math.nan, math.nan)

            t.append(now)
            cpu1.append(c1)
            cpu2.append(c2)
            mem1.append(r1)
            mem2.append(r2)

            line_cpu1.set_data(t, cpu1)
            line_cpu2.set_data(t, cpu2)
            line_mem1.set_data(t, mem1)
            line_mem2.set_data(t, mem2)

            ax_cpu.relim()
            ax_cpu.autoscale_view()

            # Memory: pure autoscale (no forced y=0 baseline)
            ax_mem.relim()
            ax_mem.autoscale_view()

            fig.tight_layout()
            fig.canvas.draw()
            fig.canvas.flush_events()

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()

