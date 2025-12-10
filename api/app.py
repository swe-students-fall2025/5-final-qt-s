# api/app.py
from flask import Flask, request, jsonify, render_template, send_from_directory
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import os
import time
from werkzeug.utils import secure_filename
from service.logic import analyze_supplies, analyze_rent, analyze_bills
from api.utils import to_json

# DB config
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "main_db")

client = MongoClient(MONGO_URL)
db = client[MONGO_DB_NAME]

# Create Flask app that serves templates from project root templates/
# and static from project root static/
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))

app = Flask(
    __name__,
    template_folder=os.path.join(PROJECT_ROOT, "templates"),
    static_folder=os.path.join(PROJECT_ROOT, "static"),
)

# Import and register routes blueprint (api endpoints) under /api
try:
    from .routes import routes as api_routes
    app.register_blueprint(api_routes, url_prefix="/api")
except Exception as e:
    # If routes import fails, show helpful error in logs but keep app running for template preview
    app.logger.warning("Could not register routes blueprint: %s", e)

# Simple health route
@app.route("/")
def home_page():
    # If user not logged in, route will render login page by default; show index page
    return render_template("login.html")

# Serve other top-level pages via Jinja templates
@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/register")
def register_page():
    return render_template("register.html")

@app.route("/my_groups")
def groups_page():
    return render_template("my_groups.html")

@app.route("/home")
def main_home():
    return render_template("home.html")

@app.route("/chores")
def chores_page():
    return render_template("chores.html")

@app.route("/bills")
def bills_page():
    return render_template("bills.html")

@app.route("/calendar")
def calendar_page():
    return render_template("calendar.html")

# Compatibility: keep support for older non-prefixed endpoints used by service layer
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

