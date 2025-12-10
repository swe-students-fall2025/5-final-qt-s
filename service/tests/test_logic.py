from service.logic import compute_recommendations

def test_recommendations():
    class FakeCollection:
        def __init__(self, docs):
            self.docs = docs
            
        def find(self, query):
            return self
            
        def limit(self, n):
            return self.docs
            
        def __iter__(self):
            return iter(self.docs)

    class FakeDB:
        def __init__(self, docs):
            self.items = FakeCollection(docs)

    fake_docs = [
        {"_id": 1, "name": "TestItem", "mood_tags": ["happy"]}
    ]

    db = FakeDB(fake_docs)
    recs = compute_recommendations(db, "happy")

    assert len(recs) == 1
    assert recs[0]["name"] == "TestItem"
