from flask import Flask, request, jsonify
from pymongo import MongoClient
import os
from service.logic import compute_recommendations

MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongo:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "main_db")

client = MongoClient(MONGO_URL)
db = client[MONGO_DB_NAME]

# when decide idea --> change item_x to whatever 
def create_app():
    app = Flask(__name__)

    @app.route("/")
    def home():
        return {"status": "service working"}

    @app.route("/recommend")
    def recommend():
        item_x = request.args.get("item_x")
        if not item_x:
            return jsonify({"error": "item_x is required"}), 400

        recs = compute_recommendations(db, item_x)
        return jsonify(recs)

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8100)
