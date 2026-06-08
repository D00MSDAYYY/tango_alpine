import sys
import time

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from aux.plot.curve import Pen
from aux.plot.vispy_plot_widget import MAX_BACKGROUND_LINES, VispyPlot


POINT_COUNT = 10_000_000
BATCH_POINTS = 50_000
TIME_RANGE_SEC = 200.0
HISTORY_RANGE_SEC = TIME_RANGE_SEC * MAX_BACKGROUND_LINES
TOTAL_RANGE_SEC = TIME_RANGE_SEC + HISTORY_RANGE_SEC


class OnlineStressSource:
    def __init__(self):
        self.points = np.empty((POINT_COUNT, 2), dtype=np.float64)
        self.count = 0
        self.started_at = time.perf_counter()
        self.sim_start_ts = time.time() - TOTAL_RANGE_SEC
        self.dt = TOTAL_RANGE_SEC / max(1, POINT_COUNT - 1)

    def append_batch(self):
        if self.count >= POINT_COUNT:
            return self.points

        end = min(self.count + BATCH_POINTS, POINT_COUNT)
        indexes = np.arange(self.count, end, dtype=np.float64)
        timestamps = self.sim_start_ts + indexes * self.dt
        phase = indexes * self.dt / 8.0

        self.points[self.count:end, 0] = timestamps
        self.points[self.count:end, 1] = (
            np.sin(phase)
            + 0.08 * np.sin(phase * 11.0)
            + 0.03 * np.sin(phase * 37.0)
        )
        self.count = end
        return self.points[: self.count]

    def done(self):
        return self.count >= POINT_COUNT

    def progress_text(self):
        elapsed = max(time.perf_counter() - self.started_at, 1e-9)
        rate = self.count / elapsed
        return (
            f"{self.count:,}/{POINT_COUNT:,} points, "
            f"{rate:,.0f} points/s, elapsed={elapsed:.2f} s"
        )


def main():
    app = QApplication(sys.argv)

    plot = VispyPlot()
    plot.resize(1400, 850)
    plot.setWindowTitle("Vispy online stress test: 5,000,000 points")
    plot.set_axis_labels("time", "value")
    plot.set_time_range(TIME_RANGE_SEC)
    plot.set_history_range(HISTORY_RANGE_SEC)
    plot.set_max_plot_points(POINT_COUNT)

    curve = plot.add_curve(Pen(color="cyan", width=1.0, show_dots=False))
    source = OnlineStressSource()

    draw_count = 0
    last_draw_at = time.perf_counter()

    def on_draw(event):
        nonlocal draw_count, last_draw_at
        draw_count += 1
        now = time.perf_counter()
        if now - last_draw_at >= 5.0:
            print(f"draw fps: {draw_count / (now - last_draw_at):.1f}")
            draw_count = 0
            last_draw_at = now

    def push_next_batch():
        started = time.perf_counter()
        data = source.append_batch()
        curve.set_data(data, refresh=False)
        plot.refresh()
        elapsed = time.perf_counter() - started

        if source.count % 250_000 == 0 or source.done():
            print(f"{source.progress_text()}, last batch+refresh={elapsed:.3f} s")

        if source.done():
            print("online stress test finished")
            timer.stop()

    plot.canvas.events.draw.connect(on_draw)

    timer = QTimer()
    timer.setInterval(0)
    timer.timeout.connect(push_next_batch)

    print(
        "online stress test started: "
        f"batch={BATCH_POINTS:,}, visible={TIME_RANGE_SEC:.0f} s, "
        f"history={HISTORY_RANGE_SEC:.0f} s, history lines={MAX_BACKGROUND_LINES}"
    )
    plot.show()
    timer.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
