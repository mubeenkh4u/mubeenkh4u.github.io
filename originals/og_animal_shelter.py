# animal_shelter.py
from pymongo import MongoClient
from pymongo.errors import PyMongoError

class AnimalShelter:
    """ CRUD operations for Animal collection in MongoDB """

    def __init__(self, username='aacuser', password='MAK1234'):
        # USER = 'aacuser'
        # PASS = 'MAK1234'
        HOST = '127.0.0.1'
        PORT = 27017
        DB = 'aac'
        COL = 'animals'
        try:
            self.client = MongoClient(f'mongodb://{username}:{password}@{HOST}:{PORT}/aac?authSource=aac')
            self.database = self.client[DB]
            self.collection = self.database[COL]
        except PyMongoError as e:
            print(f"Error connecting to MongoDB: {e}")

    def create(self, data):
        """Insert a document into the collection."""
        if data:
            try:
                result = self.collection.insert_one(data)
                return result.acknowledged
            except PyMongoError as e:
                print(f"Insert error: {e}")
                return False
        else:
            raise ValueError("Empty data cannot be inserted.")

    def read(self, query):
        """Query documents based on key/value lookup."""
        try:
            results = self.collection.find(query)
            return list(results)
        except PyMongoError as e:
            print(f"Query error: {e}")
            return []
    
    def update(self, query, new_values):
        """
        Updates one document that matches the query with new values.
        
        Parameters:
            query (dict): The filter to locate the document.
            new_values (dict): The fields to update, e.g., {"$set": {"name": "Updated Name"}}
        
        Returns:
            True if a document was updated, False otherwise.
        """
        try:
            result = self.collection.update_one(query, new_values)
            return result.modified_count > 0
        except Exception as e:
            print(f"Update error: {e}")
            return False
     
    def delete(self, query):
        """Delete one document that matches the query."""
        try:
            result = self.collection.delete_one(query)
            return result.deleted_count > 0  # Returns True if a document was deleted
        except Exception as e:
            print(f"Delete error: {e}")
            return False
