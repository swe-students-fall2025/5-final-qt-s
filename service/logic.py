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

        # can change poss so user can change how many days btw 
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
