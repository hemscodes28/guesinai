import datetime
import hashlib
import os
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///c:/Users/Hemkumar Ramesh/Desktop/Guesin/wildfire_twin.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ":" + key.hex()

def verify_password(password: str, hashed: str) -> bool:
    try:
        salt_hex, key_hex = hashed.split(":")
        salt = bytes.fromhex(salt_hex)
        key = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return new_key == key
    except Exception:
        return False

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

class WeatherLog(Base):
    __tablename__ = "weather_logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    temperature = Column(Float)
    humidity = Column(Float)
    wind_speed = Column(Float)
    wind_direction = Column(Float)
    rainfall = Column(Float)
    atmospheric_pressure = Column(Float)
    soil_moisture = Column(Float)
    vpd = Column(Float)
    solar_radiation = Column(Float)

class AlertLog(Base):
    __tablename__ = "alert_logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    row = Column(Integer)
    col = Column(Integer)
    alert_type = Column(String)  # "burning" or "critical_risk"
    message = Column(String)

class SimulationSnapshot(Base):
    __tablename__ = "simulation_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    step = Column(Integer)
    unburned_count = Column(Integer)
    burning_count = Column(Integer)
    burned_count = Column(Integer)
    active_fires = Column(String)  # JSON list of coordinates e.g. "[[24,15], [24,16]]"

class FireSpreadSample(Base):
    """Stores actual simulation spread outcomes for ML model retraining."""
    __tablename__ = "fire_spread_samples"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    step = Column(Integer)
    fuel = Column(Float)
    risk = Column(Float)
    soil_dry = Column(Float)
    wind_align = Column(Float)
    wind_spd = Column(Float)
    elev_diff = Column(Float)
    rain_effect = Column(Float)
    p_catch = Column(Float)   # 1.0 = caught fire, 0.0 = did not


class SituationReport(Base):
    """Caches AI-generated situation reports."""
    __tablename__ = "situation_reports"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    simulation_step = Column(Integer)
    report_text = Column(Text)
    model_used = Column(String, default="template")
    burning_count = Column(Integer)
    burned_count = Column(Integer)
    healthy_count = Column(Integer)


def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
