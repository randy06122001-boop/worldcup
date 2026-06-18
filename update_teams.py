import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
teams_file = os.path.join(SCRIPT_DIR, "teams.json")

# The confirmed 48 teams for 2026 World Cup
groups = {
    "A": ["Mexico", "South Korea", "Czechia", "South Africa"],
    "B": ["Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"],
    "C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "D": ["United States", "Australia", "Turkey", "Paraguay"],
    "E": ["Germany", "Ivory Coast", "Curaçao", "Ecuador"],
    "F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Uruguay", "Saudi Arabia", "Cape Verde"],
    "I": ["France", "Norway", "Senegal", "Iraq"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
    "L": ["England", "Croatia", "Ghana", "Panama"]
}

confirmed_teams = set()
for group, members in groups.items():
    for t in members:
        confirmed_teams.add(t)

with open(teams_file, "r", encoding="utf-8") as f:
    current_teams = json.load(f)

# Map some common names to match the script's names if necessary
# E.g. "USA" to "United States", "Korea Republic" to "South Korea"
name_map = {
    "USA": "United States",
    "Korea Republic": "South Korea",
    "Türkiye": "Turkey"
}

updated_teams = {}
for name, data in current_teams.items():
    mapped_name = name_map.get(name, name)
    if mapped_name in confirmed_teams:
        updated_teams[mapped_name] = data
    else:
        print(f"Removing: {name}")

missing = confirmed_teams - set(updated_teams.keys())
print(f"Missing teams to add: {missing}")

# Add missing teams with estimated stats
defaults = {
    "Czechia": {"att": 76, "def": 76, "code": "CZE", "wc_exp": 40, "default_tactic": "Neutral", "home_venue_country": None, "altitude_comfort": 0.1, "heat_tolerance": 0.15, "last_10": ["W","W","D","L","W","L","D","W","W","L"]},
    "South Africa": {"att": 74, "def": 73, "code": "RSA", "wc_exp": 35, "default_tactic": "Defensive", "home_venue_country": None, "altitude_comfort": 0.3, "heat_tolerance": 0.6, "last_10": ["W","D","D","W","W","L","D","W","W","L"]},
    "Bosnia and Herzegovina": {"att": 75, "def": 74, "code": "BIH", "wc_exp": 30, "default_tactic": "Neutral", "home_venue_country": None, "altitude_comfort": 0.1, "heat_tolerance": 0.2, "last_10": ["W","L","L","D","W","L","D","W","W","D"]},
    "Scotland": {"att": 76, "def": 77, "code": "SCO", "wc_exp": 45, "default_tactic": "Defensive", "home_venue_country": None, "altitude_comfort": 0.1, "heat_tolerance": 0.1, "last_10": ["D","L","D","W","W","W","D","L","W","D"]},
    "Haiti": {"att": 71, "def": 70, "code": "HAI", "wc_exp": 10, "default_tactic": "Defensive", "home_venue_country": None, "altitude_comfort": 0.1, "heat_tolerance": 0.8, "last_10": ["L","D","W","W","L","D","L","W","D","L"]},
    "Curaçao": {"att": 72, "def": 70, "code": "CUW", "wc_exp": 5, "default_tactic": "Attacking", "home_venue_country": None, "altitude_comfort": 0.1, "heat_tolerance": 0.7, "last_10": ["W","W","D","L","W","D","L","W","L","D"]},
    "Ivory Coast": {"att": 79, "def": 77, "code": "CIV", "wc_exp": 60, "default_tactic": "Neutral", "home_venue_country": None, "altitude_comfort": 0.2, "heat_tolerance": 0.7, "last_10": ["W","W","D","W","W","D","W","L","W","W"]},
    "Sweden": {"att": 80, "def": 81, "code": "SWE", "wc_exp": 75, "default_tactic": "Defensive", "home_venue_country": None, "altitude_comfort": 0.1, "heat_tolerance": 0.15, "last_10": ["W","D","W","W","D","W","L","D","W","W"]},
    "Tunisia": {"att": 75, "def": 76, "code": "TUN", "wc_exp": 55, "default_tactic": "Defensive", "home_venue_country": None, "altitude_comfort": 0.2, "heat_tolerance": 0.6, "last_10": ["D","W","D","W","L","D","W","W","L","D"]},
    "New Zealand": {"att": 72, "def": 71, "code": "NZL", "wc_exp": 30, "default_tactic": "Defensive", "home_venue_country": None, "altitude_comfort": 0.1, "heat_tolerance": 0.2, "last_10": ["W","W","D","L","W","L","D","W","L","D"]},
    "Cape Verde": {"att": 74, "def": 73, "code": "CPV", "wc_exp": 15, "default_tactic": "Neutral", "home_venue_country": None, "altitude_comfort": 0.1, "heat_tolerance": 0.6, "last_10": ["W","D","W","L","W","D","W","L","W","D"]},
    "Algeria": {"att": 78, "def": 77, "code": "ALG", "wc_exp": 60, "default_tactic": "Attacking", "home_venue_country": None, "altitude_comfort": 0.2, "heat_tolerance": 0.6, "last_10": ["W","W","D","W","L","D","W","W","W","D"]},
    "Austria": {"att": 80, "def": 79, "code": "AUT", "wc_exp": 50, "default_tactic": "Gegenpressing", "home_venue_country": None, "altitude_comfort": 0.2, "heat_tolerance": 0.2, "last_10": ["W","W","D","W","L","W","D","W","W","D"]},
    "Jordan": {"att": 73, "def": 71, "code": "JOR", "wc_exp": 10, "default_tactic": "Defensive", "home_venue_country": None, "altitude_comfort": 0.2, "heat_tolerance": 0.7, "last_10": ["W","D","W","W","L","D","L","W","W","D"]},
    "DR Congo": {"att": 75, "def": 74, "code": "COD", "wc_exp": 25, "default_tactic": "Neutral", "home_venue_country": None, "altitude_comfort": 0.2, "heat_tolerance": 0.7, "last_10": ["D","W","D","L","W","W","D","L","W","D"]},
    "Ghana": {"att": 76, "def": 75, "code": "GHA", "wc_exp": 60, "default_tactic": "Neutral", "home_venue_country": None, "altitude_comfort": 0.2, "heat_tolerance": 0.7, "last_10": ["W","L","D","W","L","W","D","W","D","W"]},
    "Panama": {"att": 74, "def": 74, "code": "PAN", "wc_exp": 30, "default_tactic": "Defensive", "home_venue_country": None, "altitude_comfort": 0.2, "heat_tolerance": 0.6, "last_10": ["L","D","W","W","L","W","L","W","D","W"]},
    "Norway": {"att": 82, "def": 78, "code": "NOR", "wc_exp": 45, "default_tactic": "Attacking", "home_venue_country": None, "altitude_comfort": 0.1, "heat_tolerance": 0.1, "last_10": ["W","W","L","W","D","W","W","L","W","W"]}
}

