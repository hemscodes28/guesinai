# ==========================================================================
# BURNT SOIL -> RECOMMENDED SPECIES / CROP PREDICTION MODEL
# Project: Post-fire Amazon Reforestation Recommendation System
# Run each "# %% [CELL]" block as a separate cell in Google Colab
# ==========================================================================

# %% [CELL 1] Install/Import libraries
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import joblib

from sklearn.model_selection import train_test_split, GridSearchCV, StratifiedKFold
from sklearn.preprocessing import OneHotEncoder, LabelEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (classification_report, confusion_matrix,
                              ConfusionMatrixDisplay, accuracy_score, f1_score)

RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

# %% [CELL 2] Upload / Load dataset
# In Colab: use the file upload widget, then read the CSV
from google.colab import files
uploaded = files.upload()  # choose amazon_reforestation_synthetic_dataset.csv

df = pd.read_csv("amazon_reforestation_synthetic_dataset.csv")
print("Shape:", df.shape)
df.head()

# %% [CELL 3] Quick EDA
print(df.info())
print("\nMissing values:\n", df.isnull().sum())
print("\nTarget class distribution:\n", df["recommended_species"].value_counts())

plt.figure(figsize=(7, 4))
sns.countplot(data=df, y="recommended_species",
              order=df["recommended_species"].value_counts().index)
plt.title("Recommended Species Distribution (class imbalance check)")
plt.tight_layout()
plt.show()

# Correlation heatmap of numeric features
plt.figure(figsize=(12, 9))
numeric_cols = df.select_dtypes(include=[np.number]).columns
sns.heatmap(df[numeric_cols].corr(), cmap="coolwarm", center=0, annot=False)
plt.title("Correlation Heatmap - Numeric Features")
plt.tight_layout()
plt.show()

# %% [CELL 4] Data leakage check & cleanup
# IMPORTANT: 'recommended_reforestation_method' is a perfect 1-to-1 duplicate
# of 'recommended_species' in this dataset (verified: each species maps to
# exactly one method with zero overlap). If we leave it in, the model will
# just learn that mapping instead of learning from real soil/climate signals.
# We MUST drop it to avoid leakage.
leak_check = pd.crosstab(df["recommended_species"], df["recommended_reforestation_method"])
print(leak_check)

df_model = df.drop(columns=["recommended_reforestation_method"])

# %% [CELL 5] Define features and target
TARGET = "recommended_species"

categorical_features = ["soil_type", "drainage"]
numeric_features = [c for c in df_model.columns
                     if c not in categorical_features + [TARGET]]

X = df_model[numeric_features + categorical_features]
y = df_model[TARGET]

print("Numeric features:", numeric_features)
print("Categorical features:", categorical_features)

# Encode target labels (Brazil Nut, Rubber Tree, etc. -> integers)
label_encoder = LabelEncoder()
y_encoded = label_encoder.fit_transform(y)
print("\nClasses:", list(label_encoder.classes_))

# %% [CELL 6] Train/test split (stratified because of class imbalance)
X_train, X_test, y_train, y_test = train_test_split(
    X, y_encoded, test_size=0.2, random_state=RANDOM_STATE, stratify=y_encoded
)
print("Train size:", X_train.shape, "Test size:", X_test.shape)

# %% [CELL 7] Preprocessing pipeline
preprocessor = ColumnTransformer(
    transformers=[
        ("num", StandardScaler(), numeric_features),
        ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
    ]
)

# %% [CELL 8] Model pipeline - Random Forest
# class_weight='balanced' compensates for Mahogany (57 samples) vs
# Brazil Nut (6346 samples) style imbalance without needing to
# oversample/undersample manually.
rf_pipeline = Pipeline(steps=[
    ("preprocess", preprocessor),
    ("classifier", RandomForestClassifier(
        n_estimators=300,
        max_depth=None,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1
    ))
])

rf_pipeline.fit(X_train, y_train)

# %% [CELL 9] Evaluate on test set
y_pred = rf_pipeline.predict(X_test)

print("Accuracy:", accuracy_score(y_test, y_pred))
print("Macro F1 (fairer with imbalance):", f1_score(y_test, y_pred, average="macro"))
print("\nClassification Report:\n")
print(classification_report(y_test, y_pred, target_names=label_encoder.classes_))

cm = confusion_matrix(y_test, y_pred)
disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=label_encoder.classes_)
fig, ax = plt.subplots(figsize=(8, 8))
disp.plot(ax=ax, cmap="Blues", xticks_rotation=45)
plt.title("Confusion Matrix - Species Recommendation")
plt.tight_layout()
plt.show()

