"""Seed database with OFFICIAL 2026 World Cup data (Beijing Time)."""
import json, sys, io
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
except: pass

from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.config import FIFA_COMPETITION_ID, FIFA_SEASON_ID

from app.models.database import init_db_sync, SyncSession
from app.models.team import Team
from app.models.match import Match, Group
from app.config import SEED_DIR
from data.seed.seed_squads import seed_squads

BJT = lambda m,d,h: datetime(2026, m, d, h, 0, 0)

FIFA_STAGE_MAP = {
    "Round of 32": "1/16决赛",
    "Round of 16": "1/8决赛",
    "Quarter-final": "1/4决赛",
    "Semi-final": "半决赛",
    "Play-off for third place": "季军赛",
    "Final": "决赛",
}
FIFA_CITY_MAP = {
    "New Jersey": "NY/NJ",
    "San Francisco Bay Area": "San Francisco",
}

VENUES_CN = {
    "Mexico City": "阿兹台克体育场", "Guadalajara": "阿克伦体育场",
    "Monterrey": "BBVA体育场", "Toronto": "BMO球场",
    "Vancouver": "BC广场", "Los Angeles": "SoFi体育场",
    "San Francisco": "李维斯体育场", "Seattle": "流明球场",
    "Dallas": "AT&T体育场", "Houston": "NRG体育场",
    "Kansas City": "箭头体育场", "Atlanta": "梅赛德斯-奔驰体育场",
    "Miami": "硬石体育场", "Boston": "吉列体育场",
    "Philadelphia": "林肯金融球场", "NY/NJ": "大都会人寿体育场",
}

VENUE_ALTITUDES = {
    "Mexico City": 2250, "Guadalajara": 1560, "Monterrey": 540,
    "Toronto": 76, "Vancouver": 2, "Los Angeles": 30, "San Francisco": 10,
    "Seattle": 50, "Dallas": 130, "Houston": 13, "Kansas City": 270,
    "Atlanta": 320, "Miami": 2, "Boston": 70, "Philadelphia": 12, "NY/NJ": 2,
}


def _fifa_locale_desc(items, locale: str = "en-GB") -> str:
    if not items:
        return ""
    if isinstance(items, str):
        return items
    for item in items:
        if item.get("Locale") == locale:
            return item.get("Description", "") or ""
    return items[0].get("Description", "") or ""


def ensure_tbd_team(session, team_map):
    """Placeholder team for knockout slots not yet decided."""
    if "TBD" in team_map:
        return team_map
    tbd = Team(
        name_cn="待定", name_en="TBD", fifa_code="TBD",
        fifa_ranking=999, elo_rating=1500, elo_rating_initial=1500,
        is_host=False, host_country="", confederation="",
        total_market_value=0, avg_age=26.0, squad_size=0,
    )
    session.add(tbd)
    session.flush()
    team_map["TBD"] = tbd
    return team_map


def load_fifa_calendar() -> list:
    """Fetch all World Cup matches from FIFA API."""
    try:
        url = (
            "https://api.fifa.com/api/v3/calendar/matches"
            f"?idCompetition={FIFA_COMPETITION_ID}&idSeason={FIFA_SEASON_ID}"
            "&language=en&count=500"
        )
        req = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("Results") or []
    except Exception as e:
        print(f"[WARN] FIFA calendar fetch failed: {e}")
        return []


def _matchday_from_date(month: int, day: int) -> int:
    """Infer World Cup group matchday from kickoff date (Beijing time)."""
    if month != 6:
        return 1
    if day <= 18:
        return 1
    if day <= 24:
        return 2
    return 3


def _fifa_group_name(row: dict) -> str:
    desc = _fifa_locale_desc(row.get("GroupName"))
    return desc.replace("Group ", "").strip()


