import numpy as np
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class _DetectionTask(QRunnable):
    def __init__(self, detector, cnl, points, version, completed):
        super().__init__()
        self.detector = detector
        self.cnl = cnl
        self.points = points
        self.version = version
        self.completed = completed

    @Slot()
    def run(self):
        results = self.detector.detect(self.points)
        self.completed.emit(self.cnl, self.version, results)


class ThreadedAnomalyDetectionRunner(QObject):
    completed = Signal(object, int, object)

    def __init__(self, detector, parent=None):
        super().__init__(parent)
        self.detector = detector
        self.thread_pool = QThreadPool.globalInstance()

    def detect(self, cnl, points, version: int):
        task = _DetectionTask(
            self.detector,
            cnl,
            np.asarray(points, dtype=np.float64).copy(),
            version,
            self.completed,
        )
        self.thread_pool.start(task)


class NoOpAnomalyDetectionRunner(QObject):
    completed = Signal(object, int, object)

    def detect(self, cnl, points, version: int):
        self.completed.emit(cnl, version, ())
