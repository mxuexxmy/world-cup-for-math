"""Match detail route."""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.templates_env import jinja_env
from app.models.database import get_db
from app.models.match import Match

router = APIRouter(prefix="/match", tags=["Matches"])


@router.get("/{match_id}", response_class=HTMLResponse)
async def match_detail(match_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    """Match detail page with predictions, odds, and factor breakdown."""
    result = await db.execute(
        select(Match)
        .options(
            selectinload(Match.home_team),
            selectinload(Match.away_team),
            selectinload(Match.odds),
            selectinload(Match.prediction),
            selectinload(Match.external_factors),
        )
        .where(Match.id == match_id)
    )
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    template = jinja_env.get_template("match_detail.html")
    html = template.render(
        request=request,
        match=match,
        title=f"{match.home_team.name_cn} vs {match.away_team.name_cn}",
    )
    return HTMLResponse(html)
