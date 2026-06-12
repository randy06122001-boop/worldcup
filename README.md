# World Cup 2026 Game Predictor

An advanced command-line (CLI) simulator and predictor for the World Cup 2026. Built in Python, it uses a Double Poisson distribution model coupled with a 10,000-run Monte Carlo simulation to forecast realistic outcomes, goals, draws, extra-time matches, and penalty shootouts.

## 🚀 Key Features

* **Double Poisson Match Engine**: Estimates expected goals (xG) based on attack/defense ratings, tactical modifiers, and form.
* **10,000-Run Monte Carlo Simulation**: Forecasts outcome percentages (Win/Draw/Loss) and determines the most likely scorelines.
* **Knockout Stage Breakdown**: Provides precise odds for matches going to Extra Time (AET) and Penalty Shootouts (Pens), listing 90-minute vs. overtime probabilities.
* **Dynamic Environment Modifiers**:
  * **Altitude Penalty**: High altitude stadiums drain team attack composure (acclimatization scaled by team-specific altitude comfort).
  * **Heat & Humidity Drain**: Combined heat/humidity reduces offensive output.
  * **Roof Adjustments**: Stadium roofs (Dome: 100%, Retractable: 70%, Partial: 30%, Open: 0%) mitigate heat/humidity effects dynamically.
  * **Home Advantage**: Country-specific crowd boost (e.g., USA playing in USA venues).
* **Form & Trend Tracker**: Calculates a weighted moving average of the last 10 games to apply form-based buffs/debuffs (UP, DOWN, STABLE).
* **Composure & WC Experience**: Composure buffs applied to tournament-tested teams during critical knockout stages and penalty shootouts.
* **Fuzzy Team Search**: Search for teams with relaxed string matching (e.g., entering "eng" matches "England").
* **Tournament Bracket Simulator**: Simulate an 8-team knockout bracket (Quarter-Finals to Grand Final) at any selected venue.

---

## 🛠️ Installation & Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/randy06122001-boop/worldcup.git
   cd worldcup
   ```

2. **Verify Files**: Ensure the following files are present in the directory:
   * `world_cup_sim.py` (Executable Python script)
   * `teams.json` (Nations statistics database)
   * `venues.json` (16 World Cup 2026 Host Venues)

3. **Run the Simulator**:
   ```bash
   python world_cup_sim.py
   ```

---

## 📊 How It Works (The Engine)

### Expected Goals (Poisson $\lambda$)
For any match, the expected goals ($\lambda_A$ and $\lambda_B$) for Team A and Team B are estimated as:
$$\lambda_A = \text{base} \times \frac{\text{ATT}_A}{\text{AvgRating}} \times \frac{\text{AvgRating}}{\text{DEF}_B}$$
$$\lambda_B = \text{base} \times \frac{\text{ATT}_B}{\text{AvgRating}} \times \frac{\text{AvgRating}}{\text{DEF}_A}$$

Where:
* **ATT / DEF** are modified by tactics, form trends, WC experience, and venue factors.
* **Venue Factors** only drain **ATTACK** ratings, reflecting decreased conversion under harsh conditions (e.g., altitude or heat).

---

## 🗃️ Database Structure

### `teams.json`
Stores stats for all 49 participating teams:
```json
"England": {
  "att": 87.0,
  "def": 85.0,
  "code": "ENG",
  "wc_exp": 85,
  "default_tactic": "Gegenpressing",
  "home_venue_country": null,
  "altitude_comfort": 0.15,
  "heat_tolerance": 0.15,
  "last_10": ["W", "W", "D", "W", "L", "W", "W", "D", "W", "W"]
}
```

### `venues.json`
Stores the climate data and roof configuration of all 16 official stadiums:
```json
"Dallas": {
  "city": "Dallas",
  "country": "USA",
  "stadium": "AT&T Stadium",
  "altitude_m": 180,
  "heat_index": 0.85,
  "humidity_index": 0.65,
  "roof": "retractable",
  "climate": "Humid subtropical, very hot summers"
}
```
