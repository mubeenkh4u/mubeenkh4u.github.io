# tests/test_callbacks.py
import os
import sys
from pathlib import Path
import pytest
import pandas as pd
import math

# Import the enhanced CRUD module
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from animal_shelter import AnimalShelter  # :contentReference[oaicite:3]{index=3}

# --- notebook-equivalent helpers used by callbacks ---
def build_query(filter_type):
    if filter_type == 'water':
        return {
            "breed": {"$in": ["Labrador Retriever Mix", "Chesapeake Bay Retriever", "Newfoundland"]},
            "sex_upon_outcome": "Intact Female",
            "age_upon_outcome_in_weeks": {"$gte": 26, "$lte": 156}
        }
    elif filter_type == 'mountain':
        return {
            "breed": {"$in": ["German Shepherd", "Alaskan Malamute", "Old English Sheepdog", "Siberian Husky", "Rottweiler"]},
            "sex_upon_outcome": "Intact Male",
            "age_upon_outcome_in_weeks": {"$gte": 26, "$lte": 156}
        }
    elif filter_type == 'disaster':
        return {
            "breed": {"$in": ["Doberman Pinscher", "German Shepherd", "Golden Retriever", "Bloodhound", "Rottweiler"]},
            "sex_upon_outcome": "Intact Male",
            "age_upon_outcome_in_weeks": {"$gte": 20, "$lte": 300}
        }
    return {}


def validate_map_inputs(viewData, selected_rows):
    if not viewData:
        return "No data to map."
    dff = pd.DataFrame(viewData)
    if "location_lat" not in dff.columns or "location_long" not in dff.columns:
        return "Lat/Long columns not found in data."
    row = (selected_rows[0] if selected_rows and len(selected_rows) > 0 else 0)
    if row < 0 or row >= len(dff):
        return "Selected row is out of range."
    try:
        lat = float(dff.iloc[row]["location_lat"])
        lon = float(dff.iloc[row]["location_long"])
        # NEW: explicitly treat NaN as invalid coordinates
        if math.isnan(lat) or math.isnan(lon):
            return "Selected row has invalid coordinates."
    except Exception:
        return "Selected row has invalid coordinates."
    return "OK"

@pytest.fixture(scope="module")
def db():
    os.environ.setdefault("MONGO_DB", "aac")
    os.environ.setdefault("MONGO_COLL", "animals")
    return AnimalShelter("aacuser", "MAK1234")

@pytest.mark.parametrize("ftype", ["reset", "water", "mountain", "disaster"])
def test_build_query_and_read_does_not_crash(db, ftype):
    if db.collection is None:
        pytest.skip("No database connection; skipping dashboard read smoke test.")
    q = build_query(ftype)
    rows = db.read(q)  # should return a list even if empty
    assert isinstance(rows, list)

def test_map_guards_happy_path():
    view = [{"location_lat": 30.27, "location_long": -97.74, "breed": "Test", "name": "Fido"}]
    assert validate_map_inputs(view, [0]) == "OK"

@pytest.mark.parametrize("view, sel, expected", [
    ([], [], "No data to map."),
    ([{"breed": "NoCoords"}], [], "Lat/Long columns not found in data."),
    ([{"location_lat": 30.0, "location_long": -97.0}], [5], "Selected row is out of range."),
    ([{"location_lat": "NaN", "location_long": -97.0}], [0], "Selected row has invalid coordinates."),
])
def test_map_guards_edge_cases(view, sel, expected):
    assert validate_map_inputs(view, sel) == expected