for name in missing:
    if name in defaults:
        updated_teams[name] = defaults[name]

# Some hardcoded updates based on current results:
# I: Norway 4-1 Iraq, France 3-1 Senegal
if "Norway" in updated_teams:
    updated_teams["Norway"]["last_10"] = updated_teams["Norway"]["last_10"][1:] + ["W"]
if "Iraq" in updated_teams:
    updated_teams["Iraq"]["last_10"] = updated_teams["Iraq"]["last_10"][1:] + ["L"]
if "France" in updated_teams:
    updated_teams["France"]["last_10"] = updated_teams["France"]["last_10"][1:] + ["W"]
if "Senegal" in updated_teams:
    updated_teams["Senegal"]["last_10"] = updated_teams["Senegal"]["last_10"][1:] + ["L"]

# K: Portugal 1-1 DR Congo
if "Portugal" in updated_teams:
    updated_teams["Portugal"]["last_10"] = updated_teams["Portugal"]["last_10"][1:] + ["D"]
if "DR Congo" in updated_teams:
    updated_teams["DR Congo"]["last_10"] = updated_teams["DR Congo"]["last_10"][1:] + ["D"]

# A: Mexico W, South Korea W
if "Mexico" in updated_teams:
    updated_teams["Mexico"]["last_10"] = updated_teams["Mexico"]["last_10"][1:] + ["W"]
if "South Korea" in updated_teams:
    updated_teams["South Korea"]["last_10"] = updated_teams["South Korea"]["last_10"][1:] + ["W"]

# D: United States W, Australia W
if "United States" in updated_teams:
    updated_teams["United States"]["last_10"] = updated_teams["United States"]["last_10"][1:] + ["W"]
if "Australia" in updated_teams:
    updated_teams["Australia"]["last_10"] = updated_teams["Australia"]["last_10"][1:] + ["W"]

# Save updated teams
with open(teams_file, "w", encoding="utf-8") as f:
    json.dump(updated_teams, f, indent=2)

print(f"Total teams: {len(updated_teams)}")
