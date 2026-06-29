"""Admin panel routes."""
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.auth import require_admin
from app.templates_env import jinja_env
from app.models.database import get_db
from app.models.match import Match
from app.models.odds import Odds
from app.models.team import Team
from app.models.prediction import Prediction, BetLedger

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)])


@router.get("/", response_class=HTMLResponse)
async def admin_panel(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Match)
        .options(selectinload(Match.home_team), selectinload(Match.away_team))
        .where(Match.status.in_(["scheduled", "live"]))
        .order_by(Match.match_date)
        .limit(50)
    )
    matches = result.scalars().all()

    result = await db.execute(select(Team).order_by(Team.name_cn))
    teams = result.scalars().all()

    match_count = await db.scalar(select(func.count()).select_from(Match))
    team_count = await db.scalar(select(func.count()).select_from(Team))
    pred_count = await db.scalar(select(func.count()).select_from(Prediction))

    template = jinja_env.get_template("admin.html")
    html = template.render(
        request=request,
        matches=matches,
        teams=teams,
        match_count=match_count,
        team_count=team_count,
        pred_count=pred_count,
        saved=request.query_params.get("updated") == "1",
        title="管理后台",
    )
    return HTMLResponse(html)


@router.post("/match/{match_id}/result")
async def update_match_result(
    match_id: int,
    home_score: int = Form(...),
    away_score: int = Form(...),
    db: AsyncSession = Depends(get_db),
):
    from app.services.scraper import FifaMatchSync
    result = await FifaMatchSync.manual_score_update(db, match_id, home_score, away_score)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return RedirectResponse(url="/admin?updated=1", status_code=303)


@router.post("/match/{match_id}/odds")
async def update_odds(
    match_id: int,
    win_odds: float = Form(None),
    draw_odds: float = Form(None),
    lose_odds: float = Form(None),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Odds).where(Odds.match_id == match_id))
    odds = result.scalar_one_or_none()

    if not odds:
        odds = Odds(match_id=match_id, updated_at=datetime.utcnow())
        db.add(odds)

    if win_odds is not None:
        odds.win_odds = win_odds
    if draw_odds is not None:
        odds.draw_odds = draw_odds
    if lose_odds is not None:
        odds.lose_odds = lose_odds
    odds.updated_at = datetime.utcnow()
    odds.source = "手动录入"

    await db.commit()
    return RedirectResponse(url="/admin?updated=1", status_code=303)


@router.post("/predict-all")
async def admin_predict_all(db: AsyncSession = Depends(get_db)):
    from app.services.predictor import PredictionEngine
    from app.services.external_factors import ExternalFactorsService

    engine = PredictionEngine(db)
    result = await db.execute(
        select(Match).where(Match.status == "scheduled").order_by(Match.match_date)
    )
    matches = result.scalars().all()
    count = 0
    errors = 0
    for match in matches:
        try:
            await ExternalFactorsService.evaluate_match(db, match.id)
            await engine.predict_match(match.id)
            count += 1
        except Exception as e:
            errors += 1
            print(f"[Admin] predict {match.id}: {e}")
    return {"status": "ok", "predicted": count, "total": len(matches), "errors": errors}
