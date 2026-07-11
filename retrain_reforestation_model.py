"""
Retrain the reforestation model on the current sklearn version (1.8.0)
so the pickle loads without version mismatch errors.
"""
import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, LabelEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
import warnings
warnings.filterwarnings("ignore")

RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

print("Loading dataset...")
df = pd.read_csv("Reforestation/amazon_reforestation_synthetic_dataset.csv")
print("Shape:", df.shape)

# Drop data-leakage column
df_model = df.drop(columns=["recommended_reforestation_method"])

TARGET = "recommended_species"
categorical_features = ["soil_type", "drainage"]
numeric_features = [c for c in df_model.columns if c not in categorical_features + [TARGET]]

X = df_model[numeric_features + categorical_features]
y = df_model[TARGET]

print("Numeric features:", numeric_features)
print("Target classes:", y.unique().tolist())

label_encoder = LabelEncoder()
y_encoded = label_encoder.fit_transform(y)

X_train, X_test, y_train, y_test = train_test_split(
    X, y_encoded, test_size=0.2, random_state=RANDOM_STATE, stratify=y_encoded
)
print(f"Train: {X_train.shape} | Test: {X_test.shape}")

preprocessor = ColumnTransformer(
    transformers=[
        ("num", StandardScaler(), numeric_features),
        ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
    ]
)

rf_pipeline = Pipeline(steps=[
    ("preprocess", preprocessor),
    ("classifier", RandomForestClassifier(
        n_estimators=200,
        max_depth=None,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1
    ))
])

print("Training model on sklearn 1.8.0 ...")
rf_pipeline.fit(X_train, y_train)

y_pred = rf_pipeline.predict(X_test)
acc = accuracy_score(y_test, y_pred)
f1 = f1_score(y_test, y_pred, average="macro")
print(f"Accuracy: {acc:.4f} | Macro F1: {f1:.4f}")

# Save
joblib.dump(rf_pipeline, "Reforestation/burnt_soil_species_model_v2.pkl")
joblib.dump(label_encoder, "Reforestation/species_label_encoder_v2.pkl")
print("Model saved as burnt_soil_species_model_v2.pkl / species_label_encoder_v2.pkl")

# Quick inference test
sample = {
    'latitude': -1.5, 'longitude': -62.3, 'elevation_m': 150.0,
    'temperature_C': 29.5, 'humidity_percent': 78.0, 'rainfall_mm_day': 20.0,
    'windspeed_mps': 4.5, 'soil_pH': 5.8, 'soil_moisture_percent': 60.0,
    'organic_carbon_percent': 4.5, 'nitrogen_mgkg': 1000, 'phosphorus_mgkg': 20,
    'potassium_mgkg': 150, 'bulk_density_gcm3': 1.2, 'ndvi': 0.4,
    'canopy_cover_percent': 30.0, 'burn_severity': 0.55, 'fire_frequency_5yr': 1,
    'deforestation_percent': 35.0, 'native_species_suitability': 70.0,
    'carbon_sequestration_tCO2_ha': 150.0,
    'soil_type': 'Oxisol', 'drainage': 'Moderate'
}
df_s = pd.DataFrame([sample])[numeric_features + categorical_features]
pred = rf_pipeline.predict(df_s)[0]
proba = rf_pipeline.predict_proba(df_s)[0]
species = label_encoder.inverse_transform([pred])[0]
print(f"\nTest prediction: {species}")
print("Probabilities:", {c: round(float(p), 4) for c, p in sorted(zip(label_encoder.classes_, proba), key=lambda x: x[1], reverse=True)})
