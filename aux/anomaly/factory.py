from aux.anomaly.detector import AnomalyDetector


class AnomalyDetectorFactory:
    def create(self, settings, parent=None):
        return AnomalyDetector(settings, parent=parent)
