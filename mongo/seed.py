import json
import os
from pymongo import MongoClient

MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongo:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "main_db")

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

seed_path = os.path.join(os.path.dirname(__file__), "seed_data.json")

with open(seed_path) as f:
    data = json.load(f)

for collection_name, docs in data.items():
    if isinstance(docs, list):
        db[collection_name].delete_many({})
        db[collection_name].insert_many(docs)

print("Seeded database successfully.")
