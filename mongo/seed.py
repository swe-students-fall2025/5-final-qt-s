import json
import os
from pymongo import MongoClient

MONGO_URL = os.getenv(
    "MONGO_URL",
    "mongodb+srv://jrc9921_db_user:Xpg3EjVGFbv3Waeh@work.5foblwa.mongodb.net/?retryWrites=true&w=majority"
)
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
