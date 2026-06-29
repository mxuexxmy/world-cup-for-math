"""Build World Cup historical match dataset from StatsBomb open data."""
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).resolve().parent / "world_cup_matches.json"

STATSBOMB_MATCHES = [
    (43, 3, 2018),
    (43, 106, 2022),
]

# StatsBomb country/team name → FIFA 3-letter code
TEAM_TO_FIFA = {
    "Argentina": "ARG", "Australia": "AUS", "Belgium": "BEL", "Brazil": "BRA",
    "Cameroon": "CMR", "Canada": "CAN", "Costa Rica": "CRC", "Croatia": "CRO",
    "Czech Republic": "CZE", "Czechia": "CZE", "Denmark": "DEN", "Ecuador": "ECU",
    "England": "ENG", "France": "FRA", "Germany": "GER", "Ghana": "GHA",
    "Iran": "IRN", "Japan": "JPN", "Mexico": "MEX", "Morocco": "MAR",
    "Netherlands": "NED", "Poland": "POL", "Portugal": "POR", "Qatar": "QAT",
    "Saudi Arabia": "KSA", "Senegal": "SEN", "Serbia": "SRB", "South Korea": "KOR",
    "Spain": "ESP", "Switzerland": "SUI", "Tunisia": "TUN", "United States": "USA",
    "Uruguay": "URU", "Wales": "WAL", "Costa Rica": "CRC", "Panama": "PAN",
    "Peru": "PER", "Colombia": "COL", "Iceland": "ISL", "Nigeria": "NGA",
    "South Africa": "RSA", "Paraguay": "PAR", "Russia": "RUS", "Sweden": "SWE",
    "Egypt": "EGY", "New Zealand": "NZL", "Algeria": "ALG", "Austria": "AUT",
    "Bosnia and Herzegovina": "BIH", "Chile": "CHI", "China PR": "CHN",
    "Honduras": "HON", "Italy": "ITA", "Ivory Coast": "CIV", "Côte d'Ivoire": "CIV",
    "Greece": "GRE", "Haiti": "HAI", "Iraq": "IRQ", "Jordan": "JOR",
    "North Korea": "PRK", "Slovenia": "SVN", "Turkey": "TUR", "Ukraine": "UKR",
    "Scotland": "SCO", "Norway": "NOR", "Cape Verde": "CPV", "Congo DR": "COD",
    "Democratic Republic of the Congo": "COD", "Uzbekistan": "UZB", "Curacao": "CUW",
    "Curaçao": "CUW",
}

STAGE_MAP = {
    "Group Stage": "小组赛",
    "Round of 16": "1/16决赛",
    "Quarter-finals": "1/4决赛",
    "Semi-finals": "半决赛",
    "Third Place": "季军赛",
    "Final": "决赛",
}


def _fifa_code(team_block: dict) -> str:
    name = team_block.get("country", {}).get("name") or team_block.get("home_team_name", "")
    if not name and "home_team_name" in team_block:
        name = team_block["home_team_name"]
    code = TEAM_TO_FIFA.get(name)
    if code:
        return code
    # Fallback: first 3 letters uppercase (won't match 2026 teams but keeps row)
    return name[:3].upper() if name else "UNK"


def fetch_matches(comp_id: int, season_id: int, year: int) -> list:
    url = (
        f"https://raw.githubusercontent.com/statsbomb/open-data/master/"
        f"data/matches/{comp_id}/{season_id}.json"
    )
    resp = httpx.get(url, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    rows = []
    for m in resp.json():
        if m.get("home_score") is None or m.get("away_score") is None:
            continue
        home_name = m["home_team"]["home_team_name"]
        away_name = m["away_team"]["away_team_name"]
        home = TEAM_TO_FIFA.get(home_name) or TEAM_TO_FIFA.get(
            m["home_team"].get("country", {}).get("name", "")
        )
        away = TEAM_TO_FIFA.get(away_name) or TEAM_TO_FIFA.get(
            m["away_team"].get("country", {}).get("name", "")
        )
        if not home:
            home = TEAM_TO_FIFA.get(m["home_team"].get("country", {}).get("name", ""))
        if not away:
            away = TEAM_TO_FIFA.get(m["away_team"].get("country", {}).get("name", ""))
        if not home or not away:
            print(f"[WARN] Skip unmapped: {home_name} vs {away_name}")
            continue
        stage_en = (m.get("competition_stage") or {}).get("name", "Group Stage")
        rows.append({
            "year": year,
            "date": m.get("match_date", "")[:10],
            "stage": STAGE_MAP.get(stage_en, stage_en),
            "home": home,
            "away": away,
            "home_score": m["home_score"],
            "away_score": m["away_score"],
            "neutral": True,
        })
    return rows


def main():
    all_matches = []
    for comp_id, season_id, year in STATSBOMB_MATCHES:
        batch = fetch_matches(comp_id, season_id, year)
        print(f"[OK] {year} World Cup: {len(batch)} matches")
        all_matches.extend(batch)

    all_matches.sort(key=lambda x: (x["year"], x["date"]))
    OUT.write_text(
        json.dumps({"source": "statsbomb/open-data", "matches": all_matches}, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] Wrote {len(all_matches)} matches to {OUT}")


if __name__ == "__main__":
    main()
