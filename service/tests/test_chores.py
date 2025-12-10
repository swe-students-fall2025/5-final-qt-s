import pytest
from unittest.mock import MagicMock
from service.logic import mark_chore_complete

@pytest.fixture
def mock_db():
    return MagicMock()

def test_rotation_logic(mock_db):
    fake_chore_id = "507f1f77bcf86cd799439011" 
    
    fake_chore_doc = {
        "_id": fake_chore_id,
        "task": "Trash",
        "group_name": "Apt A",
        "assigned_to": "Reece",
        "is_recurring": True,
        "frequency_days": 7,
        "due_date": "2025-12-01"
    }
    
    fake_roommates = [
        {"username": "Alissa", "group_name": "Apt A"},
        {"username": "Khusboo", "group_name": "Apt A"},
        {"username": "Reece", "group_name": "Apt A"}
    ]

    mock_db.chores.find_one.return_value = fake_chore_doc
    mock_db.roommates.find.return_value = fake_roommates

    result = mark_chore_complete(mock_db, fake_chore_id)

    assert "Next up: Alissa" in result["message"]

    assert mock_db.chores.insert_one.called
    
    args = mock_db.chores.insert_one.call_args[0][0]
    assert args["assigned_to"] == "Alissa"
    assert args["task"] == "Trash"

def test_overdue_logic(mock_db):
    from service.logic import analyze_chores
    
    mock_db.chores.find.return_value = [{
        "_id": "123",
        "task": "Dishes",
        "assigned_to": "Majo",
        "due_date": "2020-01-01", 
        "status": "pending"
    }]
    
    result = analyze_chores(mock_db, "Apt A")
    
    assert result["chores"][0]["status"] == "OVERDUE"

def test_calendar_aggregation(mock_db):
    from service.logic import get_group_calendar
    
    mock_db.rent.find_one.return_value = {
        "group_name": "Apt A", "total_rent": 2000, "due_date": "2025-12-05"
    }
    
    mock_db.roommates.find.return_value = [
        {"name": "Alissa", "group_name": "Apt A", "rent_share": 1000}
    ]

    mock_db.supplies.find.return_value = [] 

    mock_db.chores.find.return_value = [{
        "_id": "123", "task": "Sweep", "assigned_to": "Majo",
        "due_date": "2025-12-01", "status": "pending"
    }]

    calendar = get_group_calendar(mock_db, "Apt A")

    assert len(calendar) == 2
    
    assert calendar[0]["title"] == "Sweep"
    assert "Rent Due" in calendar[1]["title"]