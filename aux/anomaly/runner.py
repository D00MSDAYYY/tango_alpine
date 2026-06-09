import numpy as np
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot


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
        results = self.detector.detect_points(self.points)
        self.completed.emit(self.cnl, self.version, results)


class ThreadedAnomalyDetectionRunner(QObject):
    completed = Signal(object, int, object)

    def __init__(self, detector, parent=None):
        super().__init__(parent)
        self.detector = detector
        self._running_cnls = set()
        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(2)
        self.completed.connect(
            self._on_detection_completed,
            Qt.ConnectionType.QueuedConnection,
        )

    def detect(self, cnl, points, version: int) -> bool:
        if cnl in self._running_cnls:
            return False
        self._running_cnls.add(cnl)
        task = _DetectionTask(
            self.detector,
            cnl,
            np.asarray(points, dtype=np.float64),
            version,
            self.completed,
        )
        self.thread_pool.start(task)
        return True

    def _on_detection_completed(self, cnl, version, results):
        self._running_cnls.discard(cnl)


class NoOpAnomalyDetectionRunner(QObject):
    completed = Signal(object, int, object)

    def detect(self, cnl, points, version: int) -> bool:
        self.completed.emit(cnl, version, ())
        return True
