from flask import Flask, request, jsonify
from pymongo import MongoClient
import os
from service.logic import analyze_supplies, analyze_rent

MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongo:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "main_db")

client = MongoClient(MONGO_URL)
db = client[MONGO_DB_NAME]


def create_app():
    app = Flask(__name__)

    @app.route("/")
    def home():
        return {"status": "api working"}

    @app.route("/supplies-status")
    def supplies_status():
        group_name = request.args.get("group_name")
        if not group_name:
            return {"error": "group_name required"}, 400

        results = analyze_supplies(db, group_name)
        return jsonify(results)


    @app.route("/rent-status")
    def rent_status():
        group_name = request.args.get("group_name")
        if not group_name:
            return {"error": "group_name required"}, 400

        results = analyze_rent(db, group_name)
        return jsonify(results)


    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
