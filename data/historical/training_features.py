"""Build ML feature vectors from historical World Cup results."""
from typing import Dict, List, Tuple

from app.services.elo import EloService
from app.services.feature_engine import FeatureEngine


STAGE_IMPORTANCE = {
    "小组赛": 1.0, "1/16决赛": 1.5, "1/8决赛": 2.0,
    "1/4决赛": 2.5, "半决赛": 3.0, "季军赛": 1.5, "决赛": 3.5,
}


def label_from_score(home_score: int, away_score: int) -> int:
    if home_score > away_score:
        return 0
    if home_score < away_score:
        return 2
    return 1


def build_match_features(
    home_elo: float,
    away_elo: float,
    stage: str,
    home_bonus: float = 0.0,
) -> Dict[str, float]:
    """Minimal feature dict aligned with FeatureEngine key names."""
    elo_home, elo_draw, elo_away = EloService.win_probability(
        home_elo, away_elo, home_bonus
    )
    diff = home_elo - away_elo
    home_xg = EloService.expected_goals(home_elo, away_elo, home_bonus)
    away_xg = EloService.expected_goals(away_elo, home_elo, 0)

    return {
        "elo_diff": diff,
        "fifa_rank_diff": -diff / 10.0,
        "elo_win_prob": elo_home,
        "elo_draw_prob": elo_draw,
        "recent_form_diff": 0.0,
        "goal_diff_10": 0.0,
        "market_value_ratio": diff / 500.0,
        "avg_starter_value_diff": diff * 100_000,
        "squad_depth_score_diff": 0.0,
        "injury_impact_diff": 0.0,
        "key_player_missing_home": 0.0,
        "key_player_missing_away": 0.0,
        "squad_age_diff": 0.0,
        "is_host_home": 0.0,
        "is_host_away": 0.0,
        "home_advantage_bonus": home_bonus,
        "crowd_support_score": 50.0,
        "travel_fatigue_diff": 0.0,
        "rest_day_advantage": 0.0,
        "climate_adaptation": 50.0,
        "confederation_home_advantage": 0.0,
        "weather_impact_net": 0.0,
        "altitude_effect": 0.0,
        "motivation_diff": 0.0,
        "media_pressure_diff": 0.0,
        "market_sentiment": 0.0,
        "odds_movement": 0.0,
        "manager_stability": 0.0,
        "match_stage_importance": STAGE_IMPORTANCE.get(stage, 1.0),
        "elo_x_home": diff * 0.0,
        "injury_x_stage": 0.0,
        "value_x_form": 0.0,
        "fatigue_x_rest": 0.0,
        "_home_xg": home_xg,
        "_away_xg": away_xg,
    }


def dataset_from_matches(matches: List[dict]) -> Tuple[List[Dict], List[int]]:
    """Walk matches chronologically; update Elo after each row."""
    elos: Dict[str, float] = {}
    X, y = [], []

    for row in matches:
        home, away = row["home"], row["away"]
        elos.setdefault(home, 1500.0)
        elos.setdefault(away, 1500.0)

        feats = build_match_features(elos[home], elos[away], row.get("stage", "小组赛"))
        X.append(feats)
        y.append(label_from_score(row["home_score"], row["away_score"]))

        hg, ag = row["home_score"], row["away_score"]
        if hg > ag:
            new_h, new_a = EloService.update_elo(elos[home], elos[away], hg - ag)
        elif ag > hg:
            new_a, new_h = EloService.update_elo(elos[away], elos[home], ag - hg)
        else:
            new_h, new_a = EloService.update_elo_draw(elos[home], elos[away])
        elos[home], elos[away] = new_h, new_a

    return X, y
