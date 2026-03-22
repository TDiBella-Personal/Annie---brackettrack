"""Fetch NCAA tournament bracket data from ncaa-api (primary) or SportRadar (fallback)."""

import json
import os
import time
from datetime import datetime, timedelta

import requests

NCAA_API_BASE = "https://ncaa-api.henrygd.me"
SPORTRADAR_BASE = "https://api.sportradar.us"
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")

# NCAA tournament structure
REGIONS = ["South", "East", "Midwest", "West"]
ROUNDS = [
    "First Four",
    "Round of 64",
    "Round of 32",
    "Sweet 16",
    "Elite 8",
    "Final Four",
    "Championship",
]


def _get_with_retry(url, params=None, max_retries=2, delay=1.0):
    """GET request with retry logic."""
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429:
                time.sleep(delay * (attempt + 1))
                continue
            resp.raise_for_status()
        except requests.RequestException:
            if attempt == max_retries - 1:
                raise
            time.sleep(delay * (attempt + 1))
    return None


def fetch_ncaa_scoreboard(gender, date_str):
    """Fetch scoreboard from ncaa-api for a given date.

    Args:
        gender: 'men' or 'women'
        date_str: date in YYYY/MM/DD format
    """
    sport = f"basketball-{gender}"
    url = f"{NCAA_API_BASE}/scoreboard/{sport}/d1/{date_str}"
    try:
        data = _get_with_retry(url)
        if data and "games" in data:
            return data["games"]
    except Exception:
        pass
    return []


def fetch_ncaa_game(game_id):
    """Fetch detailed game data from ncaa-api."""
    url = f"{NCAA_API_BASE}/game/{game_id}"
    try:
        return _get_with_retry(url)
    except Exception:
        return None


def fetch_sportradar_bracket(gender, season_year=None, api_key=None):
    """Fallback: fetch bracket from SportRadar API.

    Args:
        gender: 'men' or 'women'
        season_year: e.g., 2026
        api_key: SportRadar API key
    """
    if not api_key:
        api_key = os.environ.get("SPORTRADAR_API_KEY", "")
    if not api_key:
        return None

    sport = "ncaamb" if gender == "men" else "ncaawb"
    if season_year is None:
        season_year = datetime.now().year

    url = f"{SPORTRADAR_BASE}/{sport}/trial/v8/en/tournaments/{season_year}/PST/schedule.json"
    try:
        data = _get_with_retry(url, params={"api_key": api_key})
        if data and "tournaments" in data:
            for t in data["tournaments"]:
                if "NCAA" in t.get("name", "") and "Tournament" in t.get("name", ""):
                    tournament_id = t["id"]
                    summary_url = f"{SPORTRADAR_BASE}/{sport}/trial/v8/en/tournaments/{tournament_id}/summary.json"
                    return _get_with_retry(summary_url, params={"api_key": api_key})
    except Exception:
        pass
    return None


def _parse_ncaa_games(raw_games):
    """Parse ncaa-api game data into our standard format."""
    games = []
    for g in raw_games:
        game = g.get("game", g)
        home = game.get("home", {})
        away = game.get("away", {})

        parsed = {
            "game_id": game.get("gameID", game.get("url", "")),
            "status": game.get("gameState", game.get("currentPeriod", "pre")),
            "start_time": game.get("startTime", game.get("startTimeEpoch", "")),
            "network": game.get("network", ""),
            "round": game.get("bracketRound", game.get("currentRound", "")),
            "region": game.get("bracketRegion", ""),
            "home": {
                "name": home.get("names", {}).get("short", home.get("name", "TBD")),
                "seed": home.get("seed", home.get("description", "")),
                "score": home.get("score", ""),
                "winner": home.get("winner", False),
            },
            "away": {
                "name": away.get("names", {}).get("short", away.get("name", "TBD")),
                "seed": away.get("seed", away.get("description", "")),
                "score": away.get("score", ""),
                "winner": away.get("winner", False),
            },
        }

        # Determine final status
        state = str(game.get("gameState", "")).lower()
        if state in ("final", "f", "post"):
            parsed["status"] = "final"
        elif state in ("live", "in_progress", "i"):
            parsed["status"] = "live"
        else:
            parsed["status"] = "pre"

        games.append(parsed)
    return games


