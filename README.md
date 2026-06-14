# World Cup 2026 Game Predictor v3.0

An advanced command-line (CLI) simulator and predictor for the World Cup 2026. Built in Python, it uses a Double Poisson distribution model coupled with a 10,000-run Monte Carlo simulation to forecast realistic outcomes, goals, draws, extra-time matches, and penalty shootouts.

## Features

### Simulation Engine
* **Double Poisson Match Engine**: Estimates expected goals (xG) based on attack/defense ratings, tactical modifiers, and form.
* **10,000-Run Monte Carlo Simulation**: Forecasts outcome percentages with **95% confidence intervals** (e.g., `62.35% +/- 0.95%`).
* **Knockout Stage Breakdown**: Precise odds for 90-minute win, Extra Time (AET), and Penalty Shootouts separately.
* **Smooth Form Trend**: Continuous linear modifier based on weighted last-10 results (no dead zone).
* **Sequential Penalty Shootout**: Realistic sudden death with early-exit logic matching real tournament rules.
* **Extra Time Fatigue**: Environmental penalties (heat, altitude) are doubled during extra time.

### Environmental Modifiers
* **Altitude Penalty**: High altitude stadiums drain team attack (scaled by team-specific altitude comfort).
* **Heat & Humidity Drain**: Combined heat/humidity reduces offensive output (scaled by team-specific heat tolerance).
* **Roof Adjustments**: Dome (100%), Retractable (70%), Partial (30%), Open (0%) heat/humidity reduction.
* **Home Advantage**: Country-specific crowd boost (e.g., USA at US venues).

### Match Features
* **Red Card Toggle**: Simulate the impact of a red card (-15% ATT, -10% DEF) for either team.
* **Save/Export Reports**: Save match prediction reports as `.txt` files in the `exports/` folder.
* **Fuzzy Team Search**: Relaxed string matching + country code support (e.g., "ENG" matches "England").

### Tournament Modes
* **Single Match**: Simulate any head-to-head matchup with full pre-match intelligence.
* **8-Team Knockout Bracket**: Quarter-Finals through Grand Final with odds per round.
* **Full 48-Team Tournament**: 12 groups of 4 (serpentine seeding) -> Round of 32 -> Grand Final.

---

## Installation & Usage

### Setup
```bash
git clone https://github.com/randy06122001-boop/worldcup.git
cd worldcup
```

No dependencies beyond Python 3.7+ standard library.

### Interactive Mode
```bash
python world_cup_sim.py
```

### CLI Mode (Non-Interactive)
```bash
# Quick single match
python world_cup_sim.py --match "England" "Japan" --venue "Dallas" --knockout

# With red card
python world_cup_sim.py --match "Brazil" "Germany" --venue "New York" --red-card-b

# Top 8 bracket
python world_cup_sim.py --bracket --top8

# Full 48-team tournament
python world_cup_sim.py --groups

# Custom simulation count
python world_cup_sim.py --match "USA" "Mexico" --runs 50000
```

### CLI Options
| Flag | Description |
|------|-------------|
| `--match TEAM_A TEAM_B` | Simulate a single match |
| `--venue NAME` | Set the venue (default: New York) |
| `--knockout` | Treat as knockout match |
| `--bracket` | Run 8-team knockout bracket |
| `--top8` | Seed bracket with top 8 teams |
| `--groups` | Run full 48-team group stage + knockout |
| `--runs N` | Number of Monte Carlo simulations (default: 10000) |
| `--red-card-a` | Red card for Team A (-15% ATT, -10% DEF) |
| `--red-card-b` | Red card for Team B |

---

## How It Works

### Expected Goals (Poisson Lambda)
For any match, the expected goals for Team A and Team B are estimated as:

$$\lambda_A = \text{base} \times \frac{\text{ATT}_A}{\text{AvgRating}} \times \frac{\text{AvgRating}}{\text{DEF}_B}$$

Where **ATT** and **DEF** are modified by:
- Tactical modifiers (Gegenpressing, Attacking, Defensive, Neutral)
- Form trend (continuous, weighted last-10 results)
- WC experience (knockout rounds only)
- Venue factors (altitude, heat/humidity, roof type — attack only)
- Red card penalties (if active)

### Confidence Intervals
Monte Carlo estimates include 95% CI: $\text{margin} = 1.96 \times \sqrt{\frac{p(1-p)}{N}}$

---

## Data Files

### `teams.json` (48 teams)
```json
"England": {
  "att": 84, "def": 81, "code": "ENG", "wc_exp": 85,
  "default_tactic": "Gegenpressing",
  "altitude_comfort": 0.10, "heat_tolerance": 0.15,
  "last_10": ["W","W","D","L","W","D","W","W","L","D"]
}
```

### `venues.json` (16 stadiums)
```json
"Dallas": {
  "city": "Dallas", "country": "USA", "stadium": "AT&T Stadium",
  "altitude_m": 139, "heat_index": 0.90, "humidity_index": 0.70,
  "roof": "retractable",
  "climate": "Extreme summer heat, retractable roof likely closed"
}
```

---

## Changelog

### v3.0
- Full 48-team Group Stage Simulator (12 groups, serpentine seeding)
- CLI arguments via argparse (non-interactive mode)
- Save/export match reports to `exports/`
- 95% confidence intervals on all probabilities
- Red card toggle (-15% ATT, -10% DEF)
- Extra time fatigue (doubled environmental penalties)
- Smooth continuous trend modifier (no dead zone)
- Sequential penalty sudden death
- Fixed 90-min vs AET score display
- Widened penalty conversion range (65-80%)
- Fuzzy search now supports country codes
- Removed Venezuela (49 -> 48 teams)
- Updated Spain & England tactics to Gegenpressing
- Added `.gitignore`

### v2.1
- Team-specific altitude comfort & heat tolerance
- Indoor/retractable roof logic
- Country-specific home boost
- JSON validation at startup

### v1.0
- Initial release with Poisson + Monte Carlo engine
