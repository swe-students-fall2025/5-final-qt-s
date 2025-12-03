from bson import ObjectId

def to_json(doc):
    if not doc:
        return doc
    d = dict(doc)
    d["_id"] = str(d["_id"])
    return d