def _parse_sportradar_bracket(data):
    """Parse SportRadar bracket summary into our standard format."""
    if not data:
        return {"rounds": [], "games": [], "teams": []}

    games = []
    teams_seen = set()
    teams = []

    for round_data in data.get("rounds", []):
        round_name = round_data.get("name", "")
        for bracket in round_data.get("bracketed", [{"games": round_data.get("games", [])}]):
            region = bracket.get("bracket", {}).get("name", "")
            for g in bracket.get("games", []):
                home = g.get("home", {})
                away = g.get("away", {})
                home_name = home.get("name", home.get("alias", "TBD"))
                away_name = away.get("name", away.get("alias", "TBD"))

                parsed = {
                    "game_id": g.get("id", ""),
                    "status": g.get("status", "scheduled").lower(),
                    "start_time": g.get("scheduled", ""),
                    "network": g.get("broadcast", {}).get("network", ""),
                    "round": round_name,
                    "region": region,
                    "home": {
                        "name": home_name,
                        "seed": home.get("seed", ""),
                        "score": home.get("points", ""),
                        "winner": g.get("status", "") == "closed" and int(home.get("points", 0) or 0) > int(away.get("points", 0) or 0),
                    },
                    "away": {
                        "name": away_name,
                        "seed": away.get("seed", ""),
                        "score": away.get("points", ""),
                        "winner": g.get("status", "") == "closed" and int(away.get("points", 0) or 0) > int(home.get("points", 0) or 0),
                    },
                }

                if parsed["status"] in ("closed", "complete"):
                    parsed["status"] = "final"
                elif parsed["status"] in ("inprogress", "halftime"):
                    parsed["status"] = "live"
                else:
                    parsed["status"] = "pre"

                games.append(parsed)

                for team_data, key in [(home, "home"), (away, "away")]:
                    name = team_data.get("name", team_data.get("alias", ""))
                    if name and name not in teams_seen:
                        teams_seen.add(name)
                        teams.append({
                            "name": name,
                            "seed": team_data.get("seed", ""),
                            "eliminated": False,
                        })

    return {"games": games, "teams": teams}


def build_bracket_state(games):
    """Build bracket state from a list of parsed games.

    Returns dict with:
        - teams: list of team dicts with elimination status
        - rounds: dict mapping round name to list of games
        - regions: dict mapping region name to list of games
    """
    teams = {}
    rounds = {}
    regions = {}

    for game in games:
        # Track rounds
        round_name = game.get("round", "Unknown")
        rounds.setdefault(round_name, []).append(game)

        # Track regions
        region = game.get("region", "")
        if region:
            regions.setdefault(region, []).append(game)

        # Track teams
        for side in ("home", "away"):
            team = game[side]
            name = team["name"]
            if name == "TBD":
                continue
            if name not in teams:
                teams[name] = {
                    "name": name,
                    "seed": team["seed"],
                    "eliminated": False,
                    "wins": 0,
                    "region": game.get("region", ""),
                }
            # If game is final and this team lost, mark eliminated
            if game["status"] == "final" and not team.get("winner", False):
                teams[name]["eliminated"] = True
            if game["status"] == "final" and team.get("winner", False):
                teams[name]["wins"] = teams[name].get("wins", 0) + 1

    return {
        "teams": list(teams.values()),
        "rounds": rounds,
        "regions": regions,
        "all_games": games,
    }


def load_cached_data(gender):
    """Load previously cached tournament data."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{gender}_bracket.json")
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            return json.load(f)
    return None


def save_cached_data(gender, data):
    """Cache tournament data for fallback use."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{gender}_bracket.json")
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2, default=str)


def fetch_tournament_data(gender):
    """Fetch complete tournament data, trying NCAA API first, then SportRadar.

    Args:
        gender: 'men' or 'women'

    Returns:
        dict with bracket_state, todays_games, last_results
    """
    now = datetime.now()
    today = now.strftime("%Y/%m/%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y/%m/%d")

    all_games = []

    # Try NCAA API first - fetch today and yesterday
    try:
        todays_raw = fetch_ncaa_scoreboard(gender, today)
        yesterdays_raw = fetch_ncaa_scoreboard(gender, yesterday)

        # Also try fetching a wider range for bracket state
        for days_back in range(2, 21):
            date = (now - timedelta(days=days_back)).strftime("%Y/%m/%d")
            try:
                older = fetch_ncaa_scoreboard(gender, date)
                if older:
                    all_games.extend(_parse_ncaa_games(older))
                time.sleep(0.25)  # respect rate limit
            except Exception:
                break

        if yesterdays_raw:
            all_games.extend(_parse_ncaa_games(yesterdays_raw))
        if todays_raw:
            all_games.extend(_parse_ncaa_games(todays_raw))

        if all_games:
            bracket = build_bracket_state(all_games)
            todays_games = _parse_ncaa_games(todays_raw) if todays_raw else []
            last_results = [g for g in _parse_ncaa_games(yesterdays_raw or []) if g["status"] == "final"]

            result = {
                "bracket_state": bracket,
                "todays_games": todays_games,
                "last_results": last_results,
                "source": "ncaa-api",
                "updated": now.isoformat(),
            }
            save_cached_data(gender, result)
            return result
    except Exception:
        pass

    # Fallback to SportRadar
    try:
        sr_data = fetch_sportradar_bracket(gender)
        if sr_data:
            parsed = _parse_sportradar_bracket(sr_data)
            bracket = build_bracket_state(parsed["games"])

            todays_games = [
                g for g in parsed["games"]
                if g["status"] == "pre" and _is_today(g.get("start_time", ""))
            ]
            last_results = [
                g for g in parsed["games"]
                if g["status"] == "final" and _is_yesterday_or_today(g.get("start_time", ""))
            ]

            result = {
                "bracket_state": bracket,
                "todays_games": todays_games,
                "last_results": last_results,
                "source": "sportradar",
                "updated": now.isoformat(),
            }
            save_cached_data(gender, result)
            return result
    except Exception:
        pass

    # Last resort: cached data
    cached = load_cached_data(gender)
    if cached:
        cached["source"] = "cache"
        cached["stale"] = True
        return cached

    # No data at all - return empty structure
    return {
        "bracket_state": {"teams": [], "rounds": {}, "regions": {}, "all_games": []},
        "todays_games": [],
        "last_results": [],
        "source": "none",
        "updated": now.isoformat(),
        "stale": True,
    }


