"""
Reforestation Module API Routes
Handles ML model inference for post-fire crop/species recommendation
"""
import joblib
import logging
import pandas as pd
import numpy as np
from pathlib import Path

logger = logging.getLogger("guesin_backend")

# ─── Feature Definitions (must match training) ──────────────────────────────
NUMERIC_FEATURES = [
    "latitude", "longitude", "elevation_m", "temperature_C", "humidity_percent",
    "rainfall_mm_day", "windspeed_mps", "soil_pH", "soil_moisture_percent",
    "organic_carbon_percent", "nitrogen_mgkg", "phosphorus_mgkg", "potassium_mgkg",
    "bulk_density_gcm3", "ndvi", "canopy_cover_percent", "burn_severity",
    "fire_frequency_5yr", "deforestation_percent", "native_species_suitability",
    "carbon_sequestration_tCO2_ha"
]
CATEGORICAL_FEATURES = ["soil_type", "drainage"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

SOIL_TYPES = ["Oxisol", "Inceptisol", "Histosol", "Ultisol", "Spodosol", "Entisol"]
DRAINAGE_TYPES = ["Moderate", "Poor", "Good"]

# ─── Species metadata for farmer-friendly output ─────────────────────────────
SPECIES_INFO = {
    "Brazil Nut": {
        "local_name": "Brazil Nut (Bertholletia excelsa)",
        "category": "Timber & Nut Tree",
        "growth_time": "8-10 years to first harvest",
        "economic_value": "Very High",
        "carbon_seq": "Excellent CO₂ absorber",
        "farmer_tip": "Best suited for areas with moderate soil moisture. Provides high-value nuts for export markets.",
        "icon": "🌰",
        "color": "#854d0e",
        "conditions": "Thrives in deep, well-drained Oxisol/Ultisol soils with good rainfall.",
        "harvest_season": "Jan – Mar",
        "market_price_range": "₹450–₹900/kg"
    },
    "Rubber Tree": {
        "local_name": "Rubber Tree (Hevea brasiliensis)",
        "category": "Industrial Cash Crop",
        "growth_time": "5-7 years to tapping maturity",
        "economic_value": "High",
        "carbon_seq": "Good CO₂ absorber",
        "farmer_tip": "Ideal for warm, humid zones with well-drained loamy soils. Provides steady latex income for decades.",
        "icon": "🌳",
        "color": "#166534",
        "conditions": "Best in humid tropical climate with 1500–2500mm rainfall. Avoid waterlogged fields.",
        "harvest_season": "Year-round tapping",
        "market_price_range": "₹180–₹250/kg (latex)"
    },
    "Açaí Palm": {
        "local_name": "Açaí Palm (Euterpe oleracea)",
        "category": "Fruit Palm",
        "growth_time": "3-5 years to first fruit cluster",
        "economic_value": "High",
        "carbon_seq": "Moderate CO₂ absorber",
        "farmer_tip": "Excellent for flood-prone or riparian areas. Açaí berries are a global superfood with premium export value.",
        "icon": "🌴",
        "color": "#7c3aed",
        "conditions": "Tolerates seasonally flooded lands and poor drainage. Perfect for riverbanks.",
        "harvest_season": "Jul – Dec",
        "market_price_range": "₹800–₹1500/kg"
    },
    "Andiroba": {
        "local_name": "Andiroba (Carapa guianensis)",
        "category": "Medicinal & Timber Tree",
        "growth_time": "6-8 years to seed production",
        "economic_value": "Medium-High",
        "carbon_seq": "Very good CO₂ absorber",
        "farmer_tip": "Produces valuable medicinal oil from seeds. Native species with strong biodiversity recovery potential.",
        "icon": "🌿",
        "color": "#0d9488",
        "conditions": "Prefers moist soils near watercourses. Very tolerant of burn-damaged soils.",
        "harvest_season": "Mar – Jul",
        "market_price_range": "₹600–₹1200/kg (oil)"
    },
    "Mahogany": {
        "local_name": "Mahogany (Swietenia macrophylla)",
        "category": "Premium Hardwood Timber",
        "growth_time": "15-20 years to commercial harvest",
        "economic_value": "Very High (Long-term)",
        "carbon_seq": "Outstanding CO₂ sequestration",
        "farmer_tip": "Long investment but extremely high timber value. Best planted in government reforestation programs with community support.",
        "icon": "🪵",
        "color": "#dc2626",
        "conditions": "Deep, well-drained soils. Requires forest shade in early years. Semi-deciduous tolerance.",
        "harvest_season": "Commercial timber (no seasonal harvest)",
        "market_price_range": "₹15,000–₹30,000/cubic ft"
    }
}


# ─── Model Loader ─────────────────────────────────────────────────────────────
_model = None
_encoder = None

def _load_model():
    global _model, _encoder
    if _model is None:
        # Prefer the v2 model retrained on the current sklearn version
        for model_name, enc_name in [
            ("burnt_soil_species_model_v2.pkl", "species_label_encoder_v2.pkl"),
            ("burnt_soil_species_model.pkl", "species_label_encoder.pkl"),
        ]:
            model_path = Path("Reforestation") / model_name
            encoder_path = Path("Reforestation") / enc_name
            if model_path.exists() and encoder_path.exists():
                _model = joblib.load(model_path)
                _encoder = joblib.load(encoder_path)
                logger.info(f"Reforestation model loaded: {model_name}")
                return _model, _encoder
        raise FileNotFoundError("No reforestation model file found in Reforestation/")
    return _model, _encoder


def predict_species_for_cell(cell_data: dict) -> dict:
    """
    Run inference for a single burned cell.
    cell_data: dict with simulation cell properties.
    Returns dict with recommended species and probabilities.
    """
    model, encoder = _load_model()

    # Map simulation fields to model features
    sample = {
        "latitude": cell_data.get("latitude", -2.145),
        "longitude": cell_data.get("longitude", -59.000),
        "elevation_m": cell_data.get("elevation", 100.0),
        "temperature_C": cell_data.get("temperature", 28.0),
        "humidity_percent": cell_data.get("humidity", 75.0),
        "rainfall_mm_day": max(0.0, cell_data.get("rainfall", 5.0)),
        "windspeed_mps": cell_data.get("wind_speed", 3.5),
        # Soil parameters derived from simulation fuel/risk signals
        "soil_pH": 5.5 + cell_data.get("fuel_load", 0.5) * 0.8,
        "soil_moisture_percent": cell_data.get("soil_moisture", 0.4) * 100.0,
        "organic_carbon_percent": 3.0 + cell_data.get("fuel_load", 0.5) * 3.0,
        "nitrogen_mgkg": 800 + cell_data.get("vegetation_density", 0.6) * 400,
        "phosphorus_mgkg": 15 + cell_data.get("fuel_load", 0.5) * 20,
        "potassium_mgkg": 100 + cell_data.get("vegetation_density", 0.6) * 100,
        "bulk_density_gcm3": 1.4 - cell_data.get("vegetation_density", 0.6) * 0.3,
        "ndvi": max(0.0, 0.7 - cell_data.get("risk_score", 0.3) * 0.5),
        "canopy_cover_percent": max(0.0, 60.0 - cell_data.get("risk_score", 0.3) * 50.0),
        "burn_severity": min(1.0, cell_data.get("risk_score", 0.5) * 1.2),
        "fire_frequency_5yr": 1 + int(cell_data.get("burn_duration", 1) > 5),
        "deforestation_percent": min(100.0, cell_data.get("risk_score", 0.5) * 80.0),
        "native_species_suitability": max(0.0, 80.0 - cell_data.get("risk_score", 0.3) * 40.0),
        "carbon_sequestration_tCO2_ha": 120.0 + cell_data.get("vegetation_density", 0.6) * 80.0,
        "soil_type": _infer_soil_type(cell_data),
        "drainage": _infer_drainage(cell_data),
    }

    df = pd.DataFrame([sample])[ALL_FEATURES]
    pred_encoded = model.predict(df)[0]
    proba = model.predict_proba(df)[0]
    species_name = encoder.inverse_transform([pred_encoded])[0]
    proba_dict = {cls: round(float(p), 4) for cls, p in zip(encoder.classes_, proba)}
    top3 = sorted(proba_dict.items(), key=lambda x: x[1], reverse=True)[:3]

    info = SPECIES_INFO.get(species_name, {})

    return {
        "recommended_species": species_name,
        "confidence": round(float(max(proba_dict.values())), 4),
        "top3_predictions": [{"species": s, "probability": p} for s, p in top3],
        "all_probabilities": proba_dict,
        "species_info": info,
        "input_features": {k: v for k, v in sample.items() if k not in CATEGORICAL_FEATURES},
        "soil_type": sample["soil_type"],
        "drainage": sample["drainage"]
    }


def _infer_soil_type(cell_data: dict) -> str:
    """Infer soil type from simulation characteristics."""
    elevation = cell_data.get("elevation", 100.0)
    veg = cell_data.get("vegetation_density", 0.6)
    soil_m = cell_data.get("soil_moisture", 0.4)

    if soil_m > 0.7:
        return "Histosol"       # Peat-like, very wet
    elif elevation > 200:
        return "Ultisol"        # Weathered, higher ground
    elif veg > 0.75:
        return "Oxisol"         # Rich in iron/aluminum, dense canopy
    elif soil_m < 0.2:
        return "Entisol"        # Sandy, dry
    elif veg < 0.35:
        return "Spodosol"       # Sandy, low veg
    else:
        return "Inceptisol"     # Young, moderately developed


def _infer_drainage(cell_data: dict) -> str:
    """Infer drainage class from elevation and soil moisture."""
    soil_m = cell_data.get("soil_moisture", 0.4)
    elevation = cell_data.get("elevation", 100.0)

    if soil_m > 0.65 or elevation < 90:
        return "Poor"
    elif soil_m < 0.3 and elevation > 150:
        return "Good"
    else:
        return "Moderate"


def get_batch_recommendations(burned_cells: list) -> dict:
    """
    Run batch inference over all burned cells from simulation data.
    Returns per-cell recommendations, deforestation map, and summary stats.
    """
    model, encoder = _load_model()
    results = []
    species_counts = {}
    total_burned = len(burned_cells)

    if total_burned == 0:
        return {"status": "no_burned_cells", "recommendations": [], "summary": {}}

    for cell in burned_cells:
        try:
            rec = predict_species_for_cell(cell)
            results.append({
                "row": cell["row"],
                "col": cell["col"],
                "latitude": cell["latitude"],
                "longitude": cell["longitude"],
                "recommended_species": rec["recommended_species"],
                "confidence": rec["confidence"],
                "top3_predictions": rec["top3_predictions"],
                "species_info": rec["species_info"],
                "soil_type": rec["soil_type"],
                "drainage": rec["drainage"],
                "burn_severity_estimated": round(min(1.0, cell.get("risk_score", 0.5) * 1.2), 3),
                "deforestation_percent": round(min(100.0, cell.get("risk_score", 0.5) * 80.0), 1)
            })
            sp = rec["recommended_species"]
            species_counts[sp] = species_counts.get(sp, 0) + 1
        except Exception as e:
            logger.error(f"Error predicting for cell ({cell.get('row')},{cell.get('col')}): {e}")

    dominant_species = max(species_counts, key=species_counts.get) if species_counts else "Unknown"
    total_area_ha = total_burned * 0.09  # Each 30m x 30m cell = 0.09 ha

    summary = {
        "total_burned_cells": total_burned,
        "total_deforested_area_ha": round(total_area_ha, 2),
        "species_distribution": species_counts,
        "dominant_recommended_species": dominant_species,
        "dominant_species_info": SPECIES_INFO.get(dominant_species, {}),
        "recovery_timeline_years": _estimate_recovery_years(dominant_species),
        "carbon_recovery_potential_tCO2": round(total_area_ha * 12.5, 1)
    }

    return {
        "status": "success",
        "total_burned_cells": total_burned,
        "recommendations": results,
        "summary": summary,
        "species_info_catalog": SPECIES_INFO
    }


def _estimate_recovery_years(species_name: str) -> str:
    timelines = {
        "Brazil Nut": "8-10 years",
        "Rubber Tree": "5-7 years",
        "Açaí Palm": "3-5 years",
        "Andiroba": "6-8 years",
        "Mahogany": "15-20 years"
    }
    return timelines.get(species_name, "5-10 years")
