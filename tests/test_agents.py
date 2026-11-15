"""
Tests for Agent Management Endpoints

Covers:
1. Agent registration (POST /api/v1/agents/register)
2. Duplicate agent handling (HTTP 409 Conflict)
3. Listing agents (GET /api/v1/agents)
4. Getting agent by ID (GET /api/v1/agents/{agent_id})
5. Updating an agent (PUT /api/v1/agents/{agent_id})
6. Deleting an agent (DELETE /api/v1/agents/{agent_id})
7. Validation errors and 404/400 edge cases
"""

import uuid


class TestAgentRegistration:
    """Task 6.1: Agent registration and Task 6.2: Duplicate handling."""

    def test_register_agent_success(self, client):
        """Test 1: Agent registration succeeds with valid data."""
        payload = {
            "company_name": "Swiggy",
            "industry_category": "Food Delivery",
            "webhook_url": "https://api.swiggy.com/agent/webhook",
            "interest_manifesto": "Food delivery offers and discounts.",
            "trust_score": 1.0,
        }
        response = client.post("/api/v1/agents/register", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["company_name"] == "Swiggy"
        assert data["industry_category"] == "Food Delivery"
        assert data["webhook_url"] == "https://api.swiggy.com/agent/webhook"
        assert data["interest_manifesto"] == "Food delivery offers and discounts."
        assert data["trust_score"] == 1.0
        assert data["interest_embedding"] is None
        assert "id" in data
        assert "created_at" in data
        # Validate ID is a valid UUID
        assert uuid.UUID(data["id"])

    def test_register_agent_default_trust_score(self, client):
        """Test default trust_score is 1.0 when omitted."""
        payload = {
            "company_name": "PhonePe",
            "industry_category": "FinTech",
            "interest_manifesto": "UPI and digital payments.",
        }
        response = client.post("/api/v1/agents/register", json=payload)
        assert response.status_code == 201
        assert response.json()["trust_score"] == 1.0

    def test_register_duplicate_agent_rejected(self, client):
        """Test 2: Duplicate agent registration returns 409 Conflict."""
        payload = {
            "company_name": "HDFC Bank",
            "industry_category": "Banking",
            "interest_manifesto": "Credit cards and banking services.",
        }
        resp1 = client.post("/api/v1/agents/register", json=payload)
        assert resp1.status_code == 201

        # Attempt to register with the same company name
        resp2 = client.post("/api/v1/agents/register", json=payload)
        assert resp2.status_code == 409
        assert "already exists" in resp2.json()["detail"]


class TestAgentListing:
    """Task 6.3: Listing agents."""

    def test_list_agents_empty(self, client):
        """Listing agents on fresh database returns an empty list."""
        response = client.get("/api/v1/agents")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_agents_multiple(self, client):
        """Test 3: Listing agents returns all registered agents."""
        for name, category in [("Swiggy", "Food Delivery"), ("PhonePe", "FinTech")]:
            client.post(
                "/api/v1/agents/register",
                json={
                    "company_name": name,
                    "industry_category": category,
                    "interest_manifesto": f"{name} interest manifesto",
                },
            )

        response = client.get("/api/v1/agents")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = [agent["company_name"] for agent in data]
        assert "Swiggy" in names
        assert "PhonePe" in names


class TestAgentGetById:
    """Task 6.4: Getting agent by ID."""

    def test_get_agent_by_id_success(self, client):
        """Test 4: Retrieve agent by ID returns correct agent."""
        reg_resp = client.post(
            "/api/v1/agents/register",
            json={
                "company_name": "Bajaj Auto",
                "industry_category": "Automobile",
                "interest_manifesto": "Motorcycle launches and auto finance.",
            },
        )
        agent_id = reg_resp.json()["id"]

        response = client.get(f"/api/v1/agents/{agent_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == agent_id
        assert data["company_name"] == "Bajaj Auto"

    def test_get_agent_nonexistent_returns_404(self, client):
        """Getting a non-existent UUID returns 404 Not Found."""
        random_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/agents/{random_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_agent_invalid_uuid_returns_400(self, client):
        """Getting with invalid UUID format returns 400 Bad Request."""
        response = client.get("/api/v1/agents/invalid-not-a-uuid")
        assert response.status_code == 400
        assert "not a valid uuid" in response.json()["detail"].lower()


class TestAgentUpdate:
    """Task 6.5: Updating an agent."""

    def test_update_agent_success(self, client):
        """Test 5: Updating agent details succeeds."""
        reg_resp = client.post(
            "/api/v1/agents/register",
            json={
                "company_name": "Google Pay",
                "industry_category": "Digital Payments",
                "interest_manifesto": "UPI and cashback.",
            },
        )
        agent_id = reg_resp.json()["id"]

        update_payload = {
            "interest_manifesto": "UPI, cashback, and merchant gift cards.",
            "trust_score": 0.95,
        }
        response = client.put(f"/api/v1/agents/{agent_id}", json=update_payload)
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == agent_id
        assert data["interest_manifesto"] == "UPI, cashback, and merchant gift cards."
        assert data["trust_score"] == 0.95
        assert data["company_name"] == "Google Pay"  # Unchanged

    def test_update_agent_nonexistent_returns_404(self, client):
        """Updating a non-existent agent returns 404."""
        random_id = str(uuid.uuid4())
        response = client.put(
            f"/api/v1/agents/{random_id}",
            json={"company_name": "Unknown"},
        )
        assert response.status_code == 404

    def test_update_agent_invalid_uuid_returns_400(self, client):
        """Updating with invalid UUID format returns 400."""
        response = client.put("/api/v1/agents/not-a-uuid", json={"trust_score": 0.8})
        assert response.status_code == 400


class TestAgentDelete:
    """Task 6.6: Deleting an agent."""

    def test_delete_agent_success(self, client):
        """Test 6: Deleting an agent succeeds and subsequent GET returns 404."""
        reg_resp = client.post(
            "/api/v1/agents/register",
            json={
                "company_name": "Temporary Agent",
                "industry_category": "Testing",
                "interest_manifesto": "To be deleted.",
            },
        )
        agent_id = reg_resp.json()["id"]

        # Delete agent
        del_resp = client.delete(f"/api/v1/agents/{agent_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "success"

        # Verify agent is gone
        get_resp = client.get(f"/api/v1/agents/{agent_id}")
        assert get_resp.status_code == 404

    def test_delete_agent_nonexistent_returns_404(self, client):
        """Deleting non-existent agent returns 404."""
        random_id = str(uuid.uuid4())
        response = client.delete(f"/api/v1/agents/{random_id}")
        assert response.status_code == 404

    def test_delete_agent_invalid_uuid_returns_400(self, client):
        """Deleting with invalid UUID returns 400."""
        response = client.delete("/api/v1/agents/not-a-uuid")
        assert response.status_code == 400
