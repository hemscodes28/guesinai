import asyncio
import json
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone
from pathlib import Path
from models import IncidentPayload


def load_env_file(base_dir=None):
    if base_dir is None:
        base_path = Path(__file__).resolve().parent
    else:
        base_path = Path(base_dir).resolve()

    current = base_path if base_path.is_dir() else base_path.parent
    directories = []
    seen = set()

    while current not in seen:
        seen.add(current)
        directories.append(current)
        if current.parent == current:
            break
        current = current.parent

    for directory in reversed(directories):
        for env_path in [directory / ".env", directory / ".env.local"]:
            if not env_path.exists():
                continue
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()


class DispatchEngine:
    def __init__(self):
        self.subscribers = set() # WebSocket subscribers
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from = os.getenv("SMTP_FROM", self.smtp_user)
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        self.use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
        self.department_emails = [
            {"id": "fire", "name": "Fire Dept", "email": os.getenv("FIRE_DEPT_EMAIL", "sarveshbala27@gmail.com")},
            {"id": "ambulance", "name": "Ambulance", "email": os.getenv("AMBULANCE_EMAIL", "barathrithish7@gmail.com")},
            {"id": "rescue", "name": "Rescue", "email": os.getenv("RESCUE_EMAIL", "balasarveshk@gmail.com")}
        ]

    async def add_subscriber(self, websocket):
        self.subscribers.add(websocket)

    async def remove_subscriber(self, websocket):
        self.subscribers.remove(websocket)

    async def broadcast_raw(self, data: dict):
        if self.subscribers:
            message = json.dumps(data)
            for ws in self.subscribers:
                try:
                    await ws.send_text(message)
                except:
                    pass

    async def dispatch(self, payload: IncidentPayload):
        """
        Dispatches payload to multiple agencies simultaneously.
        """
        # First broadcast the incident itself
        await self.broadcast_raw({"type": "INCIDENT", "data": payload.model_dump(mode='json')})
        
        # Then kick off email sending in the background
        asyncio.create_task(self.dispatch_emails(payload))

    def send_email_sync(self, recipient: str, subject: str, body: str) -> bool:
        if not self.smtp_user or not self.smtp_password:
            return False

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.smtp_from
        message["To"] = recipient
        message.set_content(body)

        strategies = []
        if self.use_ssl or self.smtp_port == 465:
            strategies.append((True, self.smtp_host, self.smtp_port, False))
        strategies.extend([
            (False, self.smtp_host, self.smtp_port, self.use_tls),
            (True, self.smtp_host, 465, False),
            (False, self.smtp_host, 587, True),
            (False, self.smtp_host, 25, False),
        ])

        last_error = None
        for use_ssl, host, port, use_tls in strategies:
            try:
                if use_ssl:
                    with smtplib.SMTP_SSL(host, port) as server:
                        server.login(self.smtp_user, self.smtp_password)
                        server.send_message(message)
                else:
                    with smtplib.SMTP(host, port) as server:
                        server.ehlo()
                        if use_tls:
                            server.starttls()
                            server.ehlo()
                        server.login(self.smtp_user, self.smtp_password)
                        server.send_message(message)
                return True
            except Exception as exc:
                last_error = exc

        print(f"SMTP delivery failed for {recipient}: {last_error}")
        return False

    async def dispatch_emails(self, payload: IncidentPayload):
        for dept in self.department_emails:
            await self.broadcast_raw({
                "type": "EMAIL_STATUS",
                "dept_id": dept["id"],
                "status": "pending",
                "message": f"Sending to {dept['email']}..."
            })

            subject = f"Evacuation Alert: {payload.incident_id}"
            body = (
                f"Emergency Level: {payload.emergency_level}\n"
                f"Target Zone: {payload.target_zone.settlement_name}\n"
                f"Time to impact: {payload.hazard_telemetry.time_to_impact_mins} mins\n"
                f"Confidence: {payload.hazard_telemetry.confidence_coefficient}\n"
                f"Please initiate evacuation and route coordination."
                f"We recommend {dept['name']} to proceed to the target zone immediately."
            )

            success = self.send_email_sync(dept["email"], subject, body)

            if success:
                response_msg = "Awaiting Acknowledgement" if dept["id"] == "fire" else ("En Route" if dept["id"] == "ambulance" else "Team Mobilized")
                await self.broadcast_raw({
                    "type": "EMAIL_STATUS",
                    "dept_id": dept["id"],
                    "status": "success",
                    "message": response_msg,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            else:
                await self.broadcast_raw({
                    "type": "EMAIL_STATUS",
                    "dept_id": dept["id"],
                    "status": "failed",
                    "message": "Failed to send. Configure SMTP credentials.",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
