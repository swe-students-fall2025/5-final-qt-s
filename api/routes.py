from flask import Blueprint, request, jsonify
from .db import db
from .utils import to_json  # converts ObjectId → string
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import os
from datetime import datetime, timedelta
from service.logic import analyze_chores, mark_chore_complete, get_group_calendar

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
        "created_by_username": creator.get("username", ""),  # Store username for easy display
        "description": data.get("description", ""),
        "roommates": [data["created_by"]],  # Creator is automatically added as roommate
        "created_at": data.get("created_at")
    }
    
    result = db.groups.insert_one(group)
    saved = db.groups.find_one({"_id": result.inserted_id})
    saved_json = to_json(saved)
    # Include username in response for display
    saved_json["created_by_username"] = creator.get("username", "")
    return jsonify(saved_json), 201

@routes.route("/groups/<group_id>", methods=["GET"])
def get_group(group_id):
    """Get a group by ID with roommates info"""
    try:
        group = db.groups.find_one({"_id": ObjectId(group_id)})
        if not group:
            return jsonify({"error": "Group not found"}), 404
        
        group_json = to_json(group)
        
        # Get roommate usernames
        roommate_ids = group.get("roommates", [])
        roommates_info = []
        for rm_id in roommate_ids:
            try:
                user = db.users.find_one({"_id": ObjectId(rm_id)})
                if user:
                    roommates_info.append({
                        "user_id": rm_id,
                        "username": user.get("username", ""),
                        "email": user.get("email", "")
                    })
            except Exception:
                pass
        
        group_json["roommates_info"] = roommates_info
        return jsonify(group_json), 200
    except Exception as e:
        return jsonify({"error": "Invalid group ID"}), 400

@routes.route("/groups", methods=["GET"])
def get_groups():
    """Get all groups (optional: filter by created_by or roommates) with roommates info"""
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
    groups_json = []
    for g in groups:
        group_json = to_json(g)
        # If username not stored, look it up
        if not group_json.get("created_by_username") and group_json.get("created_by"):
            try:
                creator = db.users.find_one({"_id": ObjectId(group_json["created_by"])})
                if creator:
                    group_json["created_by_username"] = creator.get("username", "")
            except Exception:
                pass
        
        # Get roommate usernames
        roommate_ids = g.get("roommates", [])
        roommates_info = []
        for rm_id in roommate_ids:
            try:
                user = db.users.find_one({"_id": ObjectId(rm_id)})
                if user:
                    roommates_info.append({
                        "user_id": rm_id,
                        "username": user.get("username", ""),
                        "email": user.get("email", "")
                    })
            except Exception:
                pass
        
        group_json["roommates_info"] = roommates_info
        groups_json.append(group_json)
    return jsonify(groups_json), 200

