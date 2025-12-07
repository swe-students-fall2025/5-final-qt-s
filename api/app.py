# api/app.py
from flask import Flask, request, jsonify, render_template, send_from_directory
from pymongo import MongoClient
import os
from service.logic import analyze_supplies, analyze_rent

# DB config
MONGO_URL = os.getenv("MONGO_URL", "mongodb://mongo:27017")
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

# Optional: static files served automatically by Flask from static_folder,
# but this route can help if needed for direct static access
@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

if __name__ == "__main__":
    # Default port 8000 matches your previous app.py dev config
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)), debug=True)
