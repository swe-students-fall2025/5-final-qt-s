from flask import Blueprint, request, jsonify
from .db import db
from .utils import to_json  # converts ObjectId → string
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import os
from datetime import datetime, timedelta

routes = Blueprint("routes", __name__)

# User Account Routes
@routes.route("/users", methods=["POST"])
def create_user():
    """Create a new user account"""
    data = request.json
    required_fields = ["username", "email", "password"]
    
    # Validate required fields
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields: username, email, password"}), 400
    
    # Check if user already exists
    existing_user = db.users.find_one({"$or": [{"username": data["username"]}, {"email": data["email"]}]})
    if existing_user:
        return jsonify({"error": "User with this username or email already exists"}), 409
    
    # Hash the password before saving
    password_hash = generate_password_hash(data["password"])
    
    # Create user document
    user = {
        "username": data["username"],
        "email": data["email"],
        "password_hash": password_hash,
        "full_name": data.get("full_name", ""),
        "phone": data.get("phone", ""),
        "created_at": data.get("created_at")  # Can be set by client or use default
    }
    
    result = db.users.insert_one(user)
    saved = db.users.find_one({"_id": result.inserted_id})
    saved_json = to_json(saved)
    # Remove password_hash from response for security
    saved_json.pop("password_hash", None)
    return jsonify(saved_json), 201

@routes.route("/login", methods=["POST"])
def login():
    """Login user and return JWT token for multi-device access"""
    data = request.json
    
    if not data or "password" not in data:
        return jsonify({"error": "Missing required fields: username/email and password"}), 400
    
    # User can login with either username or email
    username_or_email = data.get("username") or data.get("email")
    password = data.get("password")
    
    if not username_or_email:
        return jsonify({"error": "Must provide username or email"}), 400
    
    # Find user by username or email
    user = db.users.find_one({"$or": [{"username": username_or_email}, {"email": username_or_email}]})
    
    if not user:
        return jsonify({"error": "Invalid username/email or password"}), 401
    
    # Check password
    if not check_password_hash(user.get("password_hash", ""), password):
        return jsonify({"error": "Invalid username/email or password"}), 401
    
    # Generate JWT token
    jwt_secret = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
    token_payload = {
        "user_id": str(user["_id"]),
        "username": user["username"],
        "exp": datetime.utcnow() + timedelta(days=7)  # Token expires in 7 days
    }
    token = jwt.encode(token_payload, jwt_secret, algorithm="HS256")
    
    return jsonify({
        "token": token,
        "user_id": str(user["_id"]),
        "username": user["username"]
    }), 200

@routes.route("/users/<user_id>", methods=["GET"])
def get_user(user_id):
    """Get a user by ID"""
    try:
        user = db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"error": "User not found"}), 404
        user_json = to_json(user)
        # Remove password_hash from response for security
        user_json.pop("password_hash", None)
        return jsonify(user_json), 200
    except Exception as e:
        return jsonify({"error": "Invalid user ID"}), 400

@routes.route("/users", methods=["GET"])
def get_users():
    """Get all users (optional: filter by username or email)"""
    username = request.args.get("username")
    email = request.args.get("email")
    
    query = {}
    if username:
        query["username"] = username
    if email:
        query["email"] = email
    
    users = list(db.users.find(query))
    users_json = [to_json(u) for u in users]
    # Remove password_hash from each user for security
    for user in users_json:
        user.pop("password_hash", None)
    return jsonify(users_json), 200

# Group/Roommate Group Routes
@routes.route("/groups", methods=["POST"])
def create_group():
    """Create a new roommate group"""
    data = request.json
    required_fields = ["name", "created_by"]
    
    # Validate required fields
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields: name, created_by"}), 400
    
    # Validate that created_by user exists
    try:
        creator = db.users.find_one({"_id": ObjectId(data["created_by"])})
        if not creator:
            return jsonify({"error": "Creator user not found"}), 404
    except Exception:
        return jsonify({"error": "Invalid created_by user ID"}), 400
    
    # Create group document
    group = {
        "name": data["name"],
        "created_by": data["created_by"],
        "description": data.get("description", ""),
        "roommates": [data["created_by"]],  # Creator is automatically added as roommate
        "created_at": data.get("created_at")
    }
    
    result = db.groups.insert_one(group)
    saved = db.groups.find_one({"_id": result.inserted_id})
    return jsonify(to_json(saved)), 201

@routes.route("/groups/<group_id>", methods=["GET"])
def get_group(group_id):
    """Get a group by ID"""
    try:
        group = db.groups.find_one({"_id": ObjectId(group_id)})
        if not group:
            return jsonify({"error": "Group not found"}), 404
        return jsonify(to_json(group)), 200
    except Exception as e:
        return jsonify({"error": "Invalid group ID"}), 400

@routes.route("/groups", methods=["GET"])
def get_groups():
    """Get all groups (optional: filter by created_by or roommates)"""
    created_by = request.args.get("created_by")
    roommate_id = request.args.get("roommate_id")
    
    query = {}
    if created_by:
        try:
            query["created_by"] = created_by
        except Exception:
            pass
    if roommate_id:
        query["roommates"] = roommate_id
    
    groups = list(db.groups.find(query))
    return jsonify([to_json(g) for g in groups]), 200

@routes.route("/groups/<group_id>/roommates", methods=["POST"])
def add_roommate(group_id):
    """Add a roommate to a group"""
    try:
        group = db.groups.find_one({"_id": ObjectId(group_id)})
        if not group:
            return jsonify({"error": "Group not found"}), 404
    except Exception:
        return jsonify({"error": "Invalid group ID"}), 400
    
    data = request.json
    if "user_id" not in data:
        return jsonify({"error": "Missing required field: user_id"}), 400
    
    user_id = data["user_id"]
    
    # Validate that user exists
    try:
        user = db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return jsonify({"error": "User not found"}), 404
    except Exception:
        return jsonify({"error": "Invalid user ID"}), 400
    
    # Check if user is already a roommate
    if user_id in group.get("roommates", []):
        return jsonify({"error": "User is already a roommate in this group"}), 409
    
    # Add roommate
    db.groups.update_one(
        {"_id": ObjectId(group_id)},
        {"$addToSet": {"roommates": user_id}}
    )
    
    updated_group = db.groups.find_one({"_id": ObjectId(group_id)})
    return jsonify(to_json(updated_group)), 200

@routes.route("/groups/<group_id>/roommates/<user_id>", methods=["DELETE"])
def remove_roommate(group_id, user_id):
    """Remove a roommate from a group"""
    try:
        group = db.groups.find_one({"_id": ObjectId(group_id)})
        if not group:
            return jsonify({"error": "Group not found"}), 404
        
        # Check if user is a roommate
        if user_id not in group.get("roommates", []):
            return jsonify({"error": "User is not a roommate in this group"}), 404
        
        # Don't allow removing the creator
        if user_id == group.get("created_by"):
            return jsonify({"error": "Cannot remove the group creator"}), 403
        
        # Remove roommate
        db.groups.update_one(
            {"_id": ObjectId(group_id)},
            {"$pull": {"roommates": user_id}}
        )
        
        updated_group = db.groups.find_one({"_id": ObjectId(group_id)})
        return jsonify(to_json(updated_group)), 200
    except Exception:
        return jsonify({"error": "Invalid group ID or user ID"}), 400

