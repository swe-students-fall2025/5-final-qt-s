from datetime import datetime, timedelta
from bson.objectid import ObjectId

def analyze_rent(db, group_name):
    rent_doc = db.rent.find_one({"group_name": group_name})
    if not rent_doc:
        return {"error": "no rent record found"}

    roommates = list(db.roommates.find({"group_name": group_name}))
    if not roommates:
        return {"error": "no roommates found"}

    from datetime import datetime

    due = datetime.fromisoformat(rent_doc["due_date"])
    now = datetime.now()
    days_left = (due - now).days

    status = "OVERDUE" if days_left < 0 else "OK"

    # notifs --> in API reponses --> easy to connect w UI
    if days_left < 0:
        notification = "Rent is OVERDUE!"
    elif days_left <= 3:
        notification = f"Rent is due soon: {days_left} days left."
    else:
        notification = None

    shares = []
    for rm in roommates:
        shares.append({
            "name": rm["name"],
            "rent_share": rm.get("rent_share", 0)
        })

    return {
        "group_name": group_name,
        "total_rent": rent_doc["total_rent"],
        "due_date": rent_doc["due_date"],
        "days_left": days_left,
        "status": status,
        "notification": notification,
        "shares": shares
    }

def analyze_supplies(db, group_name):
    supplies = list(db.supplies.find({"group_name": group_name}))

    from datetime import datetime, timedelta

    low_items = []
    notifications = []

    for s in supplies:
        last = datetime.fromisoformat(s["last_bought"])

        avg_days = s.get("avg_days_between", 14)

        if datetime.now() - last > timedelta(days=avg_days):
            low_items.append({
                "item": s["item"],
                "status": "LOW SOON"
            })
            notifications.append(f"{s['item']} is running low.")

    return {
        "group_name": group_name,
        "low_items": low_items,
        "total_supplies": len(supplies),
        "notifications": notifications
    }


def analyze_chores(db, group_name):
    """
    Fetches chores and checks if they are overdue.
    """
    chores = list(db.chores.find({"group_name": group_name}))
    chore_data = []
    
    for c in chores:
        due = datetime.fromisoformat(c["due_date"])
        is_overdue = datetime.now() > due and c["status"] != "completed"
        
        chore_data.append({
            "id": str(c["_id"]),
            "task": c["task"],
            "assigned_to": c["assigned_to"],
            "due_date": c["due_date"],
            "status": "OVERDUE" if is_overdue else c["status"],
            "is_recurring": c.get("is_recurring", False)
        })

    return {
        "group_name": group_name,
        "chores": chore_data
    }

def mark_chore_complete(db, chore_id):
    """
    Marks chore as complete. If recurring, assigns to next roommate.
    """
    chore = db.chores.find_one({"_id": ObjectId(chore_id)})
    if not chore:
        return {"error": "Chore not found"}

    db.chores.update_one({"_id": ObjectId(chore_id)}, {"$set": {"status": "completed"}})

    if not chore.get("is_recurring"):
        return {"message": "Chore marked as done."}

    group_name = chore["group_name"]
    roommates = list(db.roommates.find({"group_name": group_name}))
    
    names = sorted([r["name"] for r in roommates])
    
    current_person = chore["assigned_to"]
    try:
        curr_index = names.index(current_person)
        next_index = (curr_index + 1) % len(names) 
        next_person = names[next_index]
    except ValueError:

        next_person = names[0] if names else "Unassigned"

    new_due_date = datetime.now() + timedelta(days=chore["frequency_days"])
    
    new_chore = {
        "task": chore["task"],
        "group_name": group_name,
        "assigned_to": next_person,
        "status": "pending",
        "due_date": new_due_date.isoformat(),
        "frequency_days": chore["frequency_days"],
        "is_recurring": True
    }
    db.chores.insert_one(new_chore)
    
    return {"message": f"Chore finished! Next up: {next_person}"}