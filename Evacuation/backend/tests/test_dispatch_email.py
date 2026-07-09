import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dispatch_engine import DispatchEngine, load_env_file
from models import IncidentPayload, TargetZone, HazardTelemetry


class DispatchEmailTests(unittest.TestCase):
    def test_load_env_file_prefers_real_credentials(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            child = root / "backend"
            child.mkdir()
            (child / ".env").write_text("SMTP_USER=your_email@gmail.com\nSMTP_PASSWORD=your_app_password\n", encoding="utf-8")
            (root / ".env").write_text("SMTP_USER=real.user@gmail.com\nSMTP_PASSWORD=real-app-password\n", encoding="utf-8")

            os.environ.pop("SMTP_USER", None)
            os.environ.pop("SMTP_PASSWORD", None)
            load_env_file(base_dir=child)

            self.assertEqual(os.environ["SMTP_USER"], "real.user@gmail.com")
            self.assertEqual(os.environ["SMTP_PASSWORD"], "real-app-password")

    def test_send_email_uses_smtp_when_configured(self):
        engine = DispatchEngine()
        engine.smtp_host = "localhost"
        engine.smtp_port = 2525
        engine.smtp_user = "user"
        engine.smtp_password = "pass"
        engine.smtp_from = "evac@example.com"

        payload = IncidentPayload(
            incident_id="WF-001",
            timestamp="2026-07-10T00:00:00Z",
            emergency_level="CRITICAL",
            target_zone=TargetZone(
                settlement_name="Oakridge",
                centroid=(34.0522, -118.2437),
                estimated_population=1000,
            ),
            hazard_telemetry=HazardTelemetry(
                rate_of_spread_kmh=4.5,
                primary_vector_bearing=180.0,
                time_to_impact_mins=30,
                confidence_coefficient=0.95,
            ),
        )

        with patch("dispatch_engine.smtplib.SMTP") as mock_smtp:
            mock_client = mock_smtp.return_value.__enter__.return_value
            result = engine.send_email_sync(
                "recipient@example.com",
                "Test alert",
                "Hello from test",
            )

        self.assertTrue(result)
        mock_client.login.assert_called_once_with("user", "pass")
        mock_client.send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
