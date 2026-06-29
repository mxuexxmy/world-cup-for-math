"""Train sklearn GradientBoosting on historical World Cup results."""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import cross_val_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import HISTORICAL_DIR
from app.services.feature_engine import FeatureEngine
from data.historical.training_features import dataset_from_matches

OUT = ROOT / "data" / "model.pkl"
HISTORICAL_JSON = HISTORICAL_DIR / "world_cup_matches.json"


def load_historical_matches() -> list:
    if not HISTORICAL_JSON.exists():
        print("[INFO] Building historical dataset from StatsBomb...")
        from data.historical.build_dataset import main as build_main
        build_main()
    data = json.loads(HISTORICAL_JSON.read_text(encoding="utf-8"))
    return data["matches"]


def main():
    matches = load_historical_matches()
    if len(matches) < 50:
        raise RuntimeError(f"Need at least 50 historical matches, got {len(matches)}")

    feature_dicts, labels = dataset_from_matches(matches)
    X = np.vstack([FeatureEngine.to_array(f) for f in feature_dicts])
    y = np.array(labels)

    model = GradientBoostingClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.08,
        random_state=42,
    )
    model.fit(X, y)

    cv = cross_val_score(model, X, y, cv=5, scoring="accuracy")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "wb") as f:
        pickle.dump(model, f)

    print(f"[OK] Trained on {len(matches)} World Cup matches (2018+2022)")
    print(f"[OK] Train accuracy {model.score(X, y):.3f}, CV mean {cv.mean():.3f} (+/- {cv.std():.3f})")
    print(f"[OK] Saved model to {OUT}")


if __name__ == "__main__":
    main()
