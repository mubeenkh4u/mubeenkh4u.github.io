# animal_shelter.py
from typing import Any, Dict, List
import os
import logging
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# --- central logging (root logger kept simple as requested) ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(asctime)s %(message)s")
logger = logging.getLogger("animal_shelter")
logger.info("animal_shelter module loaded")

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

        except PyMongoError as e:
            # Friendly UI message + central logging
            print(f"Error connecting to MongoDB: {e}")
            logger.exception("Error connecting to MongoDB")
            self.database = None
            self.collection = None

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
            result = self.collection.insert_one(data)
            return bool(getattr(result, "acknowledged", False))
        except PyMongoError as e:
            print(f"Insert error: {e}")
            logger.exception("Insert error")
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

        try:
            results = self.collection.find(query_to_use)
            return list(results)
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
            return result.deleted_count > 0  # Returns True if a document was deleted
        except PyMongoError as e:
            print(f"Delete error: {e}")
            logger.exception("Delete error")
            return False
        except Exception as e:
            print(f"Delete error: {e}")
            logger.exception("Delete error (generic)")
            return False
