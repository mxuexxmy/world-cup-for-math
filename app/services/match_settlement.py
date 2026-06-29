"""Post-match pipeline: Elo, results, bets, prediction refresh."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.match import Match
from app.models.prediction import MatchResult, Prediction
from app.services.elo import EloService
from app.services.predictor import PredictionEngine
from app.services.bet_optimizer import BetOptimizer


async def settle_finished_match(
    db: AsyncSession,
    match: Match,
    home_score: int,
    away_score: int,
) -> None:
    """Run full downstream updates after a match is marked finished."""
    home = match.home_team
    away = match.away_team

    if home_score > away_score:
        goal_diff = home_score - away_score
        new_home, new_away = EloService.update_elo(
            home.elo_rating, away.elo_rating, goal_diff, is_draw=False
        )
    elif away_score > home_score:
        goal_diff = away_score - home_score
        new_away, new_home = EloService.update_elo(
            away.elo_rating, home.elo_rating, goal_diff, is_draw=False
        )
    else:
        new_home, new_away = EloService.update_elo_draw(home.elo_rating, away.elo_rating)

    home.elo_rating = new_home
    away.elo_rating = new_away
    await db.flush()

    pred_result = await db.execute(
        select(Prediction).where(Prediction.match_id == match.id)
    )
    pred = pred_result.scalar_one_or_none()

    existing = await db.execute(
        select(MatchResult).where(MatchResult.match_id == match.id)
    )
    if existing.scalar_one_or_none():
        await BetOptimizer.settle_bets_for_match(db, match.id, home_score, away_score)
        return

    accuracy = 0.0
    if pred:
        if home_score > away_score:
            actual = "home"
        elif away_score > home_score:
            actual = "away"
        else:
            actual = "draw"
        probs = {
            "home": pred.prob_home_win,
            "draw": pred.prob_draw,
            "away": pred.prob_away_win,
        }
        accuracy = probs.get(actual, 0.0)

    db.add(
        MatchResult(
            match_id=match.id,
            actual_home_score=home_score,
            actual_away_score=away_score,
            prediction_accuracy_score=round(accuracy, 4),
        )
    )
    await db.commit()

    await BetOptimizer.settle_bets_for_match(db, match.id, home_score, away_score)

    engine = PredictionEngine(db)
    remaining = await db.execute(
        select(Match).where(Match.status == "scheduled").order_by(Match.match_date)
    )
    for m in remaining.scalars().all():
        try:
            await engine.predict_match(m.id)
        except Exception:
            pass