def _row_to_group_entry(row: dict, team_map: dict) -> dict:
    """Convert a FIFA First Stage calendar row to seed entry."""
    home = row.get("Home") or {}
    away = row.get("Away") or {}
    home_code = home.get("IdCountry") or ""
    away_code = away.get("IdCountry") or ""
    if home_code not in team_map or away_code not in team_map:
        raise ValueError(f"Unknown team in FIFA group fixture: {home_code} vs {away_code}")

    bjt = timezone(timedelta(hours=8))
    dt = datetime.fromisoformat(row["Date"].replace("Z", "+00:00")).astimezone(bjt)
    city = _fifa_locale_desc((row.get("Stadium") or {}).get("CityName"))
    city = FIFA_CITY_MAP.get(city, city)

    return {
        "fifa_match_id": str(row.get("IdMatch", "")),
        "group": _fifa_group_name(row),
        "matchday": _matchday_from_date(dt.month, dt.day),
        "month": dt.month,
        "day": dt.day,
        "hour": dt.hour,
        "home": home_code,
        "away": away_code,
        "city": city,
        "stadium": _fifa_locale_desc((row.get("Stadium") or {}).get("Name")),
    }


def load_group_schedule(team_map: dict) -> list:
    """Load group-stage fixtures from FIFA API, fallback to group_schedule.json."""
    try:
        rows = load_fifa_calendar()
        matches = []
        for row in rows:
            stage_en = row.get("StageName", [{}])[0].get("Description", "")
            if stage_en != "First Stage":
                continue
            matches.append(_row_to_group_entry(row, team_map))
        if len(matches) == 72:
            matches.sort(key=lambda x: (x["month"], x["day"], x["hour"]))
            print(f"[OK] Loaded {len(matches)} group matches from FIFA API")
            return matches
        print(f"[WARN] FIFA returned {len(matches)} group matches, expected 72")
    except Exception as e:
        print(f"[WARN] FIFA group fetch failed: {e}")

    with open(SEED_DIR / "group_schedule.json", "r", encoding="utf-8") as f:
        matches = json.load(f)["matches"]
    for entry in matches:
        if entry["home"] not in team_map or entry["away"] not in team_map:
            raise ValueError(
                f"group_schedule.json: unknown team {entry['home']} vs {entry['away']}"
            )
    print(f"[OK] Loaded {len(matches)} group matches from group_schedule.json")
    return matches


def load_knockout_schedule() -> list:
    """Load knockout fixtures from FIFA API, fallback to local JSON."""
    try:
        rows = load_fifa_calendar()
        bjt = timezone(timedelta(hours=8))
        matches = []
        for row in rows:
            stage_en = row.get("StageName", [{}])[0].get("Description", "")
            if stage_en == "First Stage":
                continue
            home = row.get("Home") or {}
            away = row.get("Away") or {}
            dt = datetime.fromisoformat(row["Date"].replace("Z", "+00:00")).astimezone(bjt)
            city = _fifa_locale_desc((row.get("Stadium") or {}).get("CityName"))
            city = FIFA_CITY_MAP.get(city, city)
            matches.append({
                "fifa_match_id": str(row.get("IdMatch", "")),
                "stage": FIFA_STAGE_MAP.get(stage_en, stage_en),
                "month": dt.month,
                "day": dt.day,
                "hour": dt.hour,
                "home": home.get("IdCountry") or "TBD",
                "away": away.get("IdCountry") or "TBD",
                "city": city,
                "stadium": _fifa_locale_desc((row.get("Stadium") or {}).get("Name")),
            })
        if matches:
            print(f"[OK] Loaded {len(matches)} knockout matches from FIFA API")
            return matches
    except Exception as e:
        print(f"[WARN] FIFA knockout fetch failed: {e}")

    with open(SEED_DIR / "knockout_schedule.json", "r", encoding="utf-8") as f:
        matches = json.load(f)["matches"]
    print(f"[OK] Loaded {len(matches)} knockout matches from knockout_schedule.json")
    return matches


