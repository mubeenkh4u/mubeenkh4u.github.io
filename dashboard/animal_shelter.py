# animal_shelter.py
from typing import Any, Dict, List
import os
import logging
import json
from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# --- central logging (root logger kept simple as requested) ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(asctime)s %(message)s")
logger = logging.getLogger("animal_shelter")
logger.info("animal_shelter module loaded")

# --- minimal in-memory cache (Algorithms & DS enhancement) ---
# Caches read() results by normalized query. Cleared on create/update/delete.
_cache: Dict[str, List[Dict[str, Any]]] = {}

def _cache_key(q: Dict[str, Any]) -> str:
    """Stable, JSON-based cache key for a MongoDB filter dict."""
    try:
        return json.dumps(q or {}, sort_keys=True, default=str)
    except Exception:
        # Fallback to str; still provides benefit in typical cases
        return str(q)

def _cache_get(q: Dict[str, Any]):
    return _cache.get(_cache_key(q))

def _cache_put(q: Dict[str, Any], docs: List[Dict[str, Any]]):
    _cache[_cache_key(q)] = docs

def cache_clear() -> None:
    """Public helper to flush the module cache from notebooks/UI."""
    _cache.clear()

# --- local exception for friendly, predictable error handling ---
class AnimalShelterError(Exception):
    """Raised for predictable, user-facing errors in AnimalShelter operations."""
    pass

# --- filter validator (module-level so class methods can call it) ---
def _validate_filter(filter_: Dict[str, Any], allow_empty: bool = False) -> None:
    """
    Validate MongoDB filter dictionaries.
    - When allow_empty=True, {} (or None) is permitted (e.g., read all docs).
    - Always blocks top-level $-operators for safety in student contexts.
    """
    if filter_ is None:
        if allow_empty:
            return
        raise AnimalShelterError("Filter must be a non-empty dictionary.")

    if not isinstance(filter_, dict):
        raise AnimalShelterError("Filter must be a non-empty dictionary.")

    if not filter_:
        if allow_empty:
            return
        raise AnimalShelterError("Filter must be a non-empty dictionary.")

    for k in filter_.keys():
        if str(k).startswith("$"):
            raise AnimalShelterError("Top-level query operators are not allowed.")

# --- optional DataFrame helper (Algorithms & DS enhancement) ---
def coerce_lat_long(df):
    """Coerce location_lat/location_long to numeric to avoid NaNs breaking maps.

    Usage in notebooks:
        from animal_shelter import coerce_lat_long
        df = coerce_lat_long(df)
    """
    try:
        import pandas as pd  # local import to avoid hard dependency here
    except Exception:
        return df
    for c in ["location_lat", "location_long"]:
        if hasattr(df, "columns") and c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    return df


# -------------------------
# NEW: Validation (Pydantic)
# -------------------------
from typing import Optional, Literal, Tuple
from datetime import date
from pydantic import BaseModel, Field, field_validator

GeoType = Literal["Point"]

class GeoJSONPoint(BaseModel):
    type: GeoType = "Point"
    coordinates: Tuple[float, float]  # (lon, lat)

    @field_validator("coordinates")
    @classmethod
    def validate_lon_lat(cls, v: Tuple[float, float]):
        if len(v) != 2:
            raise ValueError("coordinates must be (lon, lat)")
        lon, lat = v
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("invalid lon/lat range")
        return v

class Animal(BaseModel):
    """
    Flexible model for CSV-backed shelter docs.
    Fields are optional to avoid breaking existing data loads/tests.
    Accepts either 'species' or 'type' (alias) as many CS-340 datasets use 'type'.
    Extra fields are allowed (we don't want to reject CSV columns you don't map yet).
    """
    name: Optional[str] = None
    species: Optional[str] = None
    type: Optional[str] = Field(default=None, alias="type")
    breed: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=0, le=50)
    adopted: Optional[bool] = None
    intake_date: Optional[date] = None
    city: Optional[str] = None
    state: Optional[str] = None
    location: Optional[GeoJSONPoint] = None

    model_config = {
        "extra": "allow",
        "populate_by_name": True
    }

class AnimalUpdate(BaseModel):
    name: Optional[str] = None
    species: Optional[str] = None
    type: Optional[str] = Field(default=None, alias="type")
    breed: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=0, le=50)
    adopted: Optional[bool] = None
    intake_date: Optional[date] = None
    city: Optional[str] = None
    state: Optional[str] = None
    location: Optional[GeoJSONPoint] = None

    model_config = {
        "extra": "allow",
        "populate_by_name": True
    }

    def mongo_set(self) -> dict:
        """Build a $set update only for provided fields (safe, minimal updates)."""
        payload = {k: v for k, v in self.model_dump(by_alias=True).items() if v is not None}
        return {"$set": payload} if payload else {}


