"""
ml_model.py — WellBot Machine Learning Module
==============================================
This file:
  1. Loads the wellness dataset (wellness_data.csv)
  2. Trains three ML models to predict: mood, stress_level, productivity_score
  3. Exposes a single predict() function for Flask to call

WHY THESE MODELS?
  - RandomForestClassifier  → great for classification (mood, stress labels)
  - RandomForestRegressor   → great for numeric prediction (productivity score)
  - scikit-learn handles all the math for us — no manual formulas needed!
"""

import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, r2_score
import warnings
warnings.filterwarnings('ignore')

# ── STEP 1: LOAD & PREPARE DATA ────────────────────────────────────────────────

def load_data():
    """Load the CSV dataset and return a cleaned DataFrame."""
    csv_path = os.path.join(os.path.dirname(__file__), 'wellness_data.csv')
    df = pd.read_csv(csv_path)
    return df


def prepare_features(df):
    """
    Select the columns the models will use as input features.
    These are the things a user enters or that sensors can measure.
    """
    feature_cols = [
        'sleep_hours',
        'work_hours',
        'exercise_minutes',
        'screen_time',
        'caffeine_intake',
        'breaks_taken',
        'steps',
        'water_intake'
    ]
    return df[feature_cols]


# ── STEP 2: TRAIN MODELS ───────────────────────────────────────────────────────

class WellnessModels:
    """
    Container for all three trained models + encoders.
    Once trained, call .predict(input_dict) to get predictions.
    """

    def __init__(self):
        self.mood_model = None
        self.stress_model = None
        self.productivity_model = None
        self.mood_encoder = LabelEncoder()
        self.stress_encoder = LabelEncoder()
        self.is_trained = False
        self.feature_cols = [
            'sleep_hours', 'work_hours', 'exercise_minutes',
            'screen_time', 'caffeine_intake', 'breaks_taken',
            'steps', 'water_intake'
        ]

    def train(self):
        """Load data, train all three models, print accuracy stats."""
        df = load_data()
        X = prepare_features(df)

        # ── Mood model (classification: happy / neutral / sad) ──
        y_mood = self.mood_encoder.fit_transform(df['mood'])
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_mood, test_size=0.2, random_state=42
        )
        self.mood_model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.mood_model.fit(X_train, y_train)
        mood_acc = accuracy_score(y_test, self.mood_model.predict(X_test))
        print(f"[ML] Mood model accuracy: {mood_acc*100:.1f}%")

        # ── Stress model (classification: low / medium / high) ──
        y_stress = self.stress_encoder.fit_transform(df['stress_level'])
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_stress, test_size=0.2, random_state=42
        )
        self.stress_model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.stress_model.fit(X_train, y_train)
        stress_acc = accuracy_score(y_test, self.stress_model.predict(X_test))
        print(f"[ML] Stress model accuracy: {stress_acc*100:.1f}%")

        # ── Productivity model (regression: 0–100 score) ──
        y_prod = df['productivity_score']
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_prod, test_size=0.2, random_state=42
        )
        self.productivity_model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.productivity_model.fit(X_train, y_train)
        prod_r2 = r2_score(y_test, self.productivity_model.predict(X_test))
        print(f"[ML] Productivity model R² score: {prod_r2:.3f}")

        self.is_trained = True
        print("[ML] All models trained successfully!")

    def predict(self, input_data: dict) -> dict:
        """
        Make predictions from user input.

        Args:
            input_data: dict with keys matching feature_cols
                        e.g. {'sleep_hours': 7, 'work_hours': 8, ...}

        Returns:
            dict with mood, stress_level, productivity_score + confidence info
        """
        if not self.is_trained:
            self.train()

        # Build a single-row DataFrame in the right column order
        row = {col: float(input_data.get(col, 0)) for col in self.feature_cols}
        X_input = pd.DataFrame([row])

        # Mood prediction + probability
        mood_encoded = self.mood_model.predict(X_input)[0]
        mood_label = self.mood_encoder.inverse_transform([mood_encoded])[0]
        mood_probs = self.mood_model.predict_proba(X_input)[0]
        mood_confidence = int(max(mood_probs) * 100)

        # Stress prediction + probability
        stress_encoded = self.stress_model.predict(X_input)[0]
        stress_label = self.stress_encoder.inverse_transform([stress_encoded])[0]
        stress_probs = self.stress_model.predict_proba(X_input)[0]
        stress_confidence = int(max(stress_probs) * 100)

        # Productivity score (clamp between 0 and 100)
        prod_score = self.productivity_model.predict(X_input)[0]
        prod_score = int(max(0, min(100, round(prod_score))))

        # Build human-friendly tips based on predictions
        tips = _generate_tips(mood_label, stress_label, prod_score, row)

        # Emoji maps
        mood_emoji = {'happy': '😊', 'neutral': '😐', 'sad': '😔'}.get(mood_label, '🙂')
        stress_emoji = {'low': '✅', 'medium': '⚠️', 'high': '🔴'}.get(stress_label, '⚠️')

        return {
            'mood': mood_label.capitalize(),
            'mood_emoji': mood_emoji,
            'mood_confidence': mood_confidence,
            'stress_level': stress_label.capitalize(),
            'stress_emoji': stress_emoji,
            'stress_confidence': stress_confidence,
            'productivity_score': prod_score,
            'tips': tips
        }


