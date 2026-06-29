"""Tests for squad seeding and historical training data."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "historical" / "world_cup_matches.json"


def test_world_cup_historical_dataset():
    assert HIST.exists(), "Run: python data/historical/build_dataset.py"
    data = json.loads(HIST.read_text(encoding="utf-8"))
    matches = data["matches"]
    assert len(matches) >= 120
    for m in matches:
        assert m["home_score"] is not None
        assert m["home"] and m["away"]


def test_historical_training_features():
    from data.historical.training_features import dataset_from_matches, label_from_score

    assert label_from_score(2, 1) == 0
    assert label_from_score(1, 1) == 1
    assert label_from_score(0, 1) == 2

    sample = [
        {"home": "BRA", "away": "GER", "home_score": 1, "away_score": 0, "stage": "小组赛"},
        {"home": "GER", "away": "BRA", "home_score": 0, "away_score": 2, "stage": "小组赛"},
    ]
    X, y = dataset_from_matches(sample)
    assert len(X) == 2
    assert len(y) == 2
    assert "elo_diff" in X[0]


def test_seed_squads_generates_26_per_team():
    from data.seed.seed_squads import seed_squads, POSITIONS
    from app.models.database import init_db_sync, SyncSession, migrate_db_sync
    from app.models.team import Team, TeamSquad
    from sqlalchemy import select, func

    migrate_db_sync()
    session = SyncSession()
    try:
        session.query(TeamSquad).delete()
        session.query(Team).delete()
        session.commit()
        t = Team(
            name_cn="测试", name_en="Test", fifa_code="TST",
            fifa_ranking=50, elo_rating=1600, elo_rating_initial=1600,
            total_market_value=100_000_000, avg_age=27.0, squad_size=26,
        )
        session.add(t)
        session.flush()
        n = seed_squads(session, {"TST": t})
        session.commit()
        assert n == len(POSITIONS)
        count = session.scalar(
            select(func.count()).select_from(TeamSquad).where(TeamSquad.team_id == t.id)
        )
        starters = session.scalars(
            select(TeamSquad).where(TeamSquad.team_id == t.id, TeamSquad.is_starter == True)
        ).all()
        assert count == 26
        assert len(starters) == 11
    finally:
        session.close()
