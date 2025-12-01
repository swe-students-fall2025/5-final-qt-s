def compute_recommendations(db, item_x: str | None):
    query = {}

    if item_x:
        query["item_x_tags"] = {"$in": [item_x]}

    docs = list(db.items.find(query).limit(5))

    if not docs:
        docs = list(db.items.find({}).limit(5))

    for d in docs:
        d["_id"] = str(d["_id"])

    return docs

# when pick idea --> change item_x