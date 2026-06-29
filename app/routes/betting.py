"""Betting recommendation route."""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.templates_env import jinja_env
from app.models.database import get_db
from app.models.prediction import BetRecommendation, BetLedger
from app.models.match import Match

router = APIRouter(prefix="/betting", tags=["Betting"])


@router.get("/", response_class=HTMLResponse)
async def betting_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Betting recommendations page."""
    from app.services.bet_optimizer import BetOptimizer
    from app.models.prediction import BetLedger

    result = await db.execute(
        select(BetRecommendation)
        .order_by(BetRecommendation.expected_value.desc())
        .limit(20)
    )
    recommendations = result.scalars().all()

    # Get bankroll summary
    optimizer = BetOptimizer(db)
    summary = await optimizer.get_bankroll_summary()

    # Get recent ledger entries
    result = await db.execute(
        select(BetLedger)
        .options(
            selectinload(BetLedger.match).selectinload(Match.home_team),
            selectinload(BetLedger.match).selectinload(Match.away_team),
        )
        .order_by(BetLedger.created_at.desc())
        .limit(20)
    )
    ledger = result.scalars().all()

    # Enrich parlay legs with team names from matches when missing
    leg_match_ids = set()
    for entry in ledger:
        for leg in entry.get_legs():
            if leg.get("match_id") and not leg.get("home_team"):
                leg_match_ids.add(leg["match_id"])
    if leg_match_ids:
        result = await db.execute(
            select(Match)
            .options(selectinload(Match.home_team), selectinload(Match.away_team))
            .where(Match.id.in_(leg_match_ids))
        )
        match_map = {m.id: m for m in result.scalars().all()}
        for entry in ledger:
            legs = entry.get_legs()
            if not legs:
                continue
            changed = False
            for leg in legs:
                if leg.get("home_team"):
                    continue
                m = match_map.get(leg.get("match_id"))
                if m:
                    leg["home_team"] = m.home_team.name_cn
                    leg["away_team"] = m.away_team.name_cn
                    changed = True
            if changed:
                entry.set_legs(legs)

    template = jinja_env.get_template("betting.html")
    html = template.render(
        request=request,
        recommendations=recommendations,
        ledger=ledger,
        bankroll=summary["bankroll"],
        total_profit=summary["total_profit"],
        today_staked=summary["today_staked"],
        today_remaining=summary["today_remaining"],
        title="投注推荐 - 价值投注 & 过关组合",
    )
    return HTMLResponse(html)


@router.get("/api/recommendations")
async def get_recommendations(db: AsyncSession = Depends(get_db)):
    """API: Get current betting recommendations."""
    from app.services.bet_optimizer import BetOptimizer
    optimizer = BetOptimizer(db)
    return await optimizer.get_recommendations()


@router.post("/api/optimize")
async def run_optimization(db: AsyncSession = Depends(get_db)):
    """API: Run the betting optimizer."""
    from app.services.bet_optimizer import BetOptimizer
    optimizer = BetOptimizer(db)
    return await optimizer.optimize()


@router.post("/api/place-bet/{rec_id}")
async def place_bet(rec_id: int, db: AsyncSession = Depends(get_db)):
    """API: Place a bet from a recommendation."""
    from app.services.bet_optimizer import BetOptimizer
    optimizer = BetOptimizer(db)
    return await optimizer.place_bet(rec_id)


@router.post("/api/cancel-bet/{bet_id}")
async def cancel_bet_entry(bet_id: int, db: AsyncSession = Depends(get_db)):
    """Cancel a pending bet."""
    from sqlalchemy import select
    from app.models.prediction import BetLedger
    result = await db.execute(select(BetLedger).where(BetLedger.id == bet_id))
    bet = result.scalar_one_or_none()
    if not bet:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Bet not found")
    if bet.result != "pending":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Cannot cancel settled bet")
    await db.delete(bet)
    await db.commit()
    return {"status": "ok", "cancelled": bet_id}


@router.get("/api/bankroll")
async def get_bankroll(db: AsyncSession = Depends(get_db)):
    """API: Get current bankroll summary."""
    from app.services.bet_optimizer import BetOptimizer
    optimizer = BetOptimizer(db)
    return await optimizer.get_bankroll_summary()


