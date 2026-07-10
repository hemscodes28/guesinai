"""
ml_fire_model.py — Adaptive ML Fire Spread Model
-------------------------------------------------
Replaces the hardcoded physics formula in simulation.py with a trained
GradientBoostingRegressor that self-improves with every simulation run.

Features used for prediction:
    fuel_load, risk_score, soil_dryness, wind_alignment,
    wind_speed, elev_diff_norm, rain_effect

Bootstrap: trains on 5000 synthetic samples generated via the existing
physics formula so it works out-of-the-box with no external dataset.
"""

import math
import random
import logging
from typing import Dict, List

logger = logging.getLogger("guesin_backend")

# ── Optional sklearn dependency ──────────────────────────────────────────────
try:
    from sklearn.ensemble import GradientBoostingRegressor
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning(
        "scikit-learn not found → ML fire spread model disabled. "
        "Run: pip install scikit-learn numpy"
    )


class FireSpreadMLModel:
    """
    Wraps a GradientBoostingRegressor that predicts fire-catching probability.
    Falls back transparently to the physics formula if sklearn is unavailable.
    """

    FEATURE_NAMES = [
        "fuel_load",
        "risk_score",
        "soil_dryness",
        "wind_alignment",
        "wind_speed",
        "elev_diff_norm",   # elev_diff / 100.0
        "rain_effect",      # max(0.05, 1 - rainfall / 15.0)
    ]

    def __init__(self):
        self.model = None
        self.is_trained: bool = False
        self.training_samples: int = 0
        self.last_retrain_step: int = 0
        self._pending_samples: List[Dict] = []   # buffer for online learning

        if SKLEARN_AVAILABLE:
            self.model = GradientBoostingRegressor(
                n_estimators=120,
                learning_rate=0.08,
                max_depth=4,
                subsample=0.85,
                random_state=42,
            )
            self._bootstrap_train(n_samples=6000)

    # ── Public API ────────────────────────────────────────────────────────────

    def predict(
        self,
        fuel: float,
        risk: float,
        soil_dryness: float,
        wind_alignment: float,
        wind_spd: float,
        elev_diff: float,
        rainfall: float,
    ) -> float:
        """
        Returns predicted fire-catching probability in [0.0, 0.98].
        Automatically falls back to the physics formula when ML is unavailable.
        """
        if not SKLEARN_AVAILABLE or not self.is_trained:
            return self._physics(fuel, risk, soil_dryness, wind_alignment, wind_spd, elev_diff, rainfall)

        try:
            rain_effect = max(0.05, 1.0 - rainfall / 15.0)
            X = np.array([[
                fuel, risk, soil_dryness, wind_alignment,
                wind_spd, elev_diff / 100.0, rain_effect
            ]])
            pred = float(self.model.predict(X)[0])
            return min(0.98, max(0.0, pred))
        except Exception as exc:
            logger.debug(f"ML predict fallback ({exc})")
            return self._physics(fuel, risk, soil_dryness, wind_alignment, wind_spd, elev_diff, rainfall)

    def record_sample(
        self,
        fuel: float,
        risk: float,
        soil_dryness: float,
        wind_alignment: float,
        wind_spd: float,
        elev_diff: float,
        rainfall: float,
        caught_fire: bool,
    ):
        """
        Records an actual ignition outcome for online learning.
        Buffer is flushed when retrain() is called.
        """
        self._pending_samples.append({
            "fuel": fuel,
            "risk": risk,
            "soil_dry": soil_dryness,
            "wind_align": wind_alignment,
            "wind_spd": wind_spd,
            "elev_diff": elev_diff,
            "rain_effect": max(0.05, 1.0 - rainfall / 15.0),
            "p_catch": 1.0 if caught_fire else 0.0,
        })

    def retrain(self, extra_samples: List[Dict] = None):
        """
        Retrains the model using buffered + supplied samples.
        Requires at least 200 total samples to retrain.
        """
        if not SKLEARN_AVAILABLE:
            return

        all_samples = list(self._pending_samples)
        if extra_samples:
            all_samples.extend(extra_samples)

        if len(all_samples) < 200:
            logger.debug(f"ML retrain skipped — only {len(all_samples)} samples available.")
            return

        X, y = [], []
        for s in all_samples:
            X.append([s["fuel"], s["risk"], s["soil_dry"],
                      s["wind_align"], s["wind_spd"],
                      s["elev_diff"] / 100.0, s["rain_effect"]])
            y.append(s["p_catch"])

        try:
            self.model.fit(np.array(X), np.array(y))
            self.training_samples += len(all_samples)
            self._pending_samples.clear()
            logger.info(f"ML model retrained on {len(all_samples)} real samples. Total: {self.training_samples}")
        except Exception as exc:
            logger.error(f"ML retrain failed: {exc}")

    def get_status(self) -> Dict:
        return {
            "sklearn_available": SKLEARN_AVAILABLE,
            "is_trained": self.is_trained,
            "training_samples": self.training_samples,
            "pending_samples": len(self._pending_samples),
            "model_type": "GradientBoostingRegressor" if SKLEARN_AVAILABLE else "PhysicsFormula (fallback)",
            "feature_names": self.FEATURE_NAMES,
            "last_retrain_step": self.last_retrain_step,
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _physics(fuel: float, risk: float, soil_dryness: float,
                 wind_alignment: float, wind_spd: float,
                 elev_diff: float, rainfall: float) -> float:
        """Exact replica of the original physics formula (used as ground truth for bootstrapping)."""
        wind_effect = math.exp(wind_alignment * (wind_spd / 15.0))
        if elev_diff > 0:
            elev_effect = min(2.5, 1.0 + (elev_diff / 30.0))
        else:
            elev_effect = max(0.15, 1.0 + (elev_diff / 80.0))
        rain_effect = max(0.05, 1.0 - (rainfall / 15.0))
        p = 0.28 * fuel * risk * soil_dryness * wind_effect * elev_effect * rain_effect
        return min(0.98, max(0.0, p))

    def _bootstrap_train(self, n_samples: int = 6000):
        """
        Generates synthetic training data using the physics formula,
        then trains the model. This ensures the ML model starts with
        physics-equivalent behaviour and improves from there.
        """
        if not SKLEARN_AVAILABLE:
            return

        X, y = [], []
        for _ in range(n_samples):
            fuel         = random.uniform(0.0, 1.0)
            risk         = random.uniform(0.0, 1.0)
            soil_dry     = random.uniform(0.0, 1.0)
            wind_align   = random.uniform(-1.0, 1.0)
            wind_spd     = random.uniform(0.0, 40.0)
            elev_diff    = random.uniform(-120.0, 120.0)
            rainfall     = random.uniform(0.0, 25.0)
            rain_effect  = max(0.05, 1.0 - rainfall / 15.0)

            p = self._physics(fuel, risk, soil_dry, wind_align, wind_spd, elev_diff, rainfall)

            X.append([fuel, risk, soil_dry, wind_align, wind_spd, elev_diff / 100.0, rain_effect])
            y.append(p)

        try:
            self.model.fit(np.array(X), np.array(y))
            self.is_trained = True
            self.training_samples = n_samples
            logger.info(f"ML fire model bootstrapped with {n_samples} synthetic samples. Ready.")
        except Exception as exc:
            logger.error(f"Bootstrap training failed: {exc}")
            self.is_trained = False


# ── Singleton (imported by simulation.py and main.py) ────────────────────────
ml_model = FireSpreadMLModel()
