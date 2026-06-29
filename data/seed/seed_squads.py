"""Generate TeamSquad rows from team aggregate data in teams.json."""
import hashlib
import random

from app.models.team import TeamSquad

POSITIONS = (
    ["GK"] * 3 + ["DEF"] * 8 + ["MID"] * 8 + ["FWD"] * 7
)
STARTER_BY_POS = {"GK": 1, "DEF": 4, "MID": 4, "FWD": 2}
INJURY_TYPES = ["轻伤", "中度", "重伤", ""]


def _rng_for_team(fifa_code: str) -> random.Random:
    seed = int(hashlib.sha256(fifa_code.encode()).hexdigest()[:8], 16)
    return random.Random(seed)


def _distribute_values(total: float, n: int, rng: random.Random) -> list:
    """Zipf-like split of squad market value across players."""
    weights = [1.0 / (i + 1) ** 0.85 for i in range(n)]
    s = sum(weights)
    return [total * w / s for w in weights]


def seed_squads(session, team_map: dict) -> int:
    """Seed 26-player squads per team (11 starters). Returns player count."""
    player_count = 0

    for code, team in team_map.items():
        if code == "TBD":
            continue

        rng = _rng_for_team(code)
        total = max(team.total_market_value or 50_000_000, 10_000_000)
        values = _distribute_values(total, 26, rng)
        positions = POSITIONS.copy()
        rng.shuffle(positions)

        by_pos = {p: [] for p in ("GK", "DEF", "MID", "FWD")}
        for i, pos in enumerate(positions):
            by_pos[pos].append(i)

        starters = set()
        for pos, n_start in STARTER_BY_POS.items():
            ranked = sorted(by_pos[pos], key=lambda idx: values[idx], reverse=True)
            starters.update(ranked[:n_start])

        injured_indices = set()
        n_injured = rng.randint(0, 2)
        if n_injured:
            candidates = list(range(26))
            rng.shuffle(candidates)
            injured_indices = set(candidates[:n_injured])

        for i, pos in enumerate(positions):
            val = values[i]
            importance = min(95.0, 35.0 + (val / total) * 400)
            is_injured = i in injured_indices
            injury_detail = rng.choice(INJURY_TYPES[:3]) if is_injured else ""

            session.add(
                TeamSquad(
                    team_id=team.id,
                    name=f"{code}-{pos}-{i + 1:02d}",
                    position=pos,
                    market_value=round(val, 0),
                    is_starter=i in starters,
                    is_injured=is_injured,
                    injury_detail=injury_detail,
                    importance_score=round(importance, 1),
                    recent_form_score=round(rng.uniform(40, 85), 1),
                )
            )
            player_count += 1

        # Sync team-level injury score from squad
        injured = [i for i in injured_indices]
        if injured:
            impact = sum(
                min(95.0, 35.0 + (values[i] / total) * 400) * (0.8 if i in starters else 0.3)
                for i in injured
            )
            team.injury_impact_score = round(min(impact, 100.0), 1)

    session.flush()
    return player_count
