from flask import Blueprint, request, jsonify
from .db import db
from .utils import to_json  # converts ObjectId → string

routes = Blueprint("routes", __name__)

# when get idea --> can change what item is + how to store it
@routes.route("/items", methods=["GET"])
def get_items():
    docs = list(db.items.find({}))
    return jsonify([to_json(d) for d in docs])

@routes.route("/items", methods=["POST"])
def create_item():
    item = request.json
    result = db.items.insert_one(item)
    saved = db.items.find_one({"_id": result.inserted_id})
    return jsonify(to_json(saved)), 201