def _is_today(dt_str):
    """Check if a datetime string is today."""
    try:
        if "T" in str(dt_str):
            dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
            return dt.date() == datetime.now().date()
    except Exception:
        pass
    return False


def _is_yesterday_or_today(dt_str):
    """Check if a datetime string is yesterday or today."""
    try:
        if "T" in str(dt_str):
            dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)
            return dt.date() in (today, yesterday)
    except Exception:
        pass
    return False


def generate_sample_data(gender):
    """Generate sample tournament data for testing/demo purposes."""
    # Sample teams for a realistic-looking bracket
    if gender == "men":
        sample_teams = {
            "South": [
                ("Houston", 1), ("Auburn", 2), ("Michigan St", 3), ("Arizona", 4),
                ("Clemson", 5), ("Purdue", 6), ("Dayton", 7), ("Ole Miss", 8),
                ("Memphis", 9), ("Colorado St", 10), ("Drake", 11), ("UC San Diego", 12),
                ("Yale", 13), ("Lipscomb", 14), ("Omaha", 15), ("SIU Edwardsville", 16),
            ],
            "East": [
                ("Duke", 1), ("Alabama", 2), ("Wisconsin", 3), ("Texas Tech", 4),
                ("Oregon", 5), ("BYU", 6), ("St. Mary's", 7), ("UConn", 8),
                ("Baylor", 9), ("Vanderbilt", 10), ("VCU", 11), ("Liberty", 12),
                ("Vermont", 13), ("Troy", 14), ("Robert Morris", 15), ("American", 16),
            ],
            "Midwest": [
                ("Florida", 1), ("St. John's", 2), ("Texas A&M", 3), ("Maryland", 4),
                ("Marquette", 5), ("Illinois", 6), ("UCLA", 7), ("Gonzaga", 8),
                ("Arkansas", 9), ("New Mexico", 10), ("San Diego St", 11), ("UC Irvine", 12),
                ("High Point", 13), ("Grand Canyon", 14), ("Montana", 15), ("Norfolk St", 16),
            ],
            "West": [
                ("Tennessee", 1), ("Iowa St", 2), ("Kentucky", 3), ("Creighton", 4),
                ("Michigan", 5), ("Missouri", 6), ("Kansas", 7), ("Louisville", 8),
                ("Georgia", 9), ("Texas", 10), ("Xavier", 11), ("McNeese", 12),
                ("North Carolina", 13), ("Akron", 14), ("Wofford", 15), ("SIUE", 16),
            ],
        }
    else:
        sample_teams = {
            "Albany 1": [
                ("South Carolina", 1), ("UCLA", 2), ("LSU", 3), ("Oklahoma", 4),
                ("Duke", 5), ("West Virginia", 6), ("Iowa St", 7), ("Maryland", 8),
                ("Louisville", 9), ("Saint Louis", 10), ("Columbia", 11), ("Green Bay", 12),
                ("SE Louisiana", 13), ("UT Martin", 14), ("Army", 15), ("Merrimack", 16),
            ],
            "Albany 2": [
                ("Texas", 1), ("NC State", 2), ("Notre Dame", 3), ("Nebraska", 4),
                ("Georgia Tech", 5), ("Mississippi St", 6), ("Ole Miss", 7), ("Gonzaga", 8),
                ("Michigan", 9), ("Marquette", 10), ("UNLV", 11), ("Villanova", 12),
                ("Illinois St", 13), ("E Washington", 14), ("Sacred Heart", 15), ("Grambling", 16),
            ],
            "Portland 3": [
                ("USC", 1), ("UConn", 2), ("Kansas St", 3), ("Baylor", 4),
                ("Tennessee", 5), ("Ohio St", 6), ("North Carolina", 7), ("Michigan St", 8),
                ("Florida St", 9), ("Alabama", 10), ("FGCU", 11), ("Dayton", 12),
                ("IUPUI", 13), ("S Dakota St", 14), ("Stonehill", 15), ("Southern", 16),
            ],
            "Portland 4": [
                ("Stanford", 1), ("Iowa", 2), ("Oregon", 3), ("Indiana", 4),
                ("Virginia Tech", 5), ("TCU", 6), ("Creighton", 7), ("Florida", 8),
                ("Arizona", 9), ("Purdue", 10), ("Middle Tenn", 11), ("Toledo", 12),
                ("Portland", 13), ("Fairfield", 14), ("SF Austin", 15), ("Norfolk St", 16),
            ],
        }

    all_games = []
    all_teams = []

    for region, teams in sample_teams.items():
        for name, seed in teams:
            all_teams.append({
                "name": name,
                "seed": seed,
                "region": region,
                "eliminated": False,
                "wins": 0,
            })

        # Generate Round of 64 matchups (1v16, 8v9, 5v12, 4v13, 6v11, 3v14, 7v10, 2v15)
        matchup_order = [(0, 15), (7, 8), (4, 11), (3, 12), (5, 10), (2, 13), (6, 9), (1, 14)]
        for i, (a, b) in enumerate(matchup_order):
            team_a = teams[a]
            team_b = teams[b]
            # For sample data, higher seed wins (lower number)
            a_wins = team_a[1] < team_b[1]
            all_games.append({
                "game_id": f"{gender}_{region}_r64_{i}",
                "status": "final",
                "start_time": "",
                "network": "CBS" if i % 4 == 0 else "TBS" if i % 4 == 1 else "TNT" if i % 4 == 2 else "truTV",
                "round": "Round of 64",
                "region": region,
                "home": {
                    "name": team_a[0],
                    "seed": team_a[1],
                    "score": 75 + (5 if a_wins else -3),
                    "winner": a_wins,
                },
                "away": {
                    "name": team_b[0],
                    "seed": team_b[1],
                    "score": 75 + (-3 if a_wins else 5),
                    "winner": not a_wins,
                },
            })

    # Mark eliminated teams
    for game in all_games:
        if game["status"] == "final":
            loser = game["away"] if game["home"]["winner"] else game["home"]
            for team in all_teams:
                if team["name"] == loser["name"]:
                    team["eliminated"] = True

    # 8 upcoming games for today (2 per region, Round of 32)
    todays_games = []
    regions_list = list(sample_teams.keys())
    game_times = [
        ("12:10 PM ET", "CBS"), ("2:40 PM ET", "TBS"),
        ("5:15 PM ET", "TNT"), ("6:45 PM ET", "truTV"),
        ("7:10 PM ET", "CBS"), ("7:45 PM ET", "TBS"),
        ("9:40 PM ET", "TNT"), ("9:55 PM ET", "truTV"),
    ]
    game_num = 0
    for r in regions_list:
        teams = sample_teams[r]
        # Game 1: 1-seed vs 8-seed
        time_str, network = game_times[game_num]
        todays_games.append({
            "game_id": f"{gender}_today_{game_num + 1}",
            "status": "pre",
            "start_time": time_str,
            "network": network,
            "round": "Round of 32",
            "region": r,
            "home": {"name": teams[0][0], "seed": teams[0][1], "score": "", "winner": False},
            "away": {"name": teams[7][0], "seed": teams[7][1], "score": "", "winner": False},
        })
        game_num += 1
        # Game 2: 2-seed vs 7-seed
        time_str, network = game_times[game_num]
        todays_games.append({
            "game_id": f"{gender}_today_{game_num + 1}",
            "status": "pre",
            "start_time": time_str,
            "network": network,
            "round": "Round of 32",
            "region": r,
            "home": {"name": teams[1][0], "seed": teams[1][1], "score": "", "winner": False},
            "away": {"name": teams[6][0], "seed": teams[6][1], "score": "", "winner": False},
        })
        game_num += 1

    # Last night's results (8 games - last 2 from each region)
    last_results = all_games[-8:]

    bracket_state = build_bracket_state(all_games)
    bracket_state["teams"] = all_teams

    return {
        "bracket_state": bracket_state,
        "todays_games": todays_games,
        "last_results": last_results,
        "source": "sample",
        "updated": datetime.now().isoformat(),
    }