class AnimalShelter:
    """CRUD operations for Animal collection in MongoDB.

    Enhancements:
        - Docstrings and type hints for clarity and professional quality.
        - Central logging with friendly error messages printed for the UI.
        - Optional env-driven configuration:
            * MONGO_URI (e.g., 'mongodb://user:pass@host:27017/db?authSource=db')
            * MONGO_DB  (overrides DB)
            * MONGO_COLL (overrides COL)
        - Quick connectivity check (ping) and short timeouts to fail fast.
        - Safe query/update validation and CS-340-friendly read({}) behavior.
        - Minimal in-memory cache for read() results; invalidated on writes.
        - NEW (Milestone 3): Pydantic validation for create/updates and index creation.
        - NEW (Milestone 3): Server-side aggregations and optional geospatial helper.
    """

    def __init__(self, username: str = 'aacuser', password: str = 'MAK1234') -> None:
        """Initialize client and bind to database/collection.

        Args:
            username: Username for MongoDB when not using MONGO_URI.
            password: Password for MongoDB when not using MONGO_URI.
        """
        # USER = 'aacuser'
        # PASS = 'MAK1234'
        HOST = '127.0.0.1'
        PORT = 27017
        DB = 'aac'
        COL = 'animals'

        # Allow env to override connection details (non-breaking)
        uri_env = os.getenv("MONGO_URI")
        db_env = os.getenv("MONGO_DB")
        coll_env = os.getenv("MONGO_COLL")

        try:
            if uri_env:
                # Use env-provided URI; optional DB/COL overrides below
                self.client = MongoClient(
                    uri_env,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                )
                logger.info("Connecting with MONGO_URI")
            else:
                # Original connection style preserved
                self.client = MongoClient(
                    f'mongodb://{username}:{password}@{HOST}:{PORT}/aac?authSource=aac',
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                )
                logger.info("Connecting with username/password/host/port")

            # Fail fast if server not reachable
            self.client.admin.command("ping")
            logger.info("MongoDB ping successful")

            # Respect original names; allow env overrides for DB and collection
            use_db = db_env if db_env else DB
            use_coll = coll_env if coll_env else COL

            self.database = self.client[use_db]
            self.collection = self.database[use_coll]
            logger.info("Connected to MongoDB | db=%s coll=%s", use_db, use_coll)

            # NEW: ensure indexes on startup (idempotent)
            self._ensure_indexes()

            # NEW: optionally apply a $jsonSchema validator on startup
            try:
                apply_flag = os.getenv("MONGO_APPLY_VALIDATOR", "0").lower() in ("1", "true", "yes", "on")
                if apply_flag:
                    if self.apply_collection_validator():
                        logger.info("Collection validator applied on startup.")
                    else:
                        logger.warning("Validator apply attempted but returned False.")
                else:
                    logger.debug("MONGO_APPLY_VALIDATOR is off; skipping validator.")
            except Exception:
                # Non-fatal: validator may require specific privileges or MongoDB version
                logger.warning("Validator apply skipped due to exception", exc_info=True)

        except PyMongoError as e:
            # Friendly UI message + central logging
            print(f"Error connecting to MongoDB: {e}")
            logger.exception("Error connecting to MongoDB")
            self.database = None
            self.collection = None

    # -----------------------------
    # NEW: indexes & small utilities
    # -----------------------------
    def _ensure_indexes(self):
        """Create indexes aligned with common filters. Safe to call repeatedly."""
        if self.collection is None:
            return
        try:
            self.collection.create_index([("species", 1)])
            self.collection.create_index([("breed", 1)])
            self.collection.create_index([("city", 1), ("state", 1)])
            self.collection.create_index([("adopted", 1)])
            # Geo index (optional; harmless if you don't use location yet)
            self.collection.create_index([("location", "2dsphere")])
        except PyMongoError as e:
            logger.warning("Index creation warning: %s", e)

    @staticmethod
    def _clean_id(doc: dict) -> dict:
        """Convert ObjectId to str for UI safety."""
        if not doc or "_id" not in doc:
            return doc
        d = dict(doc)
        try:
            if isinstance(d["_id"], ObjectId):
                d["_id"] = str(d["_id"])
        except Exception:
            pass
        return d

    # -----------------------------
    # NEW: DB-level validator helper
    # -----------------------------
    def apply_collection_validator(self) -> bool:
        """
        Apply/refresh a MongoDB $jsonSchema validator on the collection.
        Uses 'moderate' so existing docs pass but new/updated docs are checked.
        Returns True on success, False otherwise.
        """
        if self.collection is None:
            print("Validator error: No database connection.")
            logger.error("Validator attempted without a database connection")
            return False

        # MongoDB $jsonSchema (keeps extras allowed; no 'additionalProperties': false)
        schema = {
            "bsonType": "object",
            "properties": {
                "name":   {"bsonType": ["string", "null"]},
                "species":{"bsonType": ["string", "null"]},
                "type":   {"bsonType": ["string", "null"]},  # many CS-340 datasets use 'type'
                "breed":  {"bsonType": ["string", "null"]},
                "adopted":{"bsonType": ["bool", "null"]},
                "intake_date": {"bsonType": ["date", "string", "null"]},

                # CS-340 common fields for your filters
                "sex_upon_outcome": {"bsonType": ["string", "null"]},
                "age_upon_outcome_in_weeks": {"bsonType": ["int", "long", "double", "null"], "minimum": 0},

                # Optional geo (GeoJSON)
                "location": {
                    "bsonType": ["object", "null"],
                    "required": ["type", "coordinates"],
                    "properties": {
                        "type": {"enum": ["Point"]},
                        "coordinates": {
                            "bsonType": "array",
                            "items": [{"bsonType": "double"}, {"bsonType": "double"}],
                            "minItems": 2, "maxItems": 2
                        }
                    }
                },

                # Your current notebook mapping columns (leaflet fallback)
                "location_lat":  {"bsonType": ["double", "int", "long", "null"]},
                "location_long": {"bsonType": ["double", "int", "long", "null"]},

                # Common city/state fields (optional)
                "city":  {"bsonType": ["string", "null"]},
                "state": {"bsonType": ["string", "null"]},
            }
        }

        try:
            self.database.command({
                "collMod": self.collection.name,
                "validator": {"$jsonSchema": schema},
                "validationLevel": "moderate"   # check inserts/updates; don't fail on old docs
            })
            logger.info("Applied collection validator to %s", self.collection.name)
            return True
        except PyMongoError as e:
            print(f"Validator apply error: {e}")
            logger.exception("Validator apply error")
            return False

    def create(self, data: Dict[str, Any]) -> bool:
        """Insert a document into the collection.

        Args:
            data: Document to insert.

        Returns:
            True if insert acknowledged; False otherwise.
        """
        if self.collection is None:
            print("Insert error: No database connection.")
            logger.error("Insert attempted without a database connection")
            return False

        if not data:
            # Preserve original behavior (raise on empty), plus log
            logger.error("Empty data passed to create()")
            raise ValueError("Empty data cannot be inserted.")

        # Friendly guardrail: reject blatantly unsafe keys (leaves structure intact)
        if any(isinstance(k, str) and k.startswith("$") for k in data.keys()):
            print("Insert error: Document keys cannot start with '$'.")
            logger.error("Insert rejected due to $-prefixed keys in document")
            return False

        try:
            # NEW: validate & normalize payload via Pydantic (allows extra fields)
            doc = Animal(**data).model_dump(by_alias=True)

            result = self.collection.insert_one(doc)
            # Invalidate cache on write
            cache_clear()
            return bool(getattr(result, "acknowledged", False))
        except PyMongoError as e:
            print(f"Insert error: {e}")
            logger.exception("Insert error")
            return False
        except Exception as e:
            # Validation or coercion error
            print(f"Insert error: {e}")
            logger.exception("Insert error (validation)")
            return False

    def read(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query documents based on key/value lookup.

        Args:
            query: MongoDB filter; {} allowed to return all documents.

        Returns:
            List of matching documents; [] on error.
        """
        if self.collection is None:
            print("Query error: No database connection.")
            logger.error("Read attempted without a database connection")
            return []

        # Allow {} (or None) to mean "all documents" for CS-340 compatibility
        if query is None or (isinstance(query, dict) and not query):
            query_to_use = {}
        else:
            # Guardrail: block top-level operators that can be risky in student contexts
            try:
                _validate_filter(query, allow_empty=False)
            except AnimalShelterError as e:
                print(f"Query error: {e}")
                logger.error("Read rejected due to unsafe filter: %s", e)
                return []
            query_to_use = query

        # --- Cache lookup (Algorithms & DS enhancement) ---
        cached = _cache_get(query_to_use)
        if cached is not None:
            logger.info("Cache hit for query")
            return cached

        try:
            results = list(self.collection.find(query_to_use))
            # NEW: stringify _id so UI elements (DataTable) never crash
            results = [self._clean_id(r) for r in results]
            _cache_put(query_to_use, results)
            return results
        except PyMongoError as e:
            print(f"Query error: {e}")
            logger.exception("Query error")
            return []

    def update(self, query: Dict[str, Any], new_values: Dict[str, Any]) -> bool:
        """
        Updates one document that matches the query with new values.

        Parameters:
            query (dict): The filter to locate the document.
            new_values (dict): The fields to update, e.g., {"$set": {"name": "Updated Name"}}

        Returns:
            True if a document was updated, False otherwise.
        """
        if self.collection is None:
            print("Update error: No database connection.")
            logger.error("Update attempted without a database connection")
            return False

        # Require non-empty, safe filter
        try:
            _validate_filter(query, allow_empty=False)
        except AnimalShelterError as e:
            print(f"Update error: {e}")
            logger.error("Update rejected due to unsafe filter: %s", e)
            return False

        # Allow only a safe subset of update operators
        allowed_ops = {"$set", "$unset", "$inc", "$push", "$pull"}
        if not isinstance(new_values, dict) or not new_values:
            print("Update error: Update document must be a non-empty dict.")
            logger.error("Update rejected due to empty or non-dict update document")
            return False
        if any(op not in allowed_ops for op in new_values.keys()):
            print(f"Update error: Only {sorted(allowed_ops)} are allowed in updates.")
            logger.error("Update rejected due to disallowed update operator(s)")
            return False
        # Disallow $-prefixed field keys inside the update payloads
        for payload in new_values.values():
            if isinstance(payload, dict) and any(isinstance(k, str) and k.startswith("$") for k in payload.keys()):
                print("Update error: Field names inside update payloads cannot start with '$'.")
                logger.error("Update rejected due to $-prefixed field in payload")
                return False

        try:
            result = self.collection.update_one(query, new_values)
            # Invalidate cache on write
            cache_clear()
            return result.modified_count > 0
        except PyMongoError as e:
            print(f"Update error: {e}")
            logger.exception("Update error")
            return False
        except Exception as e:
            # Preserve original broad catch behavior, but log centrally too
            print(f"Update error: {e}")
            logger.exception("Update error (generic)")
            return False

    def delete(self, query: Dict[str, Any]) -> bool:
        """Delete one document that matches the query.

        Args:
            query: MongoDB filter for the document to delete.

        Returns:
            True if a document was deleted; False otherwise.
        """
        if self.collection is None:
            print("Delete error: No database connection.")
            logger.error("Delete attempted without a database connection")
            return False

        # Require non-empty, safe filter
        try:
            _validate_filter(query, allow_empty=False)
        except AnimalShelterError as e:
            print(f"Delete error: {e}")
            logger.error("Delete rejected due to unsafe filter: %s", e)
            return False

        try:
            result = self.collection.delete_one(query)
            # Invalidate cache on write
            cache_clear()
            return result.deleted_count > 0  # Returns True if a document was deleted
        except PyMongoError as e:
            print(f"Delete error: {e}")
            logger.exception("Delete error")
            return False
        except Exception as e:
            print(f"Delete error: {e}")
            logger.exception("Delete error (generic)")
            return False

    # ----------------------------------
    # NEW: server-side analytics helpers
    # ----------------------------------
    def top_breeds(self, base_filter: dict | None = None, k: int = 10) -> list[dict]:
        """Return top-k breeds with counts using MongoDB aggregation pipeline.

        Args:
            base_filter: Optional MongoDB filter (same shape used in read()).
            k: Limit for number of breeds returned.

        Returns:
            List like: [{"breed": "Labrador Retriever", "count": 42}, ...]
        """
        if self.collection is None:
            return []
        try:
            pipe = [
                {"$match": base_filter or {}},
                {"$group": {"_id": "$breed", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": int(k)},
            ]
            rows = list(self.collection.aggregate(pipe))
            return [{"breed": r.get("_id"), "count": r.get("count", 0)} for r in rows if r.get("_id")]
        except PyMongoError as e:
            print(f"Aggregation error: {e}")
            logger.exception("Aggregation error")
            return []

    # --------------------------------
    # NEW: optional geospatial helper
    # --------------------------------
    def near(self, lon: float, lat: float, max_meters: int = 5000, limit: int = 100) -> list[dict]:
        """Geo query for documents within a radius of a point. Requires 2dsphere index.

        Args:
            lon: Longitude (x).
            lat: Latitude (y).
            max_meters: Maximum distance from the point in meters.
            limit: Result cap.

        Returns:
            List of matching documents, with stringified _id.
        """
        if self.collection is None:
            return []
        q = {
            "location": {
                "$near": {
                    "$geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "$maxDistance": max_meters,
                }
            }
        }
        try:
            cursor = self.collection.find(q).limit(limit)
            return [self._clean_id(x) for x in cursor]
        except PyMongoError as e:
            print(f"Geo query error: {e}")
            logger.exception("Geo query error")
            return []
