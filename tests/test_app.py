"""
Tests for the Mergington High School Activities API
"""

import pytest
from fastapi.testclient import TestClient
from src.app import app, activities


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_activities():
    """Reset activities data before each test"""
    # Store original state
    original_activities = {
        name: {
            "description": details["description"],
            "schedule": details["schedule"],
            "max_participants": details["max_participants"],
            "participants": details["participants"].copy()
        }
        for name, details in activities.items()
    }
    
    yield
    
    # Restore original state after test
    for name, details in original_activities.items():
        if name in activities:
            activities[name]["participants"] = details["participants"].copy()


class TestRootEndpoint:
    """Tests for the root endpoint"""
    
    def test_root_redirects_to_static(self, client):
        """Test that root redirects to static/index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestGetActivities:
    """Tests for GET /activities endpoint"""
    
    def test_get_activities_returns_all_activities(self, client):
        """Test that all activities are returned"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) > 0
        assert "Chess Club" in data
        assert "Programming Class" in data
    
    def test_activity_structure(self, client):
        """Test that each activity has the correct structure"""
        response = client.get("/activities")
        data = response.json()
        
        for name, details in data.items():
            assert "description" in details
            assert "schedule" in details
            assert "max_participants" in details
            assert "participants" in details
            assert isinstance(details["participants"], list)
            assert isinstance(details["max_participants"], int)


class TestSignupForActivity:
    """Tests for POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_success(self, client):
        """Test successful signup for an activity"""
        # Add a new participant
        response = client.post(
            "/activities/Chess Club/signup?email=newstudent@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "newstudent@mergington.edu" in data["message"]
        assert "Chess Club" in data["message"]
        
        # Verify participant was added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "newstudent@mergington.edu" in activities_data["Chess Club"]["participants"]
    
    def test_signup_duplicate_participant(self, client):
        """Test that duplicate signup is rejected"""
        email = "test@mergington.edu"
        
        # First signup should succeed
        response1 = client.post(
            f"/activities/Chess Club/signup?email={email}"
        )
        assert response1.status_code == 200
        
        # Second signup should fail
        response2 = client.post(
            f"/activities/Chess Club/signup?email={email}"
        )
        assert response2.status_code == 400
        data = response2.json()
        assert "already signed up" in data["detail"].lower()
    
    def test_signup_nonexistent_activity(self, client):
        """Test signup for non-existent activity"""
        response = client.post(
            "/activities/Nonexistent Club/signup?email=test@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_signup_url_encoded_activity_name(self, client):
        """Test signup with URL-encoded activity name"""
        response = client.post(
            "/activities/Programming%20Class/signup?email=test@mergington.edu"
        )
        assert response.status_code == 200


class TestUnregisterFromActivity:
    """Tests for DELETE /activities/{activity_name}/participants/{email} endpoint"""
    
    def test_unregister_success(self, client):
        """Test successful unregistration from an activity"""
        # First, sign up a participant
        email = "testdelete@mergington.edu"
        client.post(f"/activities/Chess Club/signup?email={email}")
        
        # Then unregister them
        response = client.delete(
            f"/activities/Chess Club/participants/{email}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Unregistered" in data["message"]
        assert email in data["message"]
        
        # Verify participant was removed
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert email not in activities_data["Chess Club"]["participants"]
    
    def test_unregister_existing_participant(self, client):
        """Test unregistering an existing participant"""
        # Use a participant that's already in the activity
        existing_email = "michael@mergington.edu"
        
        response = client.delete(
            f"/activities/Chess Club/participants/{existing_email}"
        )
        assert response.status_code == 200
        
        # Verify participant was removed
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert existing_email not in activities_data["Chess Club"]["participants"]
    
    def test_unregister_nonexistent_participant(self, client):
        """Test unregistering a participant not in the activity"""
        response = client.delete(
            "/activities/Chess Club/participants/notinclub@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_unregister_from_nonexistent_activity(self, client):
        """Test unregistering from non-existent activity"""
        response = client.delete(
            "/activities/Nonexistent Club/participants/test@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_unregister_url_encoded_email(self, client):
        """Test unregistering with properly URL-encoded email"""
        import urllib.parse
        
        # Use an email that needs URL encoding
        email = "test.user@mergington.edu"
        
        # First signup
        signup_response = client.post(
            f"/activities/Chess Club/signup?email={urllib.parse.quote(email)}"
        )
        assert signup_response.status_code == 200
        
        # Verify participant was added
        activities_response = client.get("/activities")
        assert email in activities_response.json()["Chess Club"]["participants"]
        
        # Then unregister with URL encoding in path
        response = client.delete(
            f"/activities/Chess%20Club/participants/{urllib.parse.quote(email)}"
        )
        assert response.status_code == 200
        
        # Verify participant was removed
        activities_response = client.get("/activities")
        assert email not in activities_response.json()["Chess Club"]["participants"]


class TestIntegrationScenarios:
    """Integration tests for common user scenarios"""
    
    def test_full_signup_and_unregister_flow(self, client):
        """Test complete flow: signup, verify, unregister, verify"""
        email = "flowtest@mergington.edu"
        activity = "Drama Club"
        
        # Get initial participant count
        initial_response = client.get("/activities")
        initial_count = len(initial_response.json()[activity]["participants"])
        
        # Signup
        signup_response = client.post(
            f"/activities/{activity}/signup?email={email}"
        )
        assert signup_response.status_code == 200
        
        # Verify added
        after_signup = client.get("/activities")
        assert len(after_signup.json()[activity]["participants"]) == initial_count + 1
        assert email in after_signup.json()[activity]["participants"]
        
        # Unregister
        unregister_response = client.delete(
            f"/activities/{activity}/participants/{email}"
        )
        assert unregister_response.status_code == 200
        
        # Verify removed
        after_unregister = client.get("/activities")
        assert len(after_unregister.json()[activity]["participants"]) == initial_count
        assert email not in after_unregister.json()[activity]["participants"]
    
    def test_multiple_signups_different_activities(self, client):
        """Test signing up for multiple activities"""
        email = "multi@mergington.edu"
        
        # Signup for multiple activities
        activities_to_join = ["Chess Club", "Programming Class", "Art Studio"]
        
        for activity in activities_to_join:
            response = client.post(
                f"/activities/{activity}/signup?email={email}"
            )
            assert response.status_code == 200
        
        # Verify participant is in all activities
        all_activities = client.get("/activities").json()
        for activity in activities_to_join:
            assert email in all_activities[activity]["participants"]