def seed_teams(session):
    with open(SEED_DIR / "teams.json", "r", encoding="utf-8") as f:
        teams_data = json.load(f)
    team_map = {}
    for t in teams_data:
        team = Team(
            name_cn=t["name_cn"], name_en=t["name_en"],
            fifa_code=t["fifa_code"], fifa_ranking=t["fifa_ranking"],
            elo_rating=t["elo_rating"], elo_rating_initial=t["elo_rating"],
            is_host=t["is_host"], host_country=t["host_country"],
            confederation=t["confederation"],
            total_market_value=t["total_market_value"],
            avg_age=t["avg_age"], squad_size=26,
            home_advantage_bonus=(80 if t["is_host"] else 0),
        )
        session.add(team)
        team_map[t["fifa_code"]] = team
    session.flush()
    print(f"[OK] Seeded {len(teams_data)} teams")
    return team_map


def seed_groups(session, team_map):
    with open(SEED_DIR / "groups.json", "r", encoding="utf-8") as f:
        groups_data = json.load(f)
    for g in groups_data:
        team_ids = [team_map[code].id for code in g["teams"]]
        group = Group(name=g["name"], teams_json=json.dumps(team_ids))
        session.add(group)
        session.flush()
        for code in g["teams"]:
            team_map[code].group_id = group.id
    session.flush()
    print(f"[OK] Seeded {len(groups_data)} groups")


def generate_schedule(session, team_map):
    """Official 2026 World Cup schedule — ALL TIMES ARE BEIJING TIME (UTC+8)."""
    matches = []

    # ===== GROUP STAGE (72 matches) — from FIFA API / group_schedule.json =====
    gs_data = load_group_schedule(team_map)
    for entry in gs_data:
        city = entry["city"]
        venue_name = VENUES_CN.get(city, city)
        alt = VENUE_ALTITUDES.get(city, 0)
        home_code = entry["home"]
        away_code = entry["away"]
        m_obj = Match(
            fifa_match_id=entry.get("fifa_match_id"),
            match_date=BJT(entry["month"], entry["day"], entry["hour"]),
            stage="小组赛",
            matchday=entry["matchday"],
            home_team_id=team_map[home_code].id,
            away_team_id=team_map[away_code].id,
            status="scheduled",
            venue=venue_name,
            city=city,
            stadium=entry.get("stadium") or venue_name,
            altitude=alt,
        )
        session.add(m_obj)
        matches.append(m_obj)

    session.flush()

    # ===== KNOCKOUT STAGE (32 matches) — from FIFA API / knockout_schedule.json =====
    team_map = ensure_tbd_team(session, team_map)
    ko_data = load_knockout_schedule()
    for entry in ko_data:
        home_code = entry["home"] if entry["home"] in team_map else "TBD"
        away_code = entry["away"] if entry["away"] in team_map else "TBD"
        city = entry["city"]
        venue_name = VENUES_CN.get(city, city)
        alt = VENUE_ALTITUDES.get(city, 0)
        m_obj = Match(
            fifa_match_id=entry.get("fifa_match_id"),
            match_date=BJT(entry["month"], entry["day"], entry["hour"]),
            stage=entry["stage"],
            matchday=0,
            home_team_id=team_map[home_code].id,
            away_team_id=team_map[away_code].id,
            status="scheduled",
            venue=venue_name,
            city=city,
            stadium=entry.get("stadium") or venue_name,
            altitude=alt,
        )
        session.add(m_obj)
        matches.append(m_obj)

    session.flush()
    print(f"[OK] Generated {len(matches)} matches ({len(gs_data)} group + {len(ko_data)} knockout = {len(gs_data)+len(ko_data)})")

    # Print today's matches (June 12 BJT)
    today = datetime(2026, 6, 12).date()
    today_ms = [m for m in matches if m.match_date.date() == today]
    print(f"\n  >>> Today (June 12, Beijing Time):")
    for m in sorted(today_ms, key=lambda x: x.match_date):
        h = session.get(Team, m.home_team_id)
        a = session.get(Team, m.away_team_id)
        print(f"    {m.match_date.strftime('%m/%d %H:%M')} BJT  {h.name_cn} vs {a.name_cn}  [{m.stage} {m.city}]")

    validate_seeded_matches(session, team_map, gs_data, ko_data)
    return matches


KNOCKOUT_STAGE_COUNTS = {
    "1/16决赛": 16,
    "1/8决赛": 8,
    "1/4决赛": 4,
    "半决赛": 2,
    "季军赛": 1,
    "决赛": 1,
}