# Bills Routes
@app.route("/api/groups/<group_name>/members", methods=["GET"])
def get_group_members_by_name(group_name):
    """Get group members by group name"""
    try:
        group = db.groups.find_one({"name": group_name})
        if not group:
            return jsonify({"error": "Group not found"}), 404
        
        roommate_ids = group.get("roommates", [])
        roommates_info = []
        for rm_id in roommate_ids:
            try:
                user = db.users.find_one({"_id": ObjectId(rm_id)})
                if user:
                    roommates_info.append({
                        "user_id": str(rm_id),
                        "username": user.get("username", ""),
                        "email": user.get("email", "")
                    })
            except Exception:
                pass
        
        return jsonify({"members": roommates_info}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/groups/<group_name>/bills", methods=["GET", "POST"])
def bills_route(group_name):
    """Get all bills for a group or create a new bill"""
    if not group_name or group_name == "null" or group_name == "undefined":
        return jsonify({"error": "Invalid group name"}), 400
    
    if request.method == "GET":
        # Get current user ID from token
        user_id = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                import jwt
                token = auth_header.split(" ")[1]
                jwt_secret = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
                payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
                user_id = payload.get("user_id")
            except Exception:
                pass
        
        results = analyze_bills(db, group_name, user_id)
        return jsonify(results), 200
    
    else:  # POST
        try:
            data = request.json
            if not data:
                return jsonify({"error": "Invalid request data"}), 400
            
            required_fields = ["name", "amount", "due_date"]
            if not all(field in data for field in required_fields):
                return jsonify({"error": "Missing required fields: name, amount, due_date"}), 400
            
            # Verify group exists
            group = db.groups.find_one({"name": group_name})
            if not group:
                return jsonify({"error": f"Group '{group_name}' not found"}), 404
            
            # Get creator from Authorization header or request
            creator_id = None
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                try:
                    import jwt
                    token = auth_header.split(" ")[1]
                    jwt_secret = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
                    payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
                    creator_id = payload.get("user_id")
                except Exception:
                    pass
            
            # Get assigned user info if provided
            assigned_to_user_id = data.get("assigned_to")
            assigned_to_username = None
            if assigned_to_user_id:
                try:
                    assigned_user = db.users.find_one({"_id": ObjectId(assigned_to_user_id)})
                    if assigned_user:
                        assigned_to_username = assigned_user.get("username", "")
                except Exception:
                    pass
            
            bill = {
                "name": data["name"],
                "amount": float(data["amount"]),
                "due_date": data["due_date"],
                "group_name": group_name,
                "category": data.get("category", "other"),  # rent, utilities, internet, other
                "assigned_to": assigned_to_user_id,  # Who this bill belongs to
                "assigned_to_username": assigned_to_username,  # Username for display
                "paid": data.get("paid", False),
                "paid_by": data.get("paid_by"),
                "paid_at": data.get("paid_at"),
                "created_by": creator_id,  # Track who created the bill
                "is_recurring": data.get("is_recurring", False),
                "recurring_frequency": data.get("recurring_frequency"),  # daily, weekly, biweekly, monthly, yearly, custom
                "recurring_days": data.get("recurring_days"),  # For custom frequency
                "notification_frequency": data.get("notification_frequency", "daily"),
                "notification_days_before": data.get("notification_days_before"),  # Days before due date to notify
                "visibility": data.get("visibility", "all"),  # "all" or "custom"
                "visible_to": data.get("visible_to", []),  # List of user IDs who can see this bill
                "editable_visibility": data.get("editable_visibility", "only_me"),  # "only_me", "all", or "custom"
                "editable_by": data.get("editable_by", []),  # List of user IDs who can edit this bill
                "deletable_visibility": data.get("deletable_visibility", "only_me"),  # "only_me", "all", or "custom"
                "deletable_by": data.get("deletable_by", []),  # List of user IDs who can delete this bill
                "notes": data.get("notes", ""),
                "created_at": datetime.now().isoformat()
            }
            
            result = db.bills.insert_one(bill)
            saved = db.bills.find_one({"_id": result.inserted_id})
            return jsonify(to_json(saved)), 201
        except Exception as e:
            app.logger.error(f"Error creating bill: {str(e)}")
            return jsonify({"error": f"Failed to create bill: {str(e)}"}), 500

@app.route("/api/bills/<bill_id>", methods=["GET", "PATCH", "DELETE"])
def bill_route(bill_id):
    """Get, update, or delete a specific bill"""
    try:
        if request.method == "GET":
            bill = db.bills.find_one({"_id": ObjectId(bill_id)})
            if not bill:
                return jsonify({"error": "Bill not found"}), 404
            return jsonify(to_json(bill)), 200
        
        elif request.method == "PATCH":
            # Get current user ID from token
            user_id = None
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                try:
                    import jwt
                    token = auth_header.split(" ")[1]
                    jwt_secret = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
                    payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
                    user_id = payload.get("user_id")
                except Exception:
                    pass
            
            # Check if bill exists and verify creator
            bill = db.bills.find_one({"_id": ObjectId(bill_id)})
            if not bill:
                return jsonify({"error": "Bill not found"}), 404
            
            # Check if user can edit the bill
            # Assigned person can always edit
            if bill.get("assigned_to") == user_id:
                can_edit = True
            else:
                editable_by = bill.get("editable_by", [])
                editable_visibility = bill.get("editable_visibility", "only_me")
                can_edit = False
                
                if editable_visibility == "all":
                    can_edit = True
                elif editable_visibility == "only_me":
                    can_edit = (bill.get("created_by") == user_id)
                else:  # custom
                    can_edit = (user_id in editable_by) if editable_by else (bill.get("created_by") == user_id)
            
            if not can_edit:
                return jsonify({"error": "You are not authorized to edit this bill. Only authorized members can modify bill information."}), 400
            
            data = request.json or {}
            update_data = {}
            
            if "name" in data:
                update_data["name"] = data["name"]
            if "amount" in data:
                update_data["amount"] = float(data["amount"])
            if "due_date" in data:
                update_data["due_date"] = data["due_date"]
            if "category" in data:
                update_data["category"] = data["category"]
            if "assigned_to" in data:
                assigned_to_user_id = data["assigned_to"]
                update_data["assigned_to"] = assigned_to_user_id
                # Get username for display
                assigned_to_username = None
                if assigned_to_user_id:
                    try:
                        assigned_user = db.users.find_one({"_id": ObjectId(assigned_to_user_id)})
                        if assigned_user:
                            assigned_to_username = assigned_user.get("username", "")
                    except Exception:
                        pass
                update_data["assigned_to_username"] = assigned_to_username
            if "paid" in data:
                update_data["paid"] = data["paid"]
                if data["paid"]:
                    update_data["paid_at"] = datetime.now().isoformat()
                    update_data["paid_by"] = data.get("paid_by")
                    
                    # If recurring bill is paid, create next occurrence
                    bill = db.bills.find_one({"_id": ObjectId(bill_id)})
                    if bill and bill.get("is_recurring") and bill.get("recurring_days"):
                        from datetime import timedelta
                        current_due = datetime.fromisoformat(bill["due_date"])
                        next_due = current_due + timedelta(days=bill["recurring_days"])
                        
                        next_bill = {
                            "name": bill["name"],
                            "amount": bill["amount"],
                            "due_date": next_due.isoformat().split('T')[0],  # Just the date part
                            "group_name": bill["group_name"],
                            "category": bill.get("category", "other"),
                            "assigned_to": bill.get("assigned_to"),  # Inherit assigned_to from original bill
                            "assigned_to_username": bill.get("assigned_to_username"),  # Inherit username
                            "paid": False,
                            "is_recurring": True,
                            "recurring_frequency": bill.get("recurring_frequency"),
                            "recurring_days": bill["recurring_days"],
                            "notification_frequency": bill.get("notification_frequency", "daily"),
                            "notification_days_before": bill.get("notification_days_before"),
                            "visibility": bill.get("visibility", "all"),
                            "visible_to": bill.get("visible_to", []),
                            "editable_visibility": bill.get("editable_visibility", "only_me"),
                            "editable_by": bill.get("editable_by", []),
                            "deletable_visibility": bill.get("deletable_visibility", "only_me"),
                            "deletable_by": bill.get("deletable_by", []),
                            "notes": bill.get("notes", ""),
                            "created_by": bill.get("created_by"),  # Inherit creator from original bill
                            "created_at": datetime.now().isoformat()
                        }
                        db.bills.insert_one(next_bill)
            if "notes" in data:
                update_data["notes"] = data["notes"]
            if "is_recurring" in data:
                update_data["is_recurring"] = data["is_recurring"]
            if "recurring_frequency" in data:
                update_data["recurring_frequency"] = data["recurring_frequency"]
            if "recurring_days" in data:
                update_data["recurring_days"] = data["recurring_days"]
            if "notification_frequency" in data:
                update_data["notification_frequency"] = data["notification_frequency"]
            if "notification_days_before" in data:
                update_data["notification_days_before"] = data["notification_days_before"]
            if "visibility" in data:
                update_data["visibility"] = data["visibility"]
            if "visible_to" in data:
                update_data["visible_to"] = data["visible_to"]
            if "editable_visibility" in data:
                update_data["editable_visibility"] = data["editable_visibility"]
            if "editable_by" in data:
                update_data["editable_by"] = data["editable_by"]
            if "deletable_visibility" in data:
                update_data["deletable_visibility"] = data["deletable_visibility"]
            if "deletable_by" in data:
                update_data["deletable_by"] = data["deletable_by"]
            
            if not update_data:
                return jsonify({"error": "No fields to update"}), 400
            
            result = db.bills.update_one(
                {"_id": ObjectId(bill_id)},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                return jsonify({"error": "Bill not found"}), 404
            
            updated = db.bills.find_one({"_id": ObjectId(bill_id)})
            return jsonify(to_json(updated)), 200
        
        else:  # DELETE
            # Get current user ID from token
            user_id = None
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                try:
                    import jwt
                    token = auth_header.split(" ")[1]
                    jwt_secret = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
                    payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
                    user_id = payload.get("user_id")
                except Exception:
                    pass
            
            # Check if bill exists and verify permissions
            bill = db.bills.find_one({"_id": ObjectId(bill_id)})
            if not bill:
                return jsonify({"error": "Bill not found"}), 404
            
            # Check if user can delete the bill
            # Assigned person can always delete
            if bill.get("assigned_to") == user_id:
                can_delete = True
            else:
                deletable_by = bill.get("deletable_by", [])
                deletable_visibility = bill.get("deletable_visibility", "only_me")
                can_delete = False
                
                if deletable_visibility == "all":
                    can_delete = True
                elif deletable_visibility == "only_me":
                    can_delete = (bill.get("created_by") == user_id)
                else:  # custom
                    can_delete = (user_id in deletable_by) if deletable_by else (bill.get("created_by") == user_id)
            
            if not can_delete:
                return jsonify({"error": "You are not authorized to delete this bill. Only authorized members can delete bill information."}), 400
            
            result = db.bills.delete_one({"_id": ObjectId(bill_id)})
            if result.deleted_count == 0:
                return jsonify({"error": "Bill not found"}), 404
            return jsonify({"message": "Bill deleted successfully"}), 200
    
    except Exception as e:
        app.logger.error(f"Error with bill operation: {str(e)}")
        return jsonify({"error": f"Invalid bill ID or operation failed: {str(e)}"}), 400

# Additional API routes that need app instance (from routes.py)
from service.logic import analyze_chores, mark_chore_complete, get_group_calendar

@app.route("/api/groups/<group_name>/chores", methods=["GET", "POST"])
def chores_route(group_name):
    # Validate group_name
    if not group_name or group_name == "null" or group_name == "undefined":
        return jsonify({"error": "Invalid group name. Please select a group first."}), 400
    
    if request.method == "GET":
        data = analyze_chores(db, group_name)
        return jsonify(data), 200
    else:  # POST
        try:
            # Handle both JSON and FormData requests
            if request.content_type and 'multipart/form-data' in request.content_type:
                # Handle file upload
                required_fields = ["task", "due_date"]
                if not all(field in request.form for field in required_fields):
                    return jsonify({"error": "Missing required fields: task, due_date"}), 400
                
                task = request.form["task"]
                assigned_to = request.form.get("assigned_to", "")
                due_date = request.form["due_date"]
                is_recurring = request.form.get("is_recurring", "False").lower() == "true"
                try:
                    frequency_days = int(request.form.get("frequency_days", 7))
                except (ValueError, TypeError):
                    frequency_days = 7
                media_file = request.files.get("media")
                
                media_url = None
                if media_file and media_file.filename:
                    # Create uploads directory if it doesn't exist
                    uploads_dir = os.path.join(PROJECT_ROOT, "static", "uploads", "chores")
                    os.makedirs(uploads_dir, exist_ok=True)
                    
                    # Generate secure filename
                    filename = secure_filename(media_file.filename)
                    # Add timestamp to avoid conflicts
                    timestamp = int(time.time() * 1000)
                    name, ext = os.path.splitext(filename)
                    filename = f"{name}_{timestamp}{ext}"
                    
                    filepath = os.path.join(uploads_dir, filename)
                    media_file.save(filepath)
                    
                    # Store relative URL for serving
                    media_url = f"/static/uploads/chores/{filename}"
            else:
                # Handle JSON request
                data = request.json
                if not data:
                    return jsonify({"error": "Invalid request: JSON data required"}), 400
                
                required_fields = ["task", "due_date"]
                if not all(field in data for field in required_fields):
                    return jsonify({"error": "Missing required fields: task, due_date"}), 400
                
                task = data["task"]
                assigned_to = data.get("assigned_to", "")
                due_date = data["due_date"]
                is_recurring = data.get("is_recurring", False)
                try:
                    frequency_days = int(data.get("frequency_days", 7))
                except (ValueError, TypeError):
                    frequency_days = 7
                media_url = None
            
            # Validate group_name (already checked at top, but double-check)
            if not group_name or group_name == "null" or group_name == "undefined":
                return jsonify({"error": "Invalid group name. Please select a group first."}), 400
            
            # Verify group exists
            group = db.groups.find_one({"name": group_name})
            if not group:
                return jsonify({"error": f"Group '{group_name}' not found"}), 404
            
            chore = {
                "task": task,
                "assigned_to": assigned_to,
                "due_date": due_date,
                "group_name": group_name,
                "status": "pending",
                "is_recurring": is_recurring,
                "frequency_days": frequency_days,
                "media_url": media_url
            }
            
            result = db.chores.insert_one(chore)
            saved = db.chores.find_one({"_id": result.inserted_id})
            if not saved:
                return jsonify({"error": "Failed to save chore"}), 500
            
            saved_json = to_json(saved)
            app.logger.info(f"Chore created: {saved_json.get('task')} for group {group_name}")
            return jsonify(saved_json), 201
        except Exception as e:
            app.logger.error(f"Error creating chore: {str(e)}")
            return jsonify({"error": f"Failed to create chore: {str(e)}"}), 500

@app.route("/api/chores/<chore_id>/complete", methods=["POST"])
def complete_chore_route(chore_id):
    try:
        completed_by = None
        completion_media_url = None
        
        # Handle both JSON and FormData requests
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Handle file upload with completion
            completed_by = request.form.get("completed_by")
            media_file = request.files.get("media")
            
            if media_file and media_file.filename:
                # Create uploads directory if it doesn't exist
                uploads_dir = os.path.join(PROJECT_ROOT, "static", "uploads", "chores", "completions")
                os.makedirs(uploads_dir, exist_ok=True)
                
                # Generate secure filename
                filename = secure_filename(media_file.filename)
                timestamp = int(time.time() * 1000)
                name, ext = os.path.splitext(filename)
                filename = f"complete_{chore_id}_{timestamp}{ext}"
                
                filepath = os.path.join(uploads_dir, filename)
                media_file.save(filepath)
                
                # Store relative URL for serving
                completion_media_url = f"/static/uploads/chores/completions/{filename}"
        else:
            # Handle JSON request
            data = request.json or {}
            completed_by = data.get("completed_by") or request.args.get("completed_by")
        
        result = mark_chore_complete(db, chore_id, completed_by, completion_media_url)
        if "error" in result:
            return jsonify(result), 404
        return jsonify(result), 200
    except Exception as e:
        app.logger.error(f"Error completing chore: {str(e)}")
        return jsonify({"error": f"Failed to complete chore: {str(e)}"}), 500

@app.route("/api/groups/<group_name>/calendar", methods=["GET"])
def get_calendar_route(group_name):
    """Get calendar events - includes both custom events and aggregated chores/bills"""
    try:
        # Get current user ID from token
        user_id = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                import jwt
                token = auth_header.split(" ")[1]
                jwt_secret = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
                payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
                user_id = payload.get("user_id")
            except Exception:
                pass
        
        # Get custom calendar events
        custom_events = []
        # Get events visible to this user (or all if no user_id)
        events_query = {"group_name": group_name}
        all_events = list(db.calendar_events.find(events_query))
        
        for event in all_events:
            visible_to = event.get("visible_to", [])
            visibility = event.get("visibility", "all")
            created_by = event.get("created_by")
            
            # Check visibility
            can_see = False
            if not user_id:
                # If no user_id, show all events (for backward compatibility)
                can_see = True
            elif visibility == "all":
                can_see = True
            elif visibility == "only_me":
                can_see = (created_by == user_id)
            else:  # custom
                can_see = (user_id in visible_to) if visible_to else (created_by == user_id)
            
            if can_see:
                start_dt = event.get("start_datetime", "")
                end_dt = event.get("end_datetime", start_dt)
                all_day = event.get("all_day", False)
                
                # Ensure we have valid datetime strings
                if not start_dt:
                    app.logger.warning(f"Event {event.get('_id')} missing start_datetime")
                    continue
                
                custom_events.append({
                    "id": str(event["_id"]),
                    "title": event.get("title", ""),
                    "start_datetime": start_dt,
                    "end_datetime": end_dt,
                    "start": start_dt,
                    "end": end_dt,
                    "date": start_dt.split('T')[0] if 'T' in start_dt else start_dt.split(' ')[0],  # For backward compatibility
                    "description": event.get("description", ""),
                    "type": "event",
                    "created_by": event.get("created_by"),
                    "visibility": visibility,
                    "visible_to": visible_to,
                    "allDay": all_day,
                    "all_day": all_day
                })
        
        # Get aggregated events (chores, bills, supplies)
        aggregated_events = get_group_calendar(db, group_name)
        
        # Combine and return
        all_events = custom_events + aggregated_events
        app.logger.info(f"Returning {len(all_events)} events for group {group_name}: {len(custom_events)} custom, {len(aggregated_events)} aggregated")
        return jsonify(all_events), 200
    except Exception as e:
        app.logger.error(f"Error getting calendar: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/groups/<group_name>/events", methods=["POST"])
def create_event_route(group_name):
    """Create a new calendar event"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid request data"}), 400
        
        required_fields = ["title", "start_datetime"]
        if not all(field in data for field in required_fields):
            return jsonify({"error": "Missing required fields: title, start_datetime"}), 400
        
        # Verify group exists
        group = db.groups.find_one({"name": group_name})
        if not group:
            return jsonify({"error": f"Group '{group_name}' not found"}), 404
        
        # Get creator from Authorization header
        creator_id = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                import jwt
                token = auth_header.split(" ")[1]
                jwt_secret = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
                payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
                creator_id = payload.get("user_id")
            except Exception:
                pass
        
        event = {
            "title": data["title"],
            "description": data.get("description", ""),
            "start_datetime": data["start_datetime"],
            "end_datetime": data.get("end_datetime", data["start_datetime"]),
            "all_day": data.get("all_day", False),
            "group_name": group_name,
            "created_by": creator_id,
            "visibility": data.get("visibility", "all"),
            "visible_to": data.get("visible_to", []),
            "created_at": datetime.now().isoformat()
        }
        
        result = db.calendar_events.insert_one(event)
        saved = db.calendar_events.find_one({"_id": result.inserted_id})
        return jsonify(to_json(saved)), 201
    except Exception as e:
        app.logger.error(f"Error creating event: {str(e)}")
        return jsonify({"error": f"Failed to create event: {str(e)}"}), 500

@app.route("/api/events/<event_id>", methods=["GET", "PATCH", "DELETE"])
def event_route(event_id):
    """Get, update, or delete a specific event"""
    try:
        # Get current user ID from token
        user_id = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                import jwt
                token = auth_header.split(" ")[1]
                jwt_secret = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
                payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
                user_id = payload.get("user_id")
            except Exception:
                pass
        
        if request.method == "GET":
            event = db.calendar_events.find_one({"_id": ObjectId(event_id)})
            if not event:
                return jsonify({"error": "Event not found"}), 404
            
            # Check visibility
            visible_to = event.get("visible_to", [])
            visibility = event.get("visibility", "all")
            created_by = event.get("created_by")
            
            can_see = False
            if visibility == "all":
                can_see = True
            elif visibility == "only_me":
                can_see = (created_by == user_id)
            else:  # custom
                can_see = (user_id in visible_to) if visible_to else (created_by == user_id)
            
            if not can_see:
                return jsonify({"error": "You are not authorized to view this event"}), 403
            
            return jsonify(to_json(event)), 200
        
        elif request.method == "PATCH":
            event = db.calendar_events.find_one({"_id": ObjectId(event_id)})
            if not event:
                return jsonify({"error": "Event not found"}), 404
            
            # Check if user can edit (creator can always edit)
            if event.get("created_by") != user_id:
                return jsonify({"error": "You are not authorized to edit this event. Only the event creator can modify it."}), 400
            
            data = request.json or {}
            update_data = {}
            
            if "title" in data:
                update_data["title"] = data["title"]
            if "description" in data:
                update_data["description"] = data["description"]
            if "start_datetime" in data:
                update_data["start_datetime"] = data["start_datetime"]
            if "end_datetime" in data:
                update_data["end_datetime"] = data["end_datetime"]
            if "all_day" in data:
                update_data["all_day"] = data["all_day"]
            if "visibility" in data:
                update_data["visibility"] = data["visibility"]
            if "visible_to" in data:
                update_data["visible_to"] = data["visible_to"]
            
            if not update_data:
                return jsonify({"error": "No fields to update"}), 400
            
            result = db.calendar_events.update_one(
                {"_id": ObjectId(event_id)},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                return jsonify({"error": "Event not found"}), 404
            
            updated = db.calendar_events.find_one({"_id": ObjectId(event_id)})
            return jsonify(to_json(updated)), 200
        
        else:  # DELETE
            event = db.calendar_events.find_one({"_id": ObjectId(event_id)})
            if not event:
                return jsonify({"error": "Event not found"}), 404
            
            # Only creator can delete
            if event.get("created_by") != user_id:
                return jsonify({"error": "You are not authorized to delete this event. Only the event creator can delete it."}), 400
            
            result = db.calendar_events.delete_one({"_id": ObjectId(event_id)})
            if result.deleted_count == 0:
                return jsonify({"error": "Event not found"}), 404
            return jsonify({"message": "Event deleted successfully"}), 200
    
    except Exception as e:
        app.logger.error(f"Error with event operation: {str(e)}")
        return jsonify({"error": f"Invalid event ID or operation failed: {str(e)}"}), 400

# Optional: static files served automatically by Flask from static_folder,
# but this route can help if needed for direct static access
@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

if __name__ == "__main__":
    # Default port 8000 matches your previous app.py dev config
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)), debug=True)
