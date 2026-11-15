"""
Tests for Post Management Endpoints

Covers:
7. Creating a post (POST /api/v1/posts)
8. Creating a post with invalid author ID (HTTP 404 Not Found & HTTP 400 Bad Request)
9. Listing posts (GET /api/v1/posts)
10. Getting a post by ID (GET /api/v1/posts/{post_id})
11. Deleting a post (DELETE /api/v1/posts/{post_id})
"""

import uuid


def _create_sample_agent(client, name="Swiggy", category="Food Delivery"):
    """Helper to create an agent for post tests."""
    resp = client.post(
        "/api/v1/agents/register",
        json={
            "company_name": name,
            "industry_category": category,
            "interest_manifesto": f"{name} interest manifesto",
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


class TestPostCreation:
    """Task 6.7: Creating a post and Task 6.8: Invalid author ID handling."""

    def test_create_post_success(self, client):
        """Test 7: Creating a post with a valid author agent succeeds."""
        agent_id = _create_sample_agent(client, "Swiggy", "Food Delivery")

        payload = {
            "author_agent_id": agent_id,
            "title": "Weekend 50% Off Restaurant Fest",
            "content": "Special promotions across all top-rated restaurants in metro cities.",
        }
        response = client.post("/api/v1/posts", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["author_agent_id"] == agent_id
        assert data["title"] == "Weekend 50% Off Restaurant Fest"
        assert data["content"] == "Special promotions across all top-rated restaurants in metro cities."
        assert data["post_embedding"] is None
        assert "id" in data
        assert "created_at" in data
        assert uuid.UUID(data["id"])

    def test_create_post_nonexistent_author_returns_404(self, client):
        """Test 8a: Creating a post with non-existent author returns 404."""
        nonexistent_author_id = str(uuid.uuid4())
        payload = {
            "author_agent_id": nonexistent_author_id,
            "title": "Ghost Post",
            "content": "This post should not be created.",
        }
        response = client.post("/api/v1/posts", json=payload)
        assert response.status_code == 404
        assert "does not exist" in response.json()["detail"].lower()

    def test_create_post_invalid_author_uuid_returns_400(self, client):
        """Test 8b: Creating a post with malformed author UUID returns 400."""
        payload = {
            "author_agent_id": "not-a-valid-uuid-1234",
            "title": "Malformed Author Post",
            "content": "This post should fail validation.",
        }
        response = client.post("/api/v1/posts", json=payload)
        assert response.status_code == 400
        assert "not a valid uuid" in response.json()["detail"].lower()


class TestPostListing:
    """Task 6.9: Listing posts."""

    def test_list_posts_empty(self, client):
        """Listing posts on fresh database returns an empty list."""
        response = client.get("/api/v1/posts")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_posts_multiple(self, client):
        """Test 9: Listing posts returns all created posts."""
        agent1_id = _create_sample_agent(client, "PhonePe", "FinTech")
        agent2_id = _create_sample_agent(client, "HDFC Bank", "Banking")

        client.post(
            "/api/v1/posts",
            json={
                "author_agent_id": agent1_id,
                "title": "UPI Cashback Rush",
                "content": "Flat 10% cashback on utility payments.",
            },
        )
        client.post(
            "/api/v1/posts",
            json={
                "author_agent_id": agent2_id,
                "title": "New Credit Card Partnership",
                "content": "Exclusive rewards for online shopping.",
            },
        )

        response = client.get("/api/v1/posts")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        titles = [post["title"] for post in data]
        assert "UPI Cashback Rush" in titles
        assert "New Credit Card Partnership" in titles


class TestPostGetById:
    """Task 6.10: Getting a post by ID."""

    def test_get_post_by_id_success(self, client):
        """Test 10: Retrieve post by ID returns correct post."""
        agent_id = _create_sample_agent(client, "Bajaj Auto", "Automobile")

        create_resp = client.post(
            "/api/v1/posts",
            json={
                "author_agent_id": agent_id,
                "title": "New Pulsar Launch Announcement",
                "content": "Introducing the next generation of sport motorcycles.",
            },
        )
        post_id = create_resp.json()["id"]

        response = client.get(f"/api/v1/posts/{post_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == post_id
        assert data["title"] == "New Pulsar Launch Announcement"
        assert data["author_agent_id"] == agent_id

    def test_get_post_nonexistent_returns_404(self, client):
        """Getting a non-existent post UUID returns 404."""
        random_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/posts/{random_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_post_invalid_uuid_returns_400(self, client):
        """Getting a post with invalid UUID format returns 400."""
        response = client.get("/api/v1/posts/invalid-post-uuid")
        assert response.status_code == 400


class TestPostDeletion:
    """Deleting posts."""

    def test_delete_post_success(self, client):
        """Deleting a post succeeds and subsequent GET returns 404."""
        agent_id = _create_sample_agent(client, "Google Pay", "Digital Payments")

        create_resp = client.post(
            "/api/v1/posts",
            json={
                "author_agent_id": agent_id,
                "title": "Temporary Offer",
                "content": "Expires in 10 minutes.",
            },
        )
        post_id = create_resp.json()["id"]

        del_resp = client.delete(f"/api/v1/posts/{post_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "success"

        # Verify post is gone
        get_resp = client.get(f"/api/v1/posts/{post_id}")
        assert get_resp.status_code == 404

    def test_delete_post_nonexistent_returns_404(self, client):
        """Deleting non-existent post returns 404."""
        random_id = str(uuid.uuid4())
        response = client.delete(f"/api/v1/posts/{random_id}")
        assert response.status_code == 404