def validate_seeded_matches(session, team_map, gs_data: list, ko_data: list):
    """Fail fast if schedule seed looks wrong (avoids silent placeholder bugs)."""
    from app.config import TOTAL_MATCHES

    total = session.query(Match).count()
    if total != TOTAL_MATCHES:
        raise ValueError(f"Expected {TOTAL_MATCHES} matches, got {total}")

    group_matches = session.query(Match).filter(Match.stage == "小组赛").all()
    if len(group_matches) != 72:
        raise ValueError(f"Expected 72 group-stage matches, got {len(group_matches)}")

    group_fifa_ids = [m.fifa_match_id for m in group_matches]
    if any(not fid for fid in group_fifa_ids):
        raise ValueError("All 72 group matches must have fifa_match_id")
    if len(set(group_fifa_ids)) != 72:
        raise ValueError("Duplicate fifa_match_id in group stage")

    if len(gs_data) != 72:
        raise ValueError(f"group schedule source has {len(gs_data)} entries, expected 72")

    knockout = session.query(Match).filter(Match.stage != "小组赛").all()
    if len(knockout) != 32:
        raise ValueError(f"Expected 32 knockout matches, got {len(knockout)}")

    stage_counts = {}
    for m in knockout:
        stage_counts[m.stage] = stage_counts.get(m.stage, 0) + 1
    for stage, expected in KNOCKOUT_STAGE_COUNTS.items():
        got = stage_counts.get(stage, 0)
        if got != expected:
            raise ValueError(f"Stage {stage}: expected {expected} matches, got {got}")

    fifa_ids_all = [m.fifa_match_id for m in session.query(Match).all() if m.fifa_match_id]
    if len(fifa_ids_all) != TOTAL_MATCHES:
        raise ValueError(f"Expected {TOTAL_MATCHES} fifa_match_id values, got {len(fifa_ids_all)}")
    if any(not fid for fid in [m.fifa_match_id for m in knockout]):
        raise ValueError("All knockout matches must have fifa_match_id")
    if len(set(fifa_ids_all)) != len(fifa_ids_all):
        raise ValueError("Duplicate fifa_match_id in schedule")

    tbd_id = team_map["TBD"].id
    mex_id = team_map["MEX"].id
    rsa_id = team_map["RSA"].id

    for m in knockout:
        if m.home_team_id == m.away_team_id and m.home_team_id != tbd_id:
            raise ValueError(f"Match {m.fifa_match_id}: home and away are the same team")
        if m.home_team_id == mex_id and m.away_team_id == rsa_id:
            raise ValueError(
                "Knockout placeholder detected (Mexico vs South Africa on every match). "
                "Check load_knockout_schedule()."
            )

    r32 = [m for m in knockout if m.stage == "1/16决赛"]
    for m in r32:
        if m.home_team_id == tbd_id or m.away_team_id == tbd_id:
            home = session.get(Team, m.home_team_id)
            away = session.get(Team, m.away_team_id)
            raise ValueError(
                f"Round of 32 must have both teams set: "
                f"{home.name_cn} vs {away.name_cn} (fifa_match_id={m.fifa_match_id})"
            )

    if len(ko_data) != 32:
        raise ValueError(f"knockout_schedule source has {len(ko_data)} entries, expected 32")

    print("[OK] Seed validation passed (104 matches, all fifa_match_id OK)")


if __name__ == "__main__":
    print("Seeding 2026 World Cup (Official Data, Beijing Time)...")
    init_db_sync()
    session = SyncSession()
    try:
        team_map = seed_teams(session)
        seed_groups(session, team_map)
        n_players = seed_squads(session, team_map)
        print(f"[OK] Seeded {n_players} squad players ({len([c for c in team_map if c != 'TBD'])} teams)")
        generate_schedule(session, team_map)
        session.commit()
        print("\n[OK] Database seeded successfully!")
    except Exception as e:
        session.rollback()
        import traceback; traceback.print_exc()
        raise
    finally:
        session.close()