# %% [CELL 10] (Optional) Hyperparameter tuning with GridSearchCV
# Uncomment to run a small grid search - takes a few minutes on Colab CPU
"""
param_grid = {
    "classifier__n_estimators": [200, 400],
    "classifier__max_depth": [None, 15, 25],
    "classifier__min_samples_split": [2, 5],
}

grid = GridSearchCV(
    rf_pipeline, param_grid, cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE),
    scoring="f1_macro", n_jobs=-1, verbose=1
)
grid.fit(X_train, y_train)
print("Best params:", grid.best_params_)
print("Best CV F1 macro:", grid.best_score_)

rf_pipeline = grid.best_estimator_
"""

# %% [CELL 11] Feature importance
ohe_columns = rf_pipeline.named_steps["preprocess"].named_transformers_["cat"] \
    .get_feature_names_out(categorical_features)
all_feature_names = numeric_features + list(ohe_columns)

importances = rf_pipeline.named_steps["classifier"].feature_importances_
feat_imp = pd.Series(importances, index=all_feature_names).sort_values(ascending=False)

plt.figure(figsize=(8, 8))
feat_imp.head(15).plot(kind="barh")
plt.gca().invert_yaxis()
plt.title("Top 15 Feature Importances")
plt.xlabel("Importance")
plt.tight_layout()
plt.show()

print(feat_imp.head(15))

# %% [CELL 12] Save the trained model + label encoder for use in your project
joblib.dump(rf_pipeline, "burnt_soil_species_model.pkl")
joblib.dump(label_encoder, "species_label_encoder.pkl")

# In Colab, download the files to use elsewhere in your project:
files.download("burnt_soil_species_model.pkl")
files.download("species_label_encoder.pkl")

# %% [CELL 13] Inference function - predict species for a NEW burnt site
def recommend_species(sample_dict, model=rf_pipeline, encoder=label_encoder):
    """
    sample_dict: a dictionary with the same feature keys used in training
    (excluding the target and the leaked 'recommended_reforestation_method' column).

    Example:
    sample_dict = {
        "latitude": -1.5, "longitude": -62.3, "elevation_m": 150.0,
        "temperature_C": 29.5, "humidity_percent": 78.0, "rainfall_mm_day": 20.0,
        "windspeed_mps": 4.5, "soil_pH": 5.8, "soil_moisture_percent": 60.0,
        "organic_carbon_percent": 4.5, "nitrogen_mgkg": 1000, "phosphorus_mgkg": 20,
        "potassium_mgkg": 150, "bulk_density_gcm3": 1.2, "ndvi": 0.4,
        "canopy_cover_percent": 30.0, "burn_severity": 0.55, "fire_frequency_5yr": 1,
        "deforestation_percent": 35.0, "native_species_suitability": 70.0,
        "carbon_sequestration_tCO2_ha": 150.0,
        "soil_type": "Oxisol", "drainage": "Moderate"
    }
    """
    sample_df = pd.DataFrame([sample_dict])[numeric_features + categorical_features]
    pred_encoded = model.predict(sample_df)[0]
    pred_proba = model.predict_proba(sample_df)[0]
    pred_species = encoder.inverse_transform([pred_encoded])[0]

    proba_dict = dict(zip(encoder.classes_, pred_proba))
    proba_dict = dict(sorted(proba_dict.items(), key=lambda x: x[1], reverse=True))

    return pred_species, proba_dict


# Example usage:
example_site = {
    "latitude": -1.5, "longitude": -62.3, "elevation_m": 150.0,
    "temperature_C": 29.5, "humidity_percent": 78.0, "rainfall_mm_day": 20.0,
    "windspeed_mps": 4.5, "soil_pH": 5.8, "soil_moisture_percent": 60.0,
    "organic_carbon_percent": 4.5, "nitrogen_mgkg": 1000, "phosphorus_mgkg": 20,
    "potassium_mgkg": 150, "bulk_density_gcm3": 1.2, "ndvi": 0.4,
    "canopy_cover_percent": 30.0, "burn_severity": 0.55, "fire_frequency_5yr": 1,
    "deforestation_percent": 35.0, "native_species_suitability": 70.0,
    "carbon_sequestration_tCO2_ha": 150.0,
    "soil_type": "Oxisol", "drainage": "Moderate"
}

species, probabilities = recommend_species(example_site)
print("Recommended species:", species)
print("Class probabilities:", probabilities)

# %% [CELL 14] (Later, in a separate script/session) Load saved model for reuse
"""
import joblib
model = joblib.load("burnt_soil_species_model.pkl")
encoder = joblib.load("species_label_encoder.pkl")
# then call recommend_species(sample_dict, model, encoder)
"""
