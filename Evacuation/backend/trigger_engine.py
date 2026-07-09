from models import IncidentPayload
from shapely.geometry import Polygon

class TriggerEngine:
    def __init__(self):
        # We could load static polygons of settlements here.
        pass

    def evaluate_risk(self, telemetry) -> bool:
        """
        Evaluates the telemetry against the Mayday protocol thresholds.
        (T_{impact} <= 120 mins) AND (C_{pred} >= 0.85)
        """
        if telemetry.time_to_impact_mins <= 120 and telemetry.confidence_coefficient >= 0.85:
            return True
        return False

    def check_trigger(self, incident: IncidentPayload) -> bool:
        """
        Returns True if autonomous dispatch should be triggered.
        """
        return self.evaluate_risk(incident.hazard_telemetry)
