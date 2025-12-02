from service.logic import compute_recommendations

def test_recommendations():
    class FakeDB:
        def __init__(self, docs):
            self.docs = docs

        def find(self, query):
            class Cursor:
                def __init__(self, docs): self.docs = docs
                def limit(self, n): return self
                def __iter__(self): return iter(self.docs)
            return Cursor(self.docs)

    fake_docs = [
        {"_id": 1, "name": "TestItem", "mood_tags": ["happy"]}
    ]

    db = FakeDB(fake_docs)
    recs = compute_recommendations(db, "happy")

    assert len(recs) == 1
    assert recs[0]["name"] == "TestItem"
