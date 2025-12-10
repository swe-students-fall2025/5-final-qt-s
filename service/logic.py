from datetime import datetime, timedelta
from bson.objectid import ObjectId

def compute_recommendations(db, tag):
    """
    Compute recommendations based on a tag.
    Searches for items matching the given tag.
    """
    # Search for items with matching tags
    # This is a placeholder implementation - adjust based on your data model
    items = list(db.items.find({"mood_tags": tag}).limit(10))
    
    # Convert ObjectId to string for JSON serialization
    results = []
    for item in items:
        item["_id"] = str(item["_id"])
        results.append(item)
    
    return results

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

def analyze_bills(db, group_name, user_id=None):
    """
    Analyzes all bills for a group and calculates notifications.
    Returns bills with status and notification info.
    Filters bills based on synchronization:
    - If synchronized=True: all group members see it
    - If synchronized=False: only creator sees it
    """
    # Get all bills for the group
    all_bills = list(db.bills.find({"group_name": group_name}))
    
    # Filter bills based on visibility
    bills = []
    for bill in all_bills:
        visibility = bill.get("visibility", "all")
        visible_to = bill.get("visible_to", [])
        created_by = bill.get("created_by")
        assigned_to = bill.get("assigned_to")
        
        # If visibility is "all", everyone in group sees it
        # If visibility is "only_me", only creator sees it
        # If visibility is "custom", check if user is in visible_to list
        if visibility == "all":
            bills.append(bill)
        elif visibility == "only_me":
            # Only creator sees it
            if user_id and created_by and created_by == user_id:
                bills.append(bill)
        elif visibility == "custom" and user_id:
            # Check if user is in visible_to list
            if visible_to and user_id in visible_to:
                bills.append(bill)
        elif not user_id:
            # If no user_id provided, show all bills (for backward compatibility)
            bills.append(bill)
    
    bill_data = []
    for bill in bills:
        if bill.get("paid", False):
            # Skip paid bills or show them separately
            bill_data.append({
                "id": str(bill["_id"]),
                "name": bill["name"],
                "amount": bill["amount"],
                "due_date": bill["due_date"],
                "category": bill.get("category", "other"),
                "status": "PAID",
                "days_left": None,
                "notification": None,
                "paid": True,
                "paid_by": bill.get("paid_by"),
                "paid_at": bill.get("paid_at"),
                "assigned_to": bill.get("assigned_to"),
                "assigned_to_username": bill.get("assigned_to_username"),
                "is_recurring": bill.get("is_recurring", False),
                "recurring_frequency": bill.get("recurring_frequency"),
                "visibility": bill.get("visibility", "all"),
                "visible_to": bill.get("visible_to", []),
                "notes": bill.get("notes", "")
            })
            continue
        
        due = datetime.fromisoformat(bill["due_date"])
        now = datetime.now()
        days_left = (due - now).days
        
        status = "OVERDUE" if days_left < 0 else ("DUE_SOON" if days_left <= 3 else "PENDING")
        
        # Generate notifications
        notification = None
        if days_left < 0:
            notification = f"{bill['name']} is OVERDUE by {abs(days_left)} days!"
        elif days_left == 0:
            notification = f"{bill['name']} is due TODAY!"
        elif days_left <= 3:
            notification = f"{bill['name']} is due in {days_left} days."
        
        bill_data.append({
            "id": str(bill["_id"]),
            "name": bill["name"],
            "amount": bill["amount"],
            "due_date": bill["due_date"],
            "category": bill.get("category", "other"),
            "status": status,
            "days_left": days_left,
            "notification": notification,
            "paid": False,
            "assigned_to": bill.get("assigned_to"),
            "assigned_to_username": bill.get("assigned_to_username"),
            "is_recurring": bill.get("is_recurring", False),
            "recurring_frequency": bill.get("recurring_frequency"),
            "visibility": bill.get("visibility", "all"),
            "visible_to": bill.get("visible_to", []),
            "notes": bill.get("notes", "")
        })
    
    # Sort by due date (overdue first, then by date)
    bill_data.sort(key=lambda x: (
        x["status"] != "OVERDUE",  # Overdue first
        x["days_left"] if x["days_left"] is not None else 9999
    ))
    
    return {
        "group_name": group_name,
        "bills": bill_data,
        "total_unpaid": sum(b["amount"] for b in bill_data if not b.get("paid", False)),
        "overdue_count": sum(1 for b in bill_data if b["status"] == "OVERDUE"),
        "due_soon_count": sum(1 for b in bill_data if b["status"] == "DUE_SOON")
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
        
        # Get completion media (latest one if multiple)
        completion_media = c.get("completion_media", [])
        latest_completion_media = completion_media[-1] if completion_media else None
        media_url = latest_completion_media.get("media_url") if latest_completion_media else c.get("media_url")
        
        chore_data.append({
            "id": str(c["_id"]),
            "task": c["task"],
            "assigned_to": c["assigned_to"],
            "due_date": c["due_date"],
            "status": "OVERDUE" if is_overdue else c["status"],
            "is_recurring": c.get("is_recurring", False),
            "media_url": media_url,
            "completion_media": completion_media,
            "completed_by": c.get("completed_by"),
            "completed_by_username": c.get("completed_by_username"),
            "completed_at": c.get("completed_at")
        })

    return {
        "group_name": group_name,
        "chores": chore_data
    }

def mark_chore_complete(db, chore_id, completed_by_user_id=None, completion_media_url=None):
    """
    Marks chore as complete. If recurring, assigns to next roommate.
    Uses group.roommates array to get actual roommates.
    """
    chore = db.chores.find_one({"_id": ObjectId(chore_id)})
    if not chore:
        return {"error": "Chore not found"}

    # Update chore with completion info
    update_data = {
        "status": "completed",
        "completed_at": datetime.now().isoformat()
    }
    if completed_by_user_id:
        update_data["completed_by"] = completed_by_user_id
        # Get username for display
        try:
            user = db.users.find_one({"_id": ObjectId(completed_by_user_id)})
            if user:
                update_data["completed_by_username"] = user.get("username", "")
        except Exception:
            pass
    
    # Add completion media URL if provided
    if completion_media_url:
        # Store completion media (can have multiple completions for recurring chores)
        completion_media = chore.get("completion_media", [])
        completion_media.append({
            "media_url": completion_media_url,
            "completed_at": datetime.now().isoformat(),
            "completed_by": completed_by_user_id
        })
        update_data["completion_media"] = completion_media
        update_data["media_url"] = completion_media_url  # Also set main media_url for backward compatibility
    
    db.chores.update_one({"_id": ObjectId(chore_id)}, {"$set": update_data})

    if not chore.get("is_recurring"):
        return {"message": "Chore marked as done."}

    # Get group and its roommates (user IDs)
    group_name = chore["group_name"]
    group = db.groups.find_one({"name": group_name})
    
    if not group:
        return {"error": "Group not found"}
    
    roommate_ids = group.get("roommates", [])
    if not roommate_ids:
        return {"error": "No roommates found in group"}
    
    # Get usernames for all roommates
    roommate_users = {}
    for rm_id in roommate_ids:
        try:
            user = db.users.find_one({"_id": ObjectId(rm_id)})
            if user:
                roommate_users[rm_id] = user.get("username", "")
        except Exception:
            pass
    
    # Find current assigned user ID (match by username or user_id)
    current_assigned = chore.get("assigned_to", "")
    current_user_id = None
    
    # Try to find by username match
    for rm_id, username in roommate_users.items():
        if username == current_assigned or str(rm_id) == current_assigned:
            current_user_id = rm_id
            break
    
    # If not found, use first roommate
    if not current_user_id and roommate_ids:
        current_user_id = roommate_ids[0]
    
    # Rotate to next roommate
    try:
        current_index = roommate_ids.index(current_user_id)
        next_index = (current_index + 1) % len(roommate_ids)
        next_user_id = roommate_ids[next_index]
        next_username = roommate_users.get(next_user_id, "Unassigned")
    except (ValueError, IndexError):
        next_user_id = roommate_ids[0] if roommate_ids else None
        next_username = roommate_users.get(next_user_id, "Unassigned") if next_user_id else "Unassigned"

    new_due_date = datetime.now() + timedelta(days=chore["frequency_days"])
    
    new_chore = {
        "task": chore["task"],
        "group_name": group_name,
        "assigned_to": next_username,  # Store username for display
        "assigned_to_user_id": str(next_user_id),  # Store user ID for tracking
        "status": "pending",
        "due_date": new_due_date.isoformat(),
        "frequency_days": chore["frequency_days"],
        "is_recurring": True
    }
    db.chores.insert_one(new_chore)
    
    return {"message": f"Chore finished! Next up: {next_username}"}

def get_group_calendar(db, group_name):
    from datetime import datetime

    events = []

    # Add rent
    rent_data = analyze_rent(db, group_name)
    if rent_data and "due_date" in rent_data:
        events.append({
            "title": f"Rent Due (${rent_data['total_rent']})",
            "date": rent_data["due_date"],
            "start": rent_data["due_date"],
            "start_datetime": rent_data["due_date"] + "T00:00:00",
            "type": "bill",
            "assignee": "Everyone",
            "status": rent_data.get("status", "pending"),
            "allDay": True,
            "all_day": True
        })
    
    # Add all bills from bills collection
    bills_data = analyze_bills(db, group_name)
    for bill in bills_data.get("bills", []):
        if not bill.get("paid", False):  # Only show unpaid bills
            due_date = bill.get("due_date", "")
            if due_date:
                # Ensure date is in YYYY-MM-DD format
                if 'T' in due_date:
                    due_date = due_date.split('T')[0]
                events.append({
                    "id": bill.get("id", ""),
                    "title": f"{bill['name']} - ${bill['amount']}",
                    "date": due_date,
                    "start": due_date,
                    "start_datetime": due_date + "T00:00:00",
                    "type": "bill",
                    "assignee": bill.get("assigned_to_username", bill.get("assigned_to", "Unassigned")),
                    "status": bill.get("status", "PENDING"),
                    "allDay": True,
                    "all_day": True
                })
        
    # Add supplies (shopping items)
    supplies_data = analyze_supplies(db, group_name)
    for item in supplies_data.get("low_items", []):
         events.append({
            "title": f"Buy {item['item']}",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "start": datetime.now().strftime("%Y-%m-%d"),
            "start_datetime": datetime.now().strftime("%Y-%m-%d") + "T00:00:00",
            "type": "shopping",
            "assignee": "Any",
            "status": "URGENT",
            "allDay": True,
            "all_day": True
        })

    # Add chores
    chores_data = analyze_chores(db, group_name)
    for c in chores_data.get("chores", []):
        if c["status"] != "completed":
            due_date = c.get("due_date", "")
            if due_date:
                # Ensure date is in YYYY-MM-DD format
                if 'T' in due_date:
                    due_date = due_date.split('T')[0]
                events.append({
                    "id": c.get("id", ""),
                    "title": c["task"],
                    "date": due_date,
                    "start": due_date,
                    "start_datetime": due_date + "T00:00:00",
                    "type": "chore",
                    "assignee": c.get("assigned_to", "Unassigned"),
                    "status": c["status"],
                    "allDay": True,
                    "all_day": True
                })

    events.sort(key=lambda x: x.get("date", ""))
    
    return events