@routes.route("/groups/<group_id>/roommates", methods=["POST"])
def add_roommate(group_id):
    """Send an invitation to join a group. Accepts user_id, email, or username."""
    try:
        group = db.groups.find_one({"_id": ObjectId(group_id)})
        if not group:
            return jsonify({"error": "Group not found"}), 404
    except Exception:
        return jsonify({"error": "Invalid group ID"}), 400
    
    data = request.json
    if "user_id" not in data:
        return jsonify({"error": "Missing required field: user_id"}), 400
    
    user_identifier = data["user_id"].strip()
    inviter_id = data.get("inviter_id")  # Who is sending the invitation
    
    # Try to find user by ID, email, or username
    user = None
    try:
        # First try as ObjectId
        user = db.users.find_one({"_id": ObjectId(user_identifier)})
    except Exception:
        pass
    
    # If not found by ID, try email or username
    if not user:
        user = db.users.find_one({
            "$or": [
                {"email": user_identifier},
                {"username": user_identifier}
            ]
        })
    
    if not user:
        return jsonify({"error": "User not found. Please check the user ID, email, or username."}), 404
    
    # Get the actual user_id as string
    user_id = str(user["_id"])
    
    # Check if user is already a roommate
    if user_id in group.get("roommates", []):
        return jsonify({"error": "User is already a roommate in this group"}), 409
    
    # Check if invitation already exists
    existing_invite = db.group_invitations.find_one({
        "group_id": group_id,
        "invited_user_id": user_id,
        "status": "pending"
    })
    
    if existing_invite:
        return jsonify({"error": "Invitation already sent to this user"}), 409
    
    # Create invitation
    invitation = {
        "group_id": group_id,
        "group_name": group.get("name", ""),
        "invited_user_id": user_id,
        "invited_username": user.get("username", ""),
        "inviter_id": inviter_id,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    db.group_invitations.insert_one(invitation)
    
    return jsonify({
        "message": f"Invitation sent to {user.get('username', 'user')}",
        "invitation_id": str(invitation["_id"])
    }), 201

@routes.route("/groups/<group_id>/roommates/<user_id>/accept", methods=["POST"])
def accept_invitation(group_id, user_id):
    """Accept a group invitation and add user to group"""
    try:
        # Find pending invitation
        invitation = db.group_invitations.find_one({
            "group_id": group_id,
            "invited_user_id": user_id,
            "status": "pending"
        })
        
        if not invitation:
            return jsonify({"error": "Invitation not found or already processed"}), 404
        
        # Get group
        group = db.groups.find_one({"_id": ObjectId(group_id)})
        if not group:
            return jsonify({"error": "Group not found"}), 404
        
        # Check if user is already a roommate
        if user_id in group.get("roommates", []):
            # Mark invitation as accepted anyway
            db.group_invitations.update_one(
                {"_id": invitation["_id"]},
                {"$set": {"status": "accepted"}}
            )
            return jsonify({"error": "User is already a roommate in this group"}), 409
        
        # Add roommate to group
        db.groups.update_one(
            {"_id": ObjectId(group_id)},
            {"$addToSet": {"roommates": user_id}}
        )
        
        # Mark invitation as accepted
        db.group_invitations.update_one(
            {"_id": invitation["_id"]},
            {"$set": {"status": "accepted", "accepted_at": datetime.now().isoformat()}}
        )
        
        updated_group = db.groups.find_one({"_id": ObjectId(group_id)})
        return jsonify(to_json(updated_group)), 200
    except Exception as e:
        return jsonify({"error": f"Invalid group ID or user ID: {str(e)}"}), 400

@routes.route("/groups/<group_id>/roommates/<user_id>/decline", methods=["POST"])
def decline_invitation(group_id, user_id):
    """Decline a group invitation"""
    try:
        invitation = db.group_invitations.find_one({
            "group_id": group_id,
            "invited_user_id": user_id,
            "status": "pending"
        })
        
        if not invitation:
            return jsonify({"error": "Invitation not found or already processed"}), 404
        
        # Mark invitation as declined
        db.group_invitations.update_one(
            {"_id": invitation["_id"]},
            {"$set": {"status": "declined", "declined_at": datetime.now().isoformat()}}
        )
        
        return jsonify({"message": "Invitation declined"}), 200
    except Exception:
        return jsonify({"error": "Invalid group ID or user ID"}), 400

@routes.route("/invitations", methods=["GET"])
def get_invitations():
    """Get pending invitations for the current user"""
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    
    invitations = list(db.group_invitations.find({
        "invited_user_id": user_id,
        "status": "pending"
    }))
    
    # Enrich with group and inviter info
    invitations_json = []
    for inv in invitations:
        inv_json = to_json(inv)
        # Get group info
        try:
            group = db.groups.find_one({"_id": ObjectId(inv["group_id"])})
            if group:
                inv_json["group"] = {
                    "id": str(group["_id"]),
                    "name": group.get("name", ""),
                    "created_by_username": group.get("created_by_username", "")
                }
        except Exception:
            pass
        
        # Get inviter info
        if inv.get("inviter_id"):
            try:
                inviter = db.users.find_one({"_id": ObjectId(inv["inviter_id"])})
                if inviter:
                    inv_json["inviter_username"] = inviter.get("username", "")
            except Exception:
                pass
        
        invitations_json.append(inv_json)
    
    return jsonify(invitations_json), 200

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

@routes.route("/groups/<group_id>", methods=["DELETE"])
def delete_group(group_id):
    """Delete a group. Only the creator can delete it."""
    try:
        group = db.groups.find_one({"_id": ObjectId(group_id)})
        if not group:
            return jsonify({"error": "Group not found"}), 404
        
        # Get creator_id from request (should be passed from frontend)
        data = request.json or {}
        creator_id = data.get("creator_id") or request.args.get("creator_id")
        
        # Verify the requester is the creator
        if creator_id and str(group.get("created_by")) != str(creator_id):
            return jsonify({"error": "Only the group creator can delete the group"}), 403
        
        # Delete the group
        db.groups.delete_one({"_id": ObjectId(group_id)})
        
        return jsonify({"message": "Group deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": "Invalid group ID"}), 400



# Note: Routes using @app.route should be registered in app.py after blueprint import
# to avoid circular imports. These are moved to app.py.
