from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path
from typing import Any, Callable, Dict

import requests
from dotenv import find_dotenv, load_dotenv

from common.logger_config import setup_logger

_ = load_dotenv(find_dotenv())
logger = setup_logger("S01E02Tools")

HUB_BASE_URL = os.getenv("HUB_BASE_URL", "")
API_KEY = os.getenv("API_KEY", "")

RESOURCES_DIR = Path(__file__).resolve().parent / "resources"

# ---------------------------------------------------------------------------
# Verifier reference — set by S01E02 task class before agent starts
# ---------------------------------------------------------------------------
_task_verifier: Any = None


def set_task_verifier(verifier: Any) -> None:
    """Inject the BaseTask instance so verify() can call BaseTask.verify()."""
    global _task_verifier
    _task_verifier = verifier


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def get_suspects() -> str:
    """Read suspects from the local CSV file."""
    csv_path = RESOURCES_DIR / "people_suspected.csv"
    if not csv_path.exists():
        return json.dumps({"error": f"File not found: {csv_path}"})

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [row for row in reader]

    logger.info("get_suspects: loaded %d suspects", len(rows))
    return json.dumps(rows, ensure_ascii=False)


def get_powerplants() -> str:
    """Fetch power plant locations from the hub."""
    url = f"{HUB_BASE_URL}/data/{API_KEY}/findhim_locations.json"
    logger.info("get_powerplants: GET %s", url)

    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    logger.info("get_powerplants: received %d entries", len(data) if isinstance(data, list) else 1)
    return json.dumps(data, ensure_ascii=False)


def get_person_locations(name: str, surname: str) -> str:
    """Get last-known coordinates for a person from the hub."""
    url = f"{HUB_BASE_URL}/api/location"
    payload = {"apikey": API_KEY, "name": name, "surname": surname}
    logger.info("get_person_locations: POST %s for %s %s", url, name, surname)

    response = requests.post(url, json=payload)
    response.raise_for_status()
    data = response.json()

    logger.info("get_person_locations: response for %s %s: %s", name, surname, json.dumps(data, ensure_ascii=False))
    return json.dumps(data, ensure_ascii=False)


def get_person_access_level(name: str, surname: str, birth_year: int) -> str:
    """Get access level for a person from the hub."""
    url = f"{HUB_BASE_URL}/api/accesslevel"
    payload = {"apikey": API_KEY, "name": name, "surname": surname, "birthYear": birth_year}
    logger.info("get_person_access_level: POST %s for %s %s (born %d)", url, name, surname, birth_year)

    response = requests.post(url, json=payload)
    response.raise_for_status()
    data = response.json()

    logger.info("get_person_access_level: response: %s", json.dumps(data, ensure_ascii=False))
    return json.dumps(data, ensure_ascii=False)


def get_city_coordinates(city_name: str) -> str:
    """Get geographic coordinates for a Polish city using Nominatim."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {"city": city_name, "country": "Poland", "format": "json"}
    headers = {"User-Agent": "aidevs4-task/1.0"}
    logger.info("get_city_coordinates: GET %s for city=%s", url, city_name)

    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()

    if not data:
        return json.dumps({"error": f"No results found for city: {city_name}"})

    first = data[0]
    result = {
        "city": city_name,
        "latitude": float(first["lat"]),
        "longitude": float(first["lon"]),
        "display_name": first.get("display_name", ""),
    }
    logger.info("get_city_coordinates: %s -> lat=%s, lon=%s", city_name, result["latitude"], result["longitude"])
    return json.dumps(result, ensure_ascii=False)


def get_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> str:
    """Calculate haversine distance between two geographic points in kilometers."""
    lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    R = 6371.0  # Earth radius in km
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance_km = R * c

    result = {"lat1": lat1, "lon1": lon1, "lat2": lat2, "lon2": lon2, "distance_km": round(distance_km, 3)}
    logger.info("get_distance: %s", json.dumps(result))
    return json.dumps(result, ensure_ascii=False)


def verify(name: str, surname: str, access_level: str, power_plant: str) -> str:
    """Submit the final answer to the hub for verification."""
    if _task_verifier is None:
        return json.dumps({"error": "Task verifier not initialized."})

    answer = {
        "name": name,
        "surname": surname,
        "accessLevel": access_level,
        "powerPlant": power_plant,
    }
    logger.info("verify: submitting answer: %s", json.dumps(answer, ensure_ascii=False))

    result = _task_verifier.verify(answer)
    logger.info("verify: hub response: %s", json.dumps(result, ensure_ascii=False))
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function calling schema)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_suspects",
            "description": "Get the list of suspected persons from local CSV file. Returns name, surname, gender, born year, city, tags.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_powerplants",
            "description": "Get the list of power plants with their city names and identification codes from the hub.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_person_locations",
            "description": "Get the last-known geographic coordinates (latitude, longitude) where a person was seen. Returns a list of locations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "First name of the person"},
                    "surname": {"type": "string", "description": "Last name of the person"},
                },
                "required": ["name", "surname"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_person_access_level",
            "description": "Get the access level for a specific person identified by name, surname, and birth year.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "First name of the person"},
                    "surname": {"type": "string", "description": "Last name of the person"},
                    "birth_year": {"type": "integer", "description": "Year the person was born"},
                },
                "required": ["name", "surname", "birth_year"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_city_coordinates",
            "description": "Get geographic coordinates (latitude, longitude) for a city in Poland using Nominatim geocoding.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city_name": {"type": "string", "description": "Name of the city in Poland"},
                },
                "required": ["city_name"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_distance",
            "description": "Calculate the haversine distance in kilometers between two geographic points specified by latitude and longitude.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lat1": {"type": "number", "description": "Latitude of the first point"},
                    "lon1": {"type": "number", "description": "Longitude of the first point"},
                    "lat2": {"type": "number", "description": "Latitude of the second point"},
                    "lon2": {"type": "number", "description": "Longitude of the second point"},
                },
                "required": ["lat1", "lon1", "lat2", "lon2"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify",
            "description": "Submit the final answer to the hub for verification. Use this when you have identified the suspect closest to a power plant, their access level, and the power plant code. The hub responds with a flag {FLG:...} on success or an error message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "First name of the suspect"},
                    "surname": {"type": "string", "description": "Last name of the suspect"},
                    "access_level": {"type": "string", "description": "Access level of the suspect"},
                    "power_plant": {"type": "string", "description": "Power plant identification code"},
                },
                "required": ["name", "surname", "access_level", "power_plant"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    },
]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

_TOOL_REGISTRY: Dict[str, Callable[..., str]] = {
    "get_suspects": get_suspects,
    "get_powerplants": get_powerplants,
    "get_person_locations": get_person_locations,
    "get_person_access_level": get_person_access_level,
    "get_city_coordinates": get_city_coordinates,
    "get_distance": get_distance,
    "verify": verify,
}


def tool_executor(name: str, args: Dict[str, Any]) -> str:
    """Dispatch a tool call by name to its implementation."""
    func = _TOOL_REGISTRY.get(name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    return func(**args)