def _generate_tips(mood, stress, productivity, row):
    """Return personalized wellness tips based on prediction results."""
    tips = []

    if row['sleep_hours'] < 6:
        tips.append("🛌 Aim for 7–9 hours of sleep to boost mood and focus.")
    if row['exercise_minutes'] < 20:
        tips.append("🏃 Even a 20-minute walk can significantly reduce stress.")
    if row['water_intake'] < 2:
        tips.append("💧 Stay hydrated! Aim for at least 2 litres of water a day.")
    if row['screen_time'] > 6:
        tips.append("📱 Try the 20-20-20 rule: every 20 min, look 20 ft away for 20 sec.")
    if row['breaks_taken'] < 3:
        tips.append("☕ Take regular short breaks — they boost productivity.")
    if row['caffeine_intake'] > 3:
        tips.append("☕ High caffeine can increase anxiety. Try herbal tea instead.")
    if row['steps'] < 5000:
        tips.append("👟 Try to hit 7,000–10,000 steps a day for cardiovascular health.")

    if stress == 'high':
        tips.append("🧘 Try a 5-minute breathing exercise: inhale 4s, hold 4s, exhale 6s.")
    if mood == 'sad':
        tips.append("🌤️ Step outside for sunlight — natural light lifts mood naturally.")
    if productivity < 50:
        tips.append("📋 Break tasks into small chunks and celebrate each completion.")

    # Always return at least one tip
    if not tips:
        tips.append("🌟 Great wellness habits! Keep up the excellent work.")

    return tips[:4]  # Return max 4 tips to keep UI clean


# ── STEP 3: SINGLETON INSTANCE ─────────────────────────────────────────────────
# Flask will import this object and call .predict() — training happens once on startup

_models = WellnessModels()


def get_models() -> WellnessModels:
    """Return the shared trained model instance (trains once if needed)."""
    if not _models.is_trained:
        _models.train()
    return _models


def predict_wellness(input_data: dict) -> dict:
    """
    Convenience function for Flask routes.
    Usage: result = predict_wellness({'sleep_hours': 7, 'work_hours': 8, ...})
    """
    return get_models().predict(input_data)


# ── QUICK TEST (run this file directly to test) ────────────────────────────────
if __name__ == '__main__':
    print("Training models...")
    test_input = {
        'sleep_hours': 7.5,
        'work_hours': 8,
        'exercise_minutes': 30,
        'screen_time': 4,
        'caffeine_intake': 2,
        'breaks_taken': 5,
        'steps': 8500,
        'water_intake': 2.5
    }
    result = predict_wellness(test_input)
    print("\nTest Prediction:")
    print(f"  Mood:         {result['mood']} {result['mood_emoji']} ({result['mood_confidence']}% confidence)")
    print(f"  Stress Level: {result['stress_level']} {result['stress_emoji']} ({result['stress_confidence']}% confidence)")
    print(f"  Productivity: {result['productivity_score']}/100")
    print(f"  Tips:")
    for tip in result['tips']:
        print(f"    {tip}")
