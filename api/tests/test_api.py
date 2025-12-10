import pytest
from unittest.mock import MagicMock, patch
from bson import ObjectId
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from api.app import app


@pytest.fixture
def client():
    """Create a test client for the Flask app"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_db():
    """Create a mock database"""
    db = MagicMock()
    db.users = MagicMock()
    db.groups = MagicMock()
    db.chores = MagicMock()
    return db


def test_create_user(client, mock_db):
    """Test creating a new user"""
    with patch('api.routes.db', mock_db):
        fake_id = ObjectId()
        
        mock_db.users.find_one.side_effect = [
            None, 
            {
                "_id": fake_id,
                "username": "testuser",
                "email": "test@test.com",
                "password_hash": "hashed_password"
            }
        ]
        
        mock_db.users.insert_one.return_value.inserted_id = fake_id
        
        response = client.post('/api/users', json={
            "username": "testuser",
            "email": "test@test.com",
            "password": "test123"
        })
        
        assert response.status_code == 201
        data = response.get_json()
        assert data["username"] == "testuser"
        assert "password_hash" not in data


def test_login(client, mock_db):
    """Test user login and JWT token generation"""
    with patch('api.routes.db', mock_db):
        fake_id = ObjectId()
        password_hash = generate_password_hash("test123")
        mock_db.users.find_one.return_value = {
            "_id": fake_id,
            "username": "testuser",
            "password_hash": password_hash
        }
        
        response = client.post('/api/login', json={
            "username": "testuser",
            "password": "test123"
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data
        assert data["username"] == "testuser"


def test_get_user(client, mock_db):
    """Test getting a user by ID"""
    with patch('api.routes.db', mock_db):
        fake_id = ObjectId()
        mock_db.users.find_one.return_value = {
            "_id": fake_id,
            "username": "testuser",
            "email": "test@test.com",
            "password_hash": "hashed"
        }
        
        response = client.get(f'/api/users/{fake_id}')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["username"] == "testuser"
        assert "password_hash" not in data


def test_create_group(client, mock_db):
    """Test creating a new roommate group"""
    with patch('api.routes.db', mock_db):
        fake_user_id = ObjectId()
        fake_group_id = ObjectId()
        
        mock_db.users.find_one.return_value = {
            "_id": fake_user_id,
            "username": "creator"
        }
        
        mock_db.groups.insert_one.return_value.inserted_id = fake_group_id
        mock_db.groups.find_one.return_value = {
            "_id": fake_group_id,
            "name": "Test Group",
            "created_by": str(fake_user_id),
            "created_by_username": "creator",
            "roommates": [str(fake_user_id)]
        }
        
        response = client.post('/api/groups', json={
            "name": "Test Group",
            "created_by": str(fake_user_id)
        })
        
        assert response.status_code == 201
        data = response.get_json()
        assert data["name"] == "Test Group"
        assert str(fake_user_id) in data["roommates"]


def test_get_groups(client, mock_db):
    """Test getting all groups"""
    with patch('api.routes.db', mock_db):
        creator_id = ObjectId()
        fake_groups = [
            {"_id": ObjectId(), "name": "Group 1", "created_by": str(creator_id), "created_by_username": "creator1", "roommates": []},
            {"_id": ObjectId(), "name": "Group 2", "created_by": str(creator_id), "created_by_username": "creator2", "roommates": []}
        ]
        mock_db.groups.find.return_value = fake_groups
        
        response = client.get('/api/groups')
        
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 2


def test_add_roommate(client, mock_db):
    """Test adding a roommate to a group"""
    with patch('api.routes.db', mock_db):
        fake_group_id = ObjectId()
        fake_user_id = ObjectId()
        
        mock_db.group_invitations.find_one.return_value = None

        mock_db.groups.find_one.side_effect = [
            {
                "_id": fake_group_id,
                "name": "Test Group",
                "roommates": ["existing_user_id"]
            },
            {
                "_id": fake_group_id,
                "name": "Test Group",
                "roommates": ["existing_user_id", str(fake_user_id)]
            }
        ]
        
        mock_db.users.find_one.return_value = {
            "_id": fake_user_id,
            "username": "newuser"
        }

        mock_db.group_invitations.insert_one.return_value.inserted_id = ObjectId()
        
        response = client.post(f'/api/groups/{fake_group_id}/roommates', json={
            "user_id": str(fake_user_id)
        })
        
        assert response.status_code == 201
        data = response.get_json()
        assert "invitation_id" in data
        assert "message" in data


def test_create_chore(client, mock_db):
    """Test creating a new chore"""
    with patch('api.app.db', mock_db):
        fake_id = ObjectId()
        future_date = (datetime.now() + timedelta(days=7)).isoformat()
        
        mock_db.chores.insert_one.return_value.inserted_id = fake_id
        mock_db.chores.find_one.return_value = {
            "_id": fake_id,
            "task": "Clean bathroom",
            "assigned_to": "user1",
            "due_date": future_date,
            "group_name": "TestGroup",
            "status": "pending"
        }
        
        response = client.post('/api/groups/TestGroup/chores', json={
            "task": "Clean bathroom",
            "assigned_to": "user1",
            "due_date": future_date
        })
        
        assert response.status_code == 201
        data = response.get_json()
        assert data["task"] == "Clean bathroom"


def test_get_chores(client, mock_db):
    """Test getting chores for a group"""
    with patch('api.app.db', mock_db):
        future_date = (datetime.now() + timedelta(days=7)).isoformat()
        mock_db.chores.find.return_value = [{
            "_id": ObjectId(),
            "task": "Clean kitchen",
            "assigned_to": "user1",
            "due_date": future_date,
            "status": "pending",
            "is_recurring": False
        }]
        
        response = client.get('/api/groups/TestGroup/chores')
        
        assert response.status_code == 200
        data = response.get_json()
        assert "chores" in data
        assert len(data["chores"]) == 1


def test_complete_chore(client, mock_db):
    """Test marking a chore as complete"""
    with patch('api.app.db', mock_db):
        fake_id = ObjectId()
        
        with patch('api.app.mark_chore_complete') as mock_complete:
            mock_complete.return_value = {"message": "Chore marked as done."}
            
            response = client.post(f'/api/chores/{fake_id}/complete', json={})
            
            assert response.status_code == 200
            data = response.get_json()
            assert "message" in data
