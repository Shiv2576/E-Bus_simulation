import json
import os
from typing import Dict, List


def load_scenarios() -> List[Dict]:
    """Load scenarios from JSON file"""
    file_path = os.path.join(os.path.dirname(__file__), "data", "scenarios.json")

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        return data["scenarios"]
    except FileNotFoundError:
        print(f"ERROR: scenarios.json not found at {file_path}")
        return []
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in scenarios.json: {e}")
        return []


def get_scenario_by_name(name: str) -> Dict:
    """Get a specific scenario by name"""
    scenarios = load_scenarios()

    for scenario in scenarios:
        if scenario["name"] == name:
            return scenario

    raise ValueError(f"Scenario '{name}' not found")
