#!/usr/bin/env python3
"""
World Cup Game Predictor CLI - v2.1
All v2.0 bugs fixed. Added: team-specific altitude/heat tolerance,
indoor/retractable roof logic, country-specific home boost, JSON validation.
"""
import random
import math
import sys
import time
import json
import difflib
import os
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

# ─── Load & Validate Data ──────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def load_json(filename: str) -> Dict:
    """Load a JSON file from the same directory as the script."""
    path = os.path.join(SCRIPT_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"{RED}ERROR: Could not find '{filename}'. "
              f"Make sure it is in: {SCRIPT_DIR}{RESET}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"{RED}ERROR: '{filename}' is not valid JSON: {e}{RESET}")
        sys.exit(1)


def validate_teams(teams: Dict) -> None:
    """Check every team entry has the required fields."""
    required = {"att", "def", "code", "wc_exp", "default_tactic",
                "last_10", "altitude_comfort", "heat_tolerance"}
    for name, data in teams.items():
        missing = required - set(data.keys())
        if missing:
            print(f"{YELLOW}WARNING: Team '{name}' is missing fields: {missing}{RESET}")
        if len(data.get("last_10", [])) != 10:
            print(f"{YELLOW}WARNING: Team '{name}' last_10 should have exactly 10 entries.{RESET}")


def validate_venues(venues: Dict) -> None:
    """Check every venue entry has the required fields."""
    required = {"city", "country", "altitude_m", "heat_index",
                "humidity_index", "roof", "climate"}
    for name, data in venues.items():
        missing = required - set(data.keys())
        if missing:
            print(f"{YELLOW}WARNING: Venue '{name}' is missing fields: {missing}{RESET}")
        if data.get("roof") not in ("dome", "retractable", "partial", "open"):
            print(f"{YELLOW}WARNING: Venue '{name}' has invalid roof type: {data.get('roof')}{RESET}")


TEAMS  : Dict[str, Any] = load_json("teams.json")
VENUES : Dict[str, Any] = load_json("venues.json")
validate_teams(TEAMS)
validate_venues(VENUES)

TACTICS: Dict[str, Dict] = {
    "Neutral":      {"att_mod": 1.00, "def_mod": 1.00},
    "Attacking":    {"att_mod": 1.15, "def_mod": 0.90},
    "Defensive":    {"att_mod": 0.85, "def_mod": 1.15},
    "Gegenpressing":{"att_mod": 1.10, "def_mod": 1.05},
}

# ─── Venue Condition Engine ─────────────────────────────────────────────────────

def get_roof_heat_reduction(roof: str) -> float:
    """
    How much the roof reduces outdoor heat/humidity effects.
    - dome:        100% reduction (full climate control)
    - retractable:  70% reduction (likely closed in extreme heat, some leakage)
    - partial:      30% reduction (shade canopy, still exposed)
    - open:          0% reduction (full outdoor exposure)
    """
    return {"dome": 1.0, "retractable": 0.70, "partial": 0.30, "open": 0.0}.get(roof, 0.0)


def get_venue_modifier(team: str, venue_key: str, is_knockout: bool) -> float:
    """
    Calculate a compound venue modifier for a team based on:
    - Altitude (scaled by team's altitude_comfort)
    - Heat & Humidity (scaled by team's heat_tolerance, reduced by roof type)
    - Home crowd (only if team's home country matches venue country)
    Returns a multiplier, e.g. 0.95 = 5% performance drain on ATTACK only.
    """
    if venue_key not in VENUES:
        return 1.0

    venue = VENUES[venue_key]
    data  = TEAMS[team]
    mod   = 1.0

    # ── Altitude penalty (team-specific acclimatisation)
    alt_m = venue["altitude_m"]
    if alt_m > 1000:
        raw_penalty = min(0.10, (alt_m - 1000) / 12000)
        comfort = data.get("altitude_comfort", 0.10)
        # High comfort (0.9) → only 10% of the raw penalty applied
        altitude_penalty = raw_penalty * (1.0 - comfort)
        mod -= altitude_penalty

    # ── Heat & Humidity drain (team-specific tolerance, roof-adjusted)
    heat  = venue["heat_index"]
    humid = venue["humidity_index"]
    roof_reduction = get_roof_heat_reduction(venue.get("roof", "open"))

    # Apply roof: reduce the effective outdoor heat/humidity
    effective_heat  = heat  * (1.0 - roof_reduction)
    effective_humid = humid * (1.0 - roof_reduction)

    if effective_heat > 0.15 or effective_humid > 0.20:
        raw_drain = ((effective_heat + effective_humid) / 2.0) * 0.07
        tolerance = data.get("heat_tolerance", 0.30)
        # High tolerance (0.9) → only 10% of the raw drain applied
        heat_drain = raw_drain * (1.0 - tolerance)
        mod -= heat_drain

    # ── Home crowd advantage (country-specific)
    home_country = data.get("home_venue_country")
    if home_country and home_country == venue.get("country"):
        mod += 0.04   # +4% only when playing in their OWN country's venues

    return max(0.82, round(mod, 4))


# ─── Form & Trend Engine ───────────────────────────────────────────────────────

def calculate_trend_factor(results: list) -> Tuple[str, float, float]:
    """
    Weighted moving average over last 10 games (newest = higher weight).
    Returns: (trend_label, win_index_pct, modifier)
    """
    weights = [1.0, 1.0, 1.2, 1.2, 1.4, 1.4, 1.6, 1.6, 2.0, 2.0]
    total_w = sum(weights)
    score   = sum(
        (1.0 if r == "W" else 0.5 if r == "D" else 0.0) * w
        for r, w in zip(results, weights)
    )
    idx = score / total_w

    if idx > 0.65:
        trend    = "UP"
        modifier = 1.0 + (idx - 0.50) * 0.25
    elif idx < 0.35:
        trend    = "DOWN"
        modifier = 1.0 + (idx - 0.50) * 0.25
    else:
        trend    = "STABLE"
        modifier = 1.0

    return trend, round(idx * 100, 1), round(modifier, 4)


# ─── Poisson Sampler ───────────────────────────────────────────────────────────

def poisson_sample(lam: float) -> int:
    """Knuth algorithm with normal approximation fallback for large lambda."""
    if lam <= 0:
        return 0
    if lam > 20:
        return max(0, round(random.gauss(lam, math.sqrt(lam))))
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= random.random()
        if p <= L:
            return k - 1


# ─── Expected Goals Calculator ─────────────────────────────────────────────────

def calculate_expected_goals(
    team_a: str, team_b: str,
    tactics_a: str, tactics_b: str,
    venue_key: str = "New York",
    is_knockout: bool = False
) -> Tuple[float, float]:
    """
    Double Poisson lambda estimation.
    BUG FIX v2.1: Venue drain applied to ATTACK only (not defense).
    BUG FIX v2.1: WC experience only applies in knockout rounds.
    """
    base = 1.15 if is_knockout else 1.35
    avg_rating = 80.0

    _, _, trend_a = calculate_trend_factor(TEAMS[team_a]["last_10"])
    _, _, trend_b = calculate_trend_factor(TEAMS[team_b]["last_10"])

    # WC experience: only buffs knockout composure (v2.1 fix)
    if is_knockout:
        exp_a = 1.0 + (TEAMS[team_a]["wc_exp"] / 100.0) * 0.05
        exp_b = 1.0 + (TEAMS[team_b]["wc_exp"] / 100.0) * 0.05
    else:
        exp_a = 1.0
        exp_b = 1.0

    # Venue environmental modifiers (applied to ATTACK only in v2.1)
    venue_a = get_venue_modifier(team_a, venue_key, is_knockout)
    venue_b = get_venue_modifier(team_b, venue_key, is_knockout)

    # Attack ratings: full modifier chain including venue drain
    att_a = TEAMS[team_a]["att"] * trend_a * TACTICS[tactics_a]["att_mod"] * exp_a * venue_a
    att_b = TEAMS[team_b]["att"] * trend_b * TACTICS[tactics_b]["att_mod"] * exp_b * venue_b

    # Defense ratings: NO venue drain — defense stays solid under harsh conditions
    def_a = TEAMS[team_a]["def"] * trend_a * TACTICS[tactics_a]["def_mod"] * exp_a
    def_b = TEAMS[team_b]["def"] * trend_b * TACTICS[tactics_b]["def_mod"] * exp_b

    lam_a = base * (att_a / avg_rating) * (avg_rating / def_b)
    lam_b = base * (att_b / avg_rating) * (avg_rating / def_a)

    return round(lam_a, 4), round(lam_b, 4)


# ─── Penalty Shootout (Sequential / Realistic) ─────────────────────────────────

def simulate_penalties(team_a: str, team_b: str) -> Tuple[int, int]:
    """Sequential shootout with early exit and WC experience composure."""
    rate_a = 0.70 + (TEAMS[team_a]["wc_exp"] / 100.0) * 0.10
    rate_b = 0.70 + (TEAMS[team_b]["wc_exp"] / 100.0) * 0.10

    score_a = score_b = 0
    max_kicks = 5

    for kick in range(1, max_kicks + 1):
        if random.random() < rate_a:
            score_a += 1
        remaining_b = max_kicks - kick
        if score_a > score_b + remaining_b:
            return score_a, score_b

        if random.random() < rate_b:
            score_b += 1
        remaining_a = max_kicks - kick
        if score_b > score_a + remaining_a:
            return score_a, score_b

    # Sudden death
    while score_a == score_b:
        a_scored = random.random() < rate_a
        b_scored = random.random() < rate_b
        if a_scored:
            score_a += 1
        if b_scored:
            score_b += 1

    return score_a, score_b


# ─── Match Simulation ──────────────────────────────────────────────────────────

def resolve_tactic(team: str, tactic: str) -> str:
    return TEAMS[team]["default_tactic"] if tactic == "Default" else tactic


def get_match_winner(team_a: str, team_b: str, result: Dict) -> str:
    if result["score_a"] > result["score_b"]:
        return team_a
    if result["score_b"] > result["score_a"]:
        return team_b
    return team_a if result["pens_a"] > result["pens_b"] else team_b


def simulate_match(
    team_a: str, team_b: str,
    is_knockout: bool = False,
    tactics_a: str = "Default",
    tactics_b: str = "Default",
    venue_key: str = "New York"
) -> Dict:
    t_a = resolve_tactic(team_a, tactics_a)
    t_b = resolve_tactic(team_b, tactics_b)

    lam_a, lam_b = calculate_expected_goals(team_a, team_b, t_a, t_b, venue_key, is_knockout)

    goals_a = poisson_sample(lam_a)
    goals_b = poisson_sample(lam_b)

    extra_time = penalties = False
    pens_a = pens_b = 0

    if goals_a == goals_b and is_knockout:
        extra_time = True
        goals_a += poisson_sample(lam_a * 0.33)
        goals_b += poisson_sample(lam_b * 0.33)
        if goals_a == goals_b:
            penalties = True
            pens_a, pens_b = simulate_penalties(team_a, team_b)

    return {
        "score_a": goals_a, "score_b": goals_b,
        "extra_time": extra_time, "penalties": penalties,
        "pens_a": pens_a, "pens_b": pens_b,
        "tactic_a": t_a, "tactic_b": t_b,
        "lam_a": lam_a, "lam_b": lam_b,
    }


# ─── Monte Carlo Engine ────────────────────────────────────────────────────────

def run_monte_carlo(
    team_a: str, team_b: str,
    runs: int = 10000,
    is_knockout: bool = False,
    venue_key: str = "New York",
    show_progress: bool = True
) -> Dict:
    t_a = resolve_tactic(team_a, "Default")
    t_b = resolve_tactic(team_b, "Default")

    a_wins = b_wins = draws = 0
    a_wins_90 = b_wins_90 = draws_90 = 0
    a_wins_aet = b_wins_aet = 0
    a_wins_pen = b_wins_pen = 0
    
    scores: Dict[str, int] = {}

    bar_width = 40
    for i in range(runs):
        if show_progress and i % 500 == 0:
            pct  = i / runs
            done = int(pct * bar_width)
            bar  = f"[{'=' * done}{' ' * (bar_width - done)}]"
            print(f"\r  {YELLOW}{bar}{RESET} {int(pct*100)}%", end="", flush=True)

        res = simulate_match(team_a, team_b, is_knockout=is_knockout,
                             tactics_a=t_a, tactics_b=t_b, venue_key=venue_key)
        sa, sb = res["score_a"], res["score_b"]

        if is_knockout:
            if not res["extra_time"]:
                if sa > sb:
                    a_wins_90 += 1; a_wins += 1
                else:
                    b_wins_90 += 1; b_wins += 1
            else:
                draws_90 += 1
                if not res["penalties"]:
                    if sa > sb:
                        a_wins_aet += 1; a_wins += 1
                    else:
                        b_wins_aet += 1; b_wins += 1
                else:
                    if res["pens_a"] > res["pens_b"]:
                        a_wins_pen += 1; a_wins += 1
                    else:
                        b_wins_pen += 1; b_wins += 1
        else:
            if sa > sb:   a_wins += 1
            elif sb > sa: b_wins += 1
            else:         draws  += 1

        scores[f"{sa}-{sb}"] = scores.get(f"{sa}-{sb}", 0) + 1

    if show_progress:
        print(f"\r  {GREEN}[{'=' * bar_width}]{RESET} 100%")

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    ret = {
        "a_win_pct":  round((a_wins / runs) * 100, 2),
        "b_win_pct":  round((b_wins / runs) * 100, 2),
        "draw_pct":   round((draws  / runs) * 100, 2),
        "top_scores": sorted_scores[:7],
        "total_runs": runs,
        "tactic_a": t_a, "tactic_b": t_b,
    }
    
    if is_knockout:
        ret.update({
            "a_win_90_pct": round((a_wins_90 / runs) * 100, 2),
            "b_win_90_pct": round((b_wins_90 / runs) * 100, 2),
            "draw_90_pct": round((draws_90 / runs) * 100, 2),
            "a_win_aet_pct": round((a_wins_aet / runs) * 100, 2),
            "b_win_aet_pct": round((b_wins_aet / runs) * 100, 2),
            "a_win_pen_pct": round((a_wins_pen / runs) * 100, 2),
            "b_win_pen_pct": round((b_wins_pen / runs) * 100, 2),
        })
        
    return ret


# ─── UI Helpers ────────────────────────────────────────────────────────────────

def print_header(title: str) -> None:
    width = len(title) + 4
    pad = max(0, (80 - width) // 2)
    print(f"\n{BOLD}{BG_BLUE}{' ' * pad}{title:^{width}}{RESET}")
    print()


def format_last10(results: list, trend: str) -> str:
    coloured = []
    for r in results:
        if r == "W":   coloured.append(f"{GREEN}W{RESET}")
        elif r == "D": coloured.append(f"{YELLOW}D{RESET}")
        else:          coloured.append(f"{RED}L{RESET}")
    arrow = (f"{GREEN}^UP{RESET}" if trend == "UP"
             else f"{RED}vDN{RESET}" if trend == "DOWN"
             else f"{YELLOW}--{RESET}")
    return " ".join(coloured) + f" {arrow}"


def fuzzy_find_team(name: str) -> Optional[str]:
    exact = [t for t in TEAMS if t.lower() == name.lower()]
    if exact:
        return exact[0]
    close = difflib.get_close_matches(name, TEAMS.keys(), n=1, cutoff=0.55)
    return close[0] if close else None


def find_venue_index(name: str, venue_names: List[str]) -> int:
    """Find the index of a venue by name, defaulting to 0 if not found."""
    for i, v in enumerate(venue_names):
        if v.lower() == name.lower():
            return i
    return 0


def pick_venue() -> str:
    venue_names = sorted(VENUES.keys())
    default_idx = find_venue_index("New York", venue_names) + 1

    print(f"\n{BOLD}Available Venues:{RESET}")
    for i, v in enumerate(venue_names, 1):
        vd = VENUES[v]
        alt_str = f"{vd['altitude_m']}m" if vd['altitude_m'] > 500 else "low"
        roof_str = vd.get("roof", "open")
        roof_col = GREEN if roof_str in ("dome", "retractable") else YELLOW if roof_str == "partial" else ""
        print(f"  {CYAN}{i:>2}.{RESET} {v:<16}({vd['country']:<7}) "
              f"Alt:{alt_str:<6} Heat:{vd['heat_index']:.0%} Humid:{vd['humidity_index']:.0%} "
              f"Roof:{roof_col}{roof_str}{RESET}")

    while True:
        try:
            choice = int(input(f"\n{BOLD}Select venue [{default_idx}={venue_names[default_idx-1]}]: {RESET}").strip()
                         or str(default_idx))
            if 1 <= choice <= len(venue_names):
                return venue_names[choice - 1]
        except ValueError:
            pass
        print(f"{RED}Enter a number 1-{len(venue_names)}.{RESET}")


def list_teams(page: int = 1) -> None:
    sorted_names = sorted(TEAMS.keys())
    per_page = math.ceil(len(sorted_names) / 2)
    total_pages = 2
    start = 0 if page == 1 else per_page
    end   = per_page if page == 1 else len(sorted_names)

    print(f"\n{BOLD}{CYAN}Team Directory — Page {page}/{total_pages} ({len(TEAMS)} total){RESET}")
    print(f"{BOLD}{'Team':<16} {'Code':<5}{'ATT/DEF':<9}{'WC':<5}{'Tactic':<14}{'Alt.C':<6}{'Heat.T':<7}{'Last 10'}{RESET}")
    print("=" * 82)
    for name in sorted_names[start:end]:
        d = TEAMS[name]
        trend, _, _ = calculate_trend_factor(d["last_10"])
        form_str = format_last10(d["last_10"], trend)
        host_tag = f"{GREEN}*{RESET}" if d.get("home_venue_country") else " "
        print(f"{host_tag}{name:<15} {d['code']:<5}{d['att']}/{d['def']:<6}"
              f"{d['wc_exp']:<5}{d['default_tactic']:<14}"
              f"{d.get('altitude_comfort',0):<6.1f}{d.get('heat_tolerance',0):<7.1f}"
              f"{form_str}")
    print()


def display_venue_report(venue_key: str, team_a: str, team_b: str) -> None:
    v  = VENUES[venue_key]
    ma = get_venue_modifier(team_a, venue_key, False)
    mb = get_venue_modifier(team_b, venue_key, False)
    roof = v.get("roof", "open")
    reduction = get_roof_heat_reduction(roof)

    print(f"\n{BOLD}Venue: {CYAN}{v['city']}{RESET} — {v.get('stadium', '')} ({v['country']})")
    print(f"  Climate  : {v['climate']}")
    print(f"  Altitude : {v['altitude_m']}m")
    print(f"  Outdoor  : Heat {v['heat_index']:.0%}  Humidity {v['humidity_index']:.0%}")
    print(f"  Roof     : {roof} ({reduction:.0%} heat/humidity reduction)")

    # v2.1 fix: display as deviation from 1.0, not raw multiplier
    da = ma - 1.0
    db = mb - 1.0
    ma_col = GREEN if da >= 0 else YELLOW if da > -0.05 else RED
    mb_col = GREEN if db >= 0 else YELLOW if db > -0.05 else RED
    print(f"  {team_a:<15} venue impact: {ma_col}{da:+.1%}{RESET}  "
          f"(alt.comfort={TEAMS[team_a].get('altitude_comfort',0):.1f}, "
          f"heat.tol={TEAMS[team_a].get('heat_tolerance',0):.1f})")
    print(f"  {team_b:<15} venue impact: {mb_col}{db:+.1%}{RESET}  "
          f"(alt.comfort={TEAMS[team_b].get('altitude_comfort',0):.1f}, "
          f"heat.tol={TEAMS[team_b].get('heat_tolerance',0):.1f})")
    print()


def display_team_preview(team: str) -> None:
    d = TEAMS[team]
    trend, idx, mod = calculate_trend_factor(d["last_10"])
    host_tag = f" {GREEN}[HOST]{RESET}" if d.get("home_venue_country") else ""
    print(f"  {BOLD}{team} ({d['code']}){RESET}{host_tag}")
    print(f"    WC Experience  : {d['wc_exp']}/100")
    print(f"    Base ATT/DEF   : {d['att']} / {d['def']}")
    print(f"    Natural Tactic : {d['default_tactic']}")
    print(f"    Alt. Comfort   : {d.get('altitude_comfort',0):.1f}  |  Heat Tolerance: {d.get('heat_tolerance',0):.1f}")
    print(f"    Last 10 Form   : {format_last10(d['last_10'], trend)}")
    print(f"    Form Modifier  : {(mod - 1.0):+.1%} (Index: {idx:.1f}%)")


# ─── Match Result Printer ──────────────────────────────────────────────────────

def print_live_result(team_a: str, team_b: str, live: Dict) -> None:
    print(f"\n{BOLD}{BG_GREEN}  LIVE MATCH RESULT  {RESET}")
    print(f"  [90 Mins] {team_a}  {live['score_a']} - {live['score_b']}  {team_b}")
    if live["extra_time"]:
        print(f"  [AET]     Match was level - Extra Time played.")
        if live["penalties"]:
            print(f"  [Pens]    {team_a} {live['pens_a']} - {live['pens_b']} {team_b}")
            winner = get_match_winner(team_a, team_b, live)
            print(f"  {BOLD}{YELLOW}Winner: {winner} wins on penalties!{RESET}")
        else:
            winner = team_a if live["score_a"] > live["score_b"] else team_b
            print(f"  {BOLD}{YELLOW}Winner: {winner} wins in Extra Time!{RESET}")
    else:
        if live["score_a"] > live["score_b"]:
            print(f"  {BOLD}{YELLOW}Winner: {team_a}!{RESET}")
        elif live["score_b"] > live["score_a"]:
            print(f"  {BOLD}{YELLOW}Winner: {team_b}!{RESET}")
        else:
            print(f"  {YELLOW}Result: Draw!{RESET}")


# ─── Bracket Simulator ────────────────────────────────────────────────────────

def simulate_bracket_match(t1: str, t2: str, venue_key: str) -> Tuple[str, str, Dict]:
    # Silent MC (no progress bar in bracket mode)
    mc = run_monte_carlo(t1, t2, runs=1000, is_knockout=True,
                         venue_key=venue_key, show_progress=False)
    print(f"  Odds  {CYAN}{t1}{RESET} {mc['a_win_pct']:.1f}%  |  "
          f"{MAGENTA}{t2}{RESET} {mc['b_win_pct']:.1f}%")

    res = simulate_match(t1, t2, is_knockout=True, venue_key=venue_key)
    winner = get_match_winner(t1, t2, res)
    loser  = t2 if winner == t1 else t1
    score  = f"{t1} {res['score_a']} - {res['score_b']} {t2}"
    if res["extra_time"] and not res["penalties"]:
        score += " (AET)"
    if res["penalties"]:
        score += f" (Pens {res['pens_a']}-{res['pens_b']})"
    return winner, loser, {"score": score, "tactic_a": res["tactic_a"], "tactic_b": res["tactic_b"]}


# ─── Main Application ──────────────────────────────────────────────────────────

def main() -> None:
    print(f"\n{BOLD}{GREEN}{'=' * 58}{RESET}")
    print(f"{BOLD}{GREEN}   WORLD CUP 2026 GAME PREDICTOR -- CLI v2.1{RESET}")
    print(f"{BOLD}{GREEN}{'=' * 58}{RESET}")
    print(f"  Engine : Poisson + Monte Carlo + Venue Conditions")
    print(f"  Teams  : {BOLD}{len(TEAMS)}{RESET} nations  |  Venues: {BOLD}{len(VENUES)}{RESET} stadiums")
    print(f"  New    : Altitude comfort, heat tolerance, roof types")
    print(f"{BOLD}{GREEN}{'=' * 58}{RESET}\n")

    while True:
        print(f"\n{BOLD}MAIN MENU{RESET}")
        print(f"  1. {CYAN}Simulate Single Match{RESET}")
        print(f"  2. {CYAN}Run Knockout Bracket (8 Teams){RESET}")
        print(f"  3. {CYAN}View All Team Stats{RESET}")
        print(f"  4. {CYAN}View All Venue Conditions{RESET}")
        print(f"  5. {RED}Exit{RESET}")

        choice = input(f"\n{BOLD}> {RESET}").strip()

        # ── Option 1: Single Match ─────────────────────────────────────────
        if choice == "1":
            while True:   # Replay loop
                print_header("SINGLE MATCH SIMULATOR")
                list_teams(page=1)
                see_more = input("Enter to continue, '2' for page 2: ").strip()
                if see_more == "2":
                    list_teams(page=2)

                while True:
                    raw = input(f"\n{BOLD}Home Team: {RESET}").strip()
                    team_a = fuzzy_find_team(raw)
                    if team_a:
                        if raw.lower() != team_a.lower():
                            print(f"  {YELLOW}Matched: {team_a}{RESET}")
                        break
                    print(f"{RED}No match for '{raw}'. Try again.{RESET}")

                while True:
                    raw = input(f"{BOLD}Away Team: {RESET}").strip()
                    team_b = fuzzy_find_team(raw)
                    if team_b:
                        if raw.lower() != team_b.lower():
                            print(f"  {YELLOW}Matched: {team_b}{RESET}")
                        break
                    print(f"{RED}No match for '{raw}'. Try again.{RESET}")

                if team_a == team_b:
                    print(f"{RED}Teams must be different!{RESET}")
                    continue

                is_ko = input("Knockout match? (y/N): ").strip().lower() == "y"
                venue_key = pick_venue()

                # Pre-match intelligence
                print(f"\n{BOLD}--- Pre-Match Intelligence ---{RESET}")
                display_team_preview(team_a)
                print()
                display_team_preview(team_b)
                display_venue_report(venue_key, team_a, team_b)

                print(f"{YELLOW}Running 10,000 simulations...{RESET}")
                res = run_monte_carlo(team_a, team_b, runs=10000,
                                      is_knockout=is_ko, venue_key=venue_key)

                print(f"\n{BOLD}{GREEN}=== PREDICTION RESULTS ==={RESET}")
                print(f"{BOLD}{team_a}{RESET} ({res['tactic_a']}) vs "
                      f"{BOLD}{team_b}{RESET} ({res['tactic_b']})")
                print(f"Venue: {VENUES[venue_key]['city']}  |  "
                      f"Type: {'Knockout' if is_ko else 'Group Stage'}\n")

                print(f"{BOLD}Outcome Probabilities:{RESET}")
                if is_ko:
                    print(f"  {CYAN}{team_a:<15} Advance : {res['a_win_pct']:>6.2f}%{RESET}")
                    print(f"  {MAGENTA}{team_b:<15} Advance : {res['b_win_pct']:>6.2f}%{RESET}")
                    print(f"\n  {BOLD}Knockout Breakdown:{RESET}")
                    print(f"    {CYAN}{team_a:<13}{RESET} Win (90m) : {res['a_win_90_pct']:>5.2f}%")
                    print(f"    {MAGENTA}{team_b:<13}{RESET} Win (90m) : {res['b_win_90_pct']:>5.2f}%")
                    print(f"    {YELLOW}{'Draw (90m)':<13}{RESET}           : {res['draw_90_pct']:>5.2f}%")
                    print(f"    {CYAN}{team_a:<13}{RESET} Win (AET) : {res['a_win_aet_pct']:>5.2f}%")
                    print(f"    {MAGENTA}{team_b:<13}{RESET} Win (AET) : {res['b_win_aet_pct']:>5.2f}%")
                    print(f"    {CYAN}{team_a:<13}{RESET} Win (Pen) : {res['a_win_pen_pct']:>5.2f}%")
                    print(f"    {MAGENTA}{team_b:<13}{RESET} Win (Pen) : {res['b_win_pen_pct']:>5.2f}%")
                else:
                    print(f"  {CYAN}{team_a:<15} Win : {res['a_win_pct']:>6.2f}%{RESET}")
                    print(f"  {YELLOW}{'Draw':<15}     : {res['draw_pct']:>6.2f}%{RESET}")
                    print(f"  {MAGENTA}{team_b:<15} Win : {res['b_win_pct']:>6.2f}%{RESET}")

                print(f"\n{BOLD}Top Scorelines:{RESET}")
                for rank, (scoreline, count) in enumerate(res["top_scores"], 1):
                    pct = (count / res["total_runs"]) * 100
                    parts = scoreline.split("-")
                    score_str = f"{team_a} {parts[0]} - {parts[1]} {team_b}"
                    bar_len = int(pct * 1.5)
                    print(f"  {rank}. {score_str:<35} {pct:5.2f}%  {'|' * bar_len}")

                input(f"\n{YELLOW}Press Enter to simulate a live match...{RESET}")
                live = simulate_match(team_a, team_b, is_knockout=is_ko, venue_key=venue_key)
                print_live_result(team_a, team_b, live)

                # Replay prompt
                again = input(f"\n{CYAN}Run another match? (y/N): {RESET}").strip().lower()
                if again != "y":
                    break

        # ── Option 2: Knockout Bracket ─────────────────────────────────────
        elif choice == "2":
            print_header("KNOCKOUT BRACKET SIMULATOR")
            print(f"  1. Seed Top 8 by rating\n  2. Random 8\n  3. Manual pick 8")
            seed_choice = input(f"\n{BOLD}> {RESET}").strip()

            selected: list = []
            if seed_choice == "1":
                ranked = sorted(
                    TEAMS.keys(),
                    key=lambda t: ((TEAMS[t]["att"] + TEAMS[t]["def"]) / 2.0) * (1.0 + TEAMS[t]["wc_exp"] / 500.0),
                    reverse=True
                )
                selected = list(ranked[:8])
            elif seed_choice == "2":
                selected = random.sample(list(TEAMS.keys()), 8)
            elif seed_choice == "3":
                list_teams(1); list_teams(2)
                print(f"{BOLD}Pick 8 teams:{RESET}")
                while len(selected) < 8:
                    raw = input(f"  Team {len(selected)+1}/8: ").strip()
                    t = fuzzy_find_team(raw)
                    if not t:
                        print(f"{RED}Not found.{RESET}")
                    elif t in selected:
                        print(f"{RED}Already picked.{RESET}")
                    else:
                        print(f"  {YELLOW}Added: {t}{RESET}")
                        selected.append(t)
            else:
                print(f"{RED}Defaulting to Top 8.{RESET}")
                ranked = sorted(TEAMS.keys(), key=lambda t: (TEAMS[t]["att"] + TEAMS[t]["def"]) / 2.0, reverse=True)
                selected = list(ranked[:8])

            print(f"\n{BOLD}Select venue for bracket:{RESET}")
            venue_key = pick_venue()
            print(f"\n{BOLD}Bracket:{RESET} {', '.join(selected)}")

            input(f"\n{YELLOW}Press Enter for Quarter-Finals...{RESET}")

            semis: list = []
            print(f"\n{BOLD}{'='*60}{RESET}")
            print(f"{BOLD}QUARTER-FINALS -- {VENUES[venue_key]['city']}{RESET}")
            print(f"{BOLD}{'='*60}{RESET}")
            for idx in range(0, 8, 2):
                t1, t2 = selected[idx], selected[idx+1]
                print(f"\nQF {idx//2+1}: {BOLD}{t1}{RESET} vs {BOLD}{t2}{RESET}")
                winner, loser, info = simulate_bracket_match(t1, t2, venue_key)
                print(f"  {info['score']}  ({info['tactic_a']} vs {info['tactic_b']})")
                print(f"  {GREEN}{winner} advances!{RESET}")
                semis.append(winner)
                time.sleep(0.3)

            input(f"\n{YELLOW}Press Enter for Semi-Finals...{RESET}")

            finalists: list = []
            third:     list = []
            print(f"\n{BOLD}SEMI-FINALS{RESET}")
            print(f"{'='*60}")
            for idx in range(0, 4, 2):
                t1, t2 = semis[idx], semis[idx+1]
                print(f"\nSF {idx//2+1}: {BOLD}{t1}{RESET} vs {BOLD}{t2}{RESET}")
                winner, loser, info = simulate_bracket_match(t1, t2, venue_key)
                print(f"  {info['score']}  ({info['tactic_a']} vs {info['tactic_b']})")
                print(f"  {GREEN}{winner} to the Final!{RESET}")
                finalists.append(winner)
                third.append(loser)
                time.sleep(0.3)

            input(f"\n{YELLOW}Press Enter for Third Place Playoff...{RESET}")

            t1, t2 = third[0], third[1]
            print(f"\n{BOLD}THIRD PLACE PLAYOFF{RESET}")
            print(f"{'='*60}")
            print(f"{BOLD}{t1}{RESET} vs {BOLD}{t2}{RESET}")
            winner_3, _, info3 = simulate_bracket_match(t1, t2, venue_key)
            print(f"  {info3['score']}")
            print(f"  {YELLOW}{winner_3} finishes THIRD!{RESET}")

            input(f"\n{YELLOW}Press Enter for the GRAND FINAL...{RESET}")

            t1, t2 = finalists[0], finalists[1]
            print(f"\n{BOLD}{BG_BLUE}  WORLD CUP 2026 GRAND FINAL  {RESET}")
            print(f"{'='*60}")
            print(f"{BOLD}{t1}{RESET} vs {BOLD}{t2}{RESET}")
            champion, _, infof = simulate_bracket_match(t1, t2, venue_key)
            print(f"  {infof['score']}")
            print(f"\n{BOLD}{YELLOW}  WORLD CUP 2026 CHAMPION: {champion}!{RESET}")

        # ── Option 3: Team Directory ───────────────────────────────────────
        elif choice == "3":
            print_header("TEAM DIRECTORY")
            print(f"  {GREEN}*{RESET} = Host nation  |  Alt.C = Altitude Comfort  |  Heat.T = Heat Tolerance")
            list_teams(1)
            input("Press Enter for page 2...")
            list_teams(2)

        # ── Option 4: Venue Conditions ─────────────────────────────────────
        elif choice == "4":
            print_header("STADIUM & VENUE CONDITIONS")
            print(f"{BOLD}{'Venue':<17}{'Stadium':<24}{'Country':<8}{'Alt(m)':<7}{'Heat':<6}{'Humid':<7}{'Roof':<13}{'Climate'}{RESET}")
            print("=" * 105)
            for name, v in sorted(VENUES.items(), key=lambda x: -x[1]["altitude_m"]):
                alt_col  = RED if v["altitude_m"] > 1500 else YELLOW if v["altitude_m"] > 500 else ""
                heat_col = RED if v["heat_index"] > 0.75 else YELLOW if v["heat_index"] > 0.5 else ""
                roof = v.get("roof", "open")
                roof_col = GREEN if roof in ("dome", "retractable") else YELLOW if roof == "partial" else ""
                print(
                    f"{name:<17}{v.get('stadium',''):<24}{v['country']:<8}"
                    f"{alt_col}{v['altitude_m']:<7}{RESET}"
                    f"{heat_col}{v['heat_index']:.0%}{RESET}   "
                    f"{v['humidity_index']:.0%}   "
                    f"{roof_col}{roof:<13}{RESET}"
                    f"{v['climate'][:38]}"
                )

        # ── Option 5: Exit ─────────────────────────────────────────────────
        elif choice == "5":
            print(f"\n{BOLD}{GREEN}Thanks for using World Cup Predictor. Goodbye!{RESET}\n")
            sys.exit(0)
        else:
            print(f"{RED}Invalid option. Choose 1-5.{RESET}")


if __name__ == "__main__":
    main()
