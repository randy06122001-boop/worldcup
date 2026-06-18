#!/usr/bin/env python3
"""
World Cup Game Predictor CLI - v3.1 (Live Update)
Added: Real groups, live standings, resume feature, champion predictor.
"""
import random
import math
import sys
import time
import json
import difflib
import os
import argparse
import datetime
import copy
from typing import Dict, Any, Tuple, Optional, List

# ─── Terminal Colors ────────────────────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
CYAN    = "\033[36m"
RED     = "\033[31m"
MAGENTA = "\033[35m"
BG_BLUE = "\033[44m"
BG_GREEN= "\033[42m"
WHITE   = "\033[37m"
DIM     = "\033[2m"

VERSION = "3.1"

# ─── Load & Validate Data ──────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def load_json(filename: str) -> Dict:
    path = os.path.join(SCRIPT_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"{RED}ERROR: Could not find '{filename}'.{RESET}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"{RED}ERROR: '{filename}' is not valid JSON: {e}{RESET}")
        sys.exit(1)

def load_json_safe(filename: str) -> Dict:
    path = os.path.join(SCRIPT_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def validate_teams(teams: Dict) -> None:
    required = {"att", "def", "code", "wc_exp", "default_tactic",
                "last_10", "altitude_comfort", "heat_tolerance"}
    for name, data in teams.items():
        missing = required - set(data.keys())
        if missing:
            print(f"{YELLOW}WARNING: Team '{name}' is missing fields: {missing}{RESET}")

TEAMS  : Dict[str, Any] = load_json("teams.json")
VENUES : Dict[str, Any] = load_json("venues.json")
GROUPS : Dict[str, List[str]] = load_json_safe("groups.json")
STATE  : Dict[str, Any] = load_json_safe("tournament_state.json")

validate_teams(TEAMS)

TACTICS: Dict[str, Dict] = {
    "Neutral":      {"att_mod": 1.00, "def_mod": 1.00},
    "Attacking":    {"att_mod": 1.15, "def_mod": 0.90},
    "Defensive":    {"att_mod": 0.85, "def_mod": 1.15},
    "Gegenpressing":{"att_mod": 1.10, "def_mod": 1.05},
}

# ─── Venue Condition Engine ─────────────────────────────────────────────────────

def get_roof_heat_reduction(roof: str) -> float:
    return {"dome": 1.0, "retractable": 0.70, "partial": 0.30, "open": 0.0}.get(roof, 0.0)

def get_venue_modifier(team: str, venue_key: str, is_knockout: bool, is_extra_time: bool = False) -> float:
    if venue_key not in VENUES:
        return 1.0

    venue = VENUES[venue_key]
    data  = TEAMS[team]
    mod   = 1.0
    fatigue = 2.0 if is_extra_time else 1.0

    alt_m = venue["altitude_m"]
    if alt_m > 1000:
        raw_penalty = min(0.10, (alt_m - 1000) / 12000)
        comfort = data.get("altitude_comfort", 0.10)
        altitude_penalty = raw_penalty * (1.0 - comfort) * fatigue
        mod -= altitude_penalty

    heat  = venue["heat_index"]
    humid = venue["humidity_index"]
    roof_reduction = get_roof_heat_reduction(venue.get("roof", "open"))
    effective_heat  = heat  * (1.0 - roof_reduction)
    effective_humid = humid * (1.0 - roof_reduction)

    if effective_heat > 0.15 or effective_humid > 0.20:
        raw_drain = ((effective_heat + effective_humid) / 2.0) * 0.07
        tolerance = data.get("heat_tolerance", 0.30)
        heat_drain = raw_drain * (1.0 - tolerance) * fatigue
        mod -= heat_drain

    home_country = data.get("home_venue_country")
    if home_country and home_country == venue.get("country"):
        mod += 0.04

    return max(0.75, round(mod, 4))


# ─── Form & Trend Engine ───────────────────────────────────────────────────────

def calculate_trend_factor(results: list) -> Tuple[str, float, float]:
    weights = [1.0, 1.0, 1.2, 1.2, 1.4, 1.4, 1.6, 1.6, 2.0, 2.0]
    total_w = sum(weights)
    score   = sum(
        (1.0 if r == "W" else 0.5 if r == "D" else 0.0) * w
        for r, w in zip(results[-10:], weights[-len(results):])
    )
    idx = score / total_w
    modifier = 1.0 + (idx - 0.50) * 0.20

    if idx > 0.60: trend = "UP"
    elif idx < 0.40: trend = "DOWN"
    else: trend = "STABLE"

    return trend, round(idx * 100, 1), round(modifier, 4)

def poisson_sample(lam: float) -> int:
    if lam <= 0: return 0
    if lam > 20: return max(0, round(random.gauss(lam, math.sqrt(lam))))
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= random.random()
        if p <= L:
            return k - 1

def calculate_expected_goals(
    team_a: str, team_b: str,
    tactics_a: str, tactics_b: str,
    venue_key: str = "New York",
    is_knockout: bool = False,
    is_extra_time: bool = False,
    red_card_a: bool = False,
    red_card_b: bool = False
) -> Tuple[float, float]:
    base = 1.15 if is_knockout else 1.35
    avg_rating = 80.0

    _, _, trend_a = calculate_trend_factor(TEAMS[team_a]["last_10"])
    _, _, trend_b = calculate_trend_factor(TEAMS[team_b]["last_10"])

    exp_a = 1.0 + (TEAMS[team_a]["wc_exp"] / 100.0) * 0.05 if is_knockout else 1.0
    exp_b = 1.0 + (TEAMS[team_b]["wc_exp"] / 100.0) * 0.05 if is_knockout else 1.0

    venue_a = get_venue_modifier(team_a, venue_key, is_knockout, is_extra_time)
    venue_b = get_venue_modifier(team_b, venue_key, is_knockout, is_extra_time)

    rc_att_a, rc_def_a = (0.85, 0.90) if red_card_a else (1.0, 1.0)
    rc_att_b, rc_def_b = (0.85, 0.90) if red_card_b else (1.0, 1.0)

    att_a = TEAMS[team_a]["att"] * trend_a * TACTICS[tactics_a]["att_mod"] * exp_a * venue_a * rc_att_a
    att_b = TEAMS[team_b]["att"] * trend_b * TACTICS[tactics_b]["att_mod"] * exp_b * venue_b * rc_att_b

    def_a = TEAMS[team_a]["def"] * trend_a * TACTICS[tactics_a]["def_mod"] * exp_a * rc_def_a
    def_b = TEAMS[team_b]["def"] * trend_b * TACTICS[tactics_b]["def_mod"] * exp_b * rc_def_b

    lam_a = base * (att_a / avg_rating) * (avg_rating / def_b)
    lam_b = base * (att_b / avg_rating) * (avg_rating / def_a)

    return round(lam_a, 4), round(lam_b, 4)

def simulate_penalties(team_a: str, team_b: str) -> Tuple[int, int]:
    rate_a = 0.65 + (TEAMS[team_a]["wc_exp"] / 100.0) * 0.15
    rate_b = 0.65 + (TEAMS[team_b]["wc_exp"] / 100.0) * 0.15

    score_a = score_b = 0
    max_kicks = 5

    for kick in range(1, max_kicks + 1):
        if random.random() < rate_a: score_a += 1
        if score_a > score_b + (max_kicks - kick): return score_a, score_b
        if random.random() < rate_b: score_b += 1
        if score_b > score_a + (max_kicks - kick): return score_a, score_b

    while score_a == score_b:
        if random.random() < rate_a: score_a += 1
        if random.random() < rate_b: score_b += 1

    return score_a, score_b

def resolve_tactic(team: str, tactic: str) -> str:
    return TEAMS[team]["default_tactic"] if tactic == "Default" else tactic

def get_match_winner(team_a: str, team_b: str, result: Dict) -> str:
    if result["score_a"] > result["score_b"]: return team_a
    if result["score_b"] > result["score_a"]: return team_b
    return team_a if result["pens_a"] > result["pens_b"] else team_b

def simulate_match(
    team_a: str, team_b: str,
    is_knockout: bool = False,
    tactics_a: str = "Default",
    tactics_b: str = "Default",
    venue_key: str = "New York",
    red_card_a: bool = False,
    red_card_b: bool = False
) -> Dict:
    t_a = resolve_tactic(team_a, tactics_a)
    t_b = resolve_tactic(team_b, tactics_b)

    lam_a, lam_b = calculate_expected_goals(
        team_a, team_b, t_a, t_b, venue_key, is_knockout,
        is_extra_time=False, red_card_a=red_card_a, red_card_b=red_card_b
    )

    goals_a_90 = poisson_sample(lam_a)
    goals_b_90 = poisson_sample(lam_b)

    goals_a = goals_a_90
    goals_b = goals_b_90
    extra_time = penalties = False
    pens_a = pens_b = 0

    if goals_a == goals_b and is_knockout:
        extra_time = True
        lam_a_et, lam_b_et = calculate_expected_goals(
            team_a, team_b, t_a, t_b, venue_key, is_knockout,
            is_extra_time=True, red_card_a=red_card_a, red_card_b=red_card_b
        )
        goals_a += poisson_sample(lam_a_et * 0.33)
        goals_b += poisson_sample(lam_b_et * 0.33)
        if goals_a == goals_b:
            penalties = True
            pens_a, pens_b = simulate_penalties(team_a, team_b)

    return {
        "score_a_90": goals_a_90, "score_b_90": goals_b_90,
        "score_a": goals_a, "score_b": goals_b,
        "extra_time": extra_time, "penalties": penalties,
        "pens_a": pens_a, "pens_b": pens_b,
        "tactic_a": t_a, "tactic_b": t_b,
        "lam_a": lam_a, "lam_b": lam_b,
    }

def confidence_interval(p: float, n: int, z: float = 1.96) -> float:
    if n <= 0: return 0.0
    return z * math.sqrt((p * (1 - p)) / n) * 100

def run_monte_carlo(team_a: str, team_b: str, runs: int = 10000, is_knockout: bool = False, venue_key: str = "New York", show_progress: bool = True, red_card_a: bool = False, red_card_b: bool = False) -> Dict:
    t_a, t_b = resolve_tactic(team_a, "Default"), resolve_tactic(team_b, "Default")
    a_wins = b_wins = draws = a_wins_90 = b_wins_90 = draws_90 = a_wins_aet = b_wins_aet = a_wins_pen = b_wins_pen = total_goals_a = total_goals_b = 0
    scores: Dict[str, int] = {}
    bar_width = 40
    for i in range(runs):
        if show_progress and i % 500 == 0:
            pct = i / runs
            done = int(pct * bar_width)
            print(f"\r  {YELLOW}[{'=' * done}{' ' * (bar_width - done)}]{RESET} {int(pct*100)}%", end="", flush=True)

        res = simulate_match(team_a, team_b, is_knockout=is_knockout, tactics_a=t_a, tactics_b=t_b, venue_key=venue_key, red_card_a=red_card_a, red_card_b=red_card_b)
        sa, sb = res["score_a"], res["score_b"]
        total_goals_a += sa; total_goals_b += sb

        if is_knockout:
            if not res["extra_time"]:
                if sa > sb: a_wins_90 += 1; a_wins += 1
                else: b_wins_90 += 1; b_wins += 1
            else:
                draws_90 += 1
                if not res["penalties"]:
                    if sa > sb: a_wins_aet += 1; a_wins += 1
                    else: b_wins_aet += 1; b_wins += 1
                else:
                    if res["pens_a"] > res["pens_b"]: a_wins_pen += 1; a_wins += 1
                    else: b_wins_pen += 1; b_wins += 1
        else:
            if sa > sb: a_wins += 1
            elif sb > sa: b_wins += 1
            else: draws += 1
        scores[f"{sa}-{sb}"] = scores.get(f"{sa}-{sb}", 0) + 1

    if show_progress: print(f"\r  {GREEN}[{'=' * bar_width}]{RESET} 100%")
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    a_pct, b_pct, d_pct = a_wins / runs, b_wins / runs, draws / runs

    ret = {
        "a_win_pct": round(a_pct * 100, 2), "b_win_pct": round(b_pct * 100, 2), "draw_pct": round(d_pct * 100, 2),
        "a_win_ci": round(confidence_interval(a_pct, runs), 2), "b_win_ci": round(confidence_interval(b_pct, runs), 2), "draw_ci": round(confidence_interval(d_pct, runs), 2),
        "avg_goals_a": round(total_goals_a / runs, 2), "avg_goals_b": round(total_goals_b / runs, 2),
        "top_scores": sorted_scores[:7], "total_runs": runs, "tactic_a": t_a, "tactic_b": t_b,
    }
    if is_knockout:
        ret.update({"a_win_90_pct": round((a_wins_90 / runs) * 100, 2), "b_win_90_pct": round((b_wins_90 / runs) * 100, 2), "draw_90_pct": round((draws_90 / runs) * 100, 2), "a_win_aet_pct": round((a_wins_aet / runs) * 100, 2), "b_win_aet_pct": round((b_wins_aet / runs) * 100, 2), "a_win_pen_pct": round((a_wins_pen / runs) * 100, 2), "b_win_pen_pct": round((b_wins_pen / runs) * 100, 2)})
    return ret

def create_groups(teams_list: List[str], num_groups: int = 12) -> List[List[str]]:
    if GROUPS:
        return [GROUPS[lbl] for lbl in sorted(GROUPS.keys())]
    ranked = sorted(teams_list, key=lambda t: ((TEAMS[t]["att"] + TEAMS[t]["def"]) / 2.0) * (1.0 + TEAMS[t]["wc_exp"] / 500.0), reverse=True)
    per_group = len(ranked) // num_groups
    groups: List[List[str]] = [[] for _ in range(num_groups)]
    for pot_idx in range(per_group):
        pot = ranked[pot_idx * num_groups : (pot_idx + 1) * num_groups]
        random.shuffle(pot)
        if pot_idx % 2 == 1: pot.reverse()
        for g_idx, team in enumerate(pot): groups[g_idx].append(team)
    return groups

def simulate_group(group: List[str], group_label: str, venue_key: str, resume: bool = False) -> List[Dict]:
    standings = {}
    if resume and "standings" in STATE and group_label in STATE["standings"]:
        standings = copy.deepcopy(STATE["standings"][group_label])
        for t in group:
            if t not in standings:
                standings[t] = {"team": t, "pts": 0, "gf": 0, "ga": 0, "gd": 0, "w": 0, "d": 0, "l": 0, "played": 0}
            else:
                standings[t]["team"] = t
    else:
        for t in group:
            standings[t] = {"team": t, "pts": 0, "gf": 0, "ga": 0, "gd": 0, "w": 0, "d": 0, "l": 0, "played": 0}

    played_list = STATE.get("played_matches", []) if resume else []
    def match_played(t1, t2):
        for m in played_list:
            if (m["home"] == t1 and m["away"] == t2) or (m["home"] == t2 and m["away"] == t1):
                return True
        return False

    matches = [(group[i], group[j]) for i in range(len(group)) for j in range(i + 1, len(group))]
    for t1, t2 in matches:
        if resume and match_played(t1, t2):
            continue
        res = simulate_match(t1, t2, is_knockout=False, venue_key=venue_key)
        g1, g2 = res["score_a"], res["score_b"]
        standings[t1]["gf"] += g1; standings[t1]["ga"] += g2; standings[t1]["played"] += 1
        standings[t2]["gf"] += g2; standings[t2]["ga"] += g1; standings[t2]["played"] += 1
        if g1 > g2: standings[t1]["pts"] += 3; standings[t1]["w"] += 1; standings[t2]["l"] += 1
        elif g2 > g1: standings[t2]["pts"] += 3; standings[t2]["w"] += 1; standings[t1]["l"] += 1
        else: standings[t1]["pts"] += 1; standings[t1]["d"] += 1; standings[t2]["pts"] += 1; standings[t2]["d"] += 1

    for t in standings: standings[t]["gd"] = standings[t]["gf"] - standings[t]["ga"]
    return sorted(standings.values(), key=lambda x: (x["pts"], x["gd"], x["gf"]), reverse=True)

def display_group_table(group_label: str, standings: List[Dict]) -> None:
    print(f"\n  {BOLD}{CYAN}Group {group_label}{RESET}")
    print(f"  {'Team':<16}{'P':>3}{'W':>4}{'D':>4}{'L':>4}{'GF':>5}{'GA':>5}{'GD':>5}{'Pts':>5}")
    print(f"  {'-' * 51}")
    for i, s in enumerate(standings):
        col = GREEN if i < 2 else YELLOW if i == 2 else RED
        print(f"  {col}{s['team']:<16}{s['played']:>3}{s['w']:>4}{s['d']:>4}{s['l']:>4}{s['gf']:>5}{s['ga']:>5}{s['gd']:>+5}{s['pts']:>5}{RESET}")

def run_group_stage(venue_key: str, resume: bool = False, quiet: bool = False) -> List[str]:
    all_teams = sorted(TEAMS.keys())
    groups = create_groups(all_teams[:48])
    group_labels = sorted(GROUPS.keys()) if GROUPS else [chr(65 + i) for i in range(len(groups))]

    all_standings, third_place = [], []
    if not quiet:
        print(f"\n{BOLD}{'='*60}{RESET}\n{BOLD}  GROUP STAGE RESULTS{RESET}\n{BOLD}{'='*60}{RESET}")

    for idx, (group, label) in enumerate(zip(groups, group_labels)):
        standings = simulate_group(group, label, venue_key, resume)
        all_standings.append(standings)
        if not quiet: display_group_table(label, standings)
        third_place.append({**standings[2], "group": label})

    qualified = []
    for standings in all_standings:
        qualified.extend([standings[0]["team"], standings[1]["team"]])

    third_sorted = sorted(third_place, key=lambda x: (x["pts"], x["gd"], x["gf"]), reverse=True)
    if not quiet:
        print(f"\n{BOLD}{CYAN}--- Best Third-Place Teams ---{RESET}")
        print(f"  {'Team':<16}{'Group':>6}{'Pts':>5}{'GD':>5}{'GF':>5}{'Status':>10}")
        print(f"  {'-' * 47}")
        for i, t in enumerate(third_sorted):
            status = f"{GREEN}ADVANCE{RESET}" if i < 8 else f"{RED}OUT{RESET}"
            print(f"  {t['team']:<16}{t['group']:>6}{t['pts']:>5}{t['gd']:>+5}{t['gf']:>5}  {status}")
            if i < 8: qualified.append(t["team"])
        print(f"\n{BOLD}{GREEN}{len(qualified)} teams advance to the Round of 32!{RESET}")
    else:
        for i, t in enumerate(third_sorted):
            if i < 8: qualified.append(t["team"])
            
    return qualified

def run_knockout_silent(qualified: List[str], venue_key: str) -> str:
    current_round = qualified[:]
    while len(current_round) > 1:
        next_round = []
        for i in range(0, len(current_round), 2):
            t1, t2 = current_round[i], current_round[i + 1]
            res = simulate_match(t1, t2, is_knockout=True, venue_key=venue_key)
            next_round.append(get_match_winner(t1, t2, res))
        current_round = next_round
    return current_round[0]

def run_knockout_from_qualified(qualified: List[str], venue_key: str) -> None:
    round_names = {32: "Round of 32", 16: "Round of 16", 8: "Quarter-Finals", 4: "Semi-Finals", 2: "Grand Final"}
    current_round = qualified[:]
    losers_sf = []
    while len(current_round) > 1:
        n = len(current_round)
        round_name = round_names.get(n, f"Round of {n}")
        input(f"\n{YELLOW}Press Enter for {round_name}...{RESET}")
        print(f"\n{BOLD}{'='*60}{RESET}\n{BOLD}  {round_name.upper()} -- {VENUES[venue_key]['city']}{RESET}\n{BOLD}{'='*60}{RESET}")
        next_round = []
        for i in range(0, n, 2):
            t1, t2 = current_round[i], current_round[i + 1]
            print(f"\n  Match {i//2 + 1}: {BOLD}{t1}{RESET} vs {BOLD}{t2}{RESET}")
            mc = run_monte_carlo(t1, t2, runs=1000, is_knockout=True, venue_key=venue_key, show_progress=False)
            print(f"  Odds  {CYAN}{t1}{RESET} {mc['a_win_pct']:.1f}%  |  {MAGENTA}{t2}{RESET} {mc['b_win_pct']:.1f}%")
            res = simulate_match(t1, t2, is_knockout=True, venue_key=venue_key)
            winner = get_match_winner(t1, t2, res)
            loser = t2 if winner == t1 else t1
            score = f"{t1} {res['score_a']} - {res['score_b']} {t2}"
            if res["extra_time"] and not res["penalties"]: score += " (AET)"
            if res["penalties"]: score += f" (Pens {res['pens_a']}-{res['pens_b']})"
            print(f"    {score}\n    {GREEN}{winner} advances!{RESET}")
            next_round.append(winner)
            if n == 4: losers_sf.append(loser)
            time.sleep(0.15)
        current_round = next_round
        if n == 4 and len(losers_sf) == 2:
            input(f"\n{YELLOW}Press Enter for Third Place Playoff...{RESET}")
            t1, t2 = losers_sf[0], losers_sf[1]
            print(f"\n{BOLD}THIRD PLACE PLAYOFF{RESET}\n{'='*60}\n  {BOLD}{t1}{RESET} vs {BOLD}{t2}{RESET}")
            res = simulate_match(t1, t2, is_knockout=True, venue_key=venue_key)
            winner_3 = get_match_winner(t1, t2, res)
            score = f"{t1} {res['score_a']} - {res['score_b']} {t2}"
            print(f"    {score}\n    {YELLOW}{winner_3} finishes THIRD!{RESET}")
    print(f"\n{BOLD}{BG_BLUE}{'='*60}{RESET}\n{BOLD}{YELLOW}  WORLD CUP 2026 CHAMPION: {current_round[0]}!{RESET}\n{BOLD}{BG_BLUE}{'='*60}{RESET}")

def predict_champion(venue_key: str, resume: bool = False, runs: int = 5000):
    print(f"\n{YELLOW}Running {runs} full tournament simulations to predict champion...{RESET}")
    champion_counts = {}
    bar_width = 40
    for i in range(runs):
        if i % max(1, runs // 100) == 0:
            pct = i / runs
            done = int(pct * bar_width)
            print(f"\r  {YELLOW}[{'=' * done}{' ' * (bar_width - done)}]{RESET} {int(pct*100)}%", end="", flush=True)
        qualified = run_group_stage(venue_key, resume=resume, quiet=True)
        champ = run_knockout_silent(qualified, venue_key)
        champion_counts[champ] = champion_counts.get(champ, 0) + 1
    print(f"\r  {GREEN}[{'=' * bar_width}]{RESET} 100%")
    sorted_champs = sorted(champion_counts.items(), key=lambda x: x[1], reverse=True)
    print(f"\n{BOLD}{BG_BLUE}{' '*10}CHAMPION PROBABILITIES{' '*10}{RESET}\n")
    for i, (team, count) in enumerate(sorted_champs[:20], 1):
        print(f"  {i:>2}. {team:<20} {(count / runs * 100):>5.1f}%")

def print_header(title: str) -> None:
    width = len(title) + 4
    print(f"\n{BOLD}{BG_BLUE}{' ' * max(0, (80 - width) // 2)}{title:^{width}}{RESET}\n")

def fuzzy_find_team(name: str) -> Optional[str]:
    exact = [t for t in TEAMS if t.lower() == name.lower()]
    if exact: return exact[0]
    code_match = [t for t in TEAMS if TEAMS[t]["code"].lower() == name.lower()]
    if code_match: return code_match[0]
    close = difflib.get_close_matches(name, TEAMS.keys(), n=1, cutoff=0.55)
    return close[0] if close else None

def main() -> None:
    print(f"\n{BOLD}{GREEN}{'=' * 58}{RESET}")
    print(f"{BOLD}{GREEN}   WORLD CUP 2026 GAME PREDICTOR -- CLI v{VERSION}{RESET}")
    print(f"{BOLD}{GREEN}{'=' * 58}{RESET}")
    print(f"  Teams  : {BOLD}{len(TEAMS)}{RESET} nations  |  Venues: {BOLD}{len(VENUES)}{RESET} stadiums")
    print(f"  New    : Live tournament resume, champion predictor")
    print(f"{BOLD}{GREEN}{'=' * 58}{RESET}\n")

    while True:
        print(f"\n{BOLD}MAIN MENU{RESET}")
        print(f"  1. {CYAN}Simulate Single Match{RESET}")
        print(f"  2. {CYAN}Run Knockout Bracket (8 Teams){RESET}")
        print(f"  3. {CYAN}Full Group Stage + Knockout (48 Teams){RESET}")
        print(f"  4. {CYAN}Resume Current Tournament (Live Update){RESET}")
        print(f"  5. {MAGENTA}Predict Tournament Champion (Monte Carlo){RESET}")
        print(f"  6. {RED}Exit{RESET}")

        choice = input(f"\n{BOLD}> {RESET}").strip()

        if choice == "1":
            team_a = fuzzy_find_team(input("Home Team: ").strip())
            team_b = fuzzy_find_team(input("Away Team: ").strip())
            if not team_a or not team_b:
                print(f"{RED}Team not found.{RESET}"); continue
            res = simulate_match(team_a, team_b)
            print(f"Result: {res['score_a']} - {res['score_b']}")
        elif choice == "2":
            venue_key = "New York"
            ranked = sorted(TEAMS.keys(), key=lambda t: (TEAMS[t]["att"] + TEAMS[t]["def"]) / 2.0, reverse=True)
            run_knockout_from_qualified(list(ranked[:8]), venue_key)
        elif choice == "3":
            venue_key = "New York"
            run_knockout_from_qualified(run_group_stage(venue_key), venue_key)
        elif choice == "4":
            print_header("RESUMING TOURNAMENT STAGE")
            venue_key = "New York"
            run_knockout_from_qualified(run_group_stage(venue_key, resume=True), venue_key)
        elif choice == "5":
            print_header("CHAMPION PREDICTOR")
            venue_key = "New York"
            resume = input("Resume from current standings? (Y/n): ").strip().lower() != 'n'
            runs = int(input("Number of tournament simulations (default 5000): ").strip() or "5000")
            predict_champion(venue_key, resume=resume, runs=runs)
        elif choice == "6":
            print(f"\n{BOLD}{GREEN}Goodbye!{RESET}\n")
            sys.exit(0)
        else:
            print(f"{RED}Invalid option.{RESET}")

if __name__ == "__main__":
    main()
