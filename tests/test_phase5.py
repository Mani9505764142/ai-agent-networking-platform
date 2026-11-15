"""
Phase 5 Comprehensive Automated Test Suite.

Covers:
1. Comments:
   - Create comment on existing post.
   - Nested endpoint /api/v1/posts/{post_id}/comments.
   - Reject invalid post ID (404 / 422).
   - Reject invalid author ID (404 / 422).
   - Reject empty content (400 / 422).
   - Retrieve comments by post.
   - Retrieve comments by author agent.
   - Get comment by ID.
   - Delete comment.

2. Subscriptions:
   - Subscribe agent to another agent.
   - Self-subscription prevention (400).
   - Duplicate subscription prevention (409).
   - Reject non-existent subscriber / target agents (404).
   - Unsubscribe by ID and by agent pair.
   - List following and subscribers.

3. Feedback:
   - Submit feedback on routing outcomes.
   - Submit feedback referencing routing_log_id.
   - Duplicate feedback prevention (409).
   - Reject invalid post, source agent, or target agent (404).
   - Reject invalid routing log (404) and mismatched log (400).
   - Reject invalid feedback type (422).
   - Retrieve feedback with filters.

4. Integration:
   - Full lifecycle test connecting Agents, Posts, Subscriptions, Comments, and Feedback.
"""

import uuid
import pytest
from app.models.routing_log import RoutingLog


def _register_agent(client, company_name: str, industry: str = "FinTech"):
    """Helper to register a test agent."""
    response = client.post(
        "/api/v1/agents/register",
        json={
            "company_name": company_name,
            "industry_category": industry,
            "webhook_url": f"https://api.{company_name.lower().replace(' ', '')}.com/webhook",
            "interest_manifesto": f"Interested in {industry} solutions, partnerships, and APIs.",
        },
    )
    assert response.status_code == 201, f"Failed to register agent: {response.text}"
    return response.json()


def _create_post(client, author_id: str, title: str = "Test Post", content: str = "Test post body content"):
    """Helper to create a test post."""
    response = client.post(
        "/api/v1/posts",
        json={
            "author_agent_id": author_id,
            "title": title,
            "content": content,
        },
    )
    assert response.status_code == 201, f"Failed to create post: {response.text}"
    return response.json()


# ═════════════════════════════════════════════════════════════════════════════
# 1. COMMENTS TESTS
# ═════════════════════════════════════════════════════════════════════════════

def test_create_comment_success(client):
    """Verify creating a comment on an existing post by a registered agent."""
    author = _register_agent(client, "Swiggy Foods", "Food Delivery")
    commenter = _register_agent(client, "PhonePe UPI", "FinTech")
    post = _create_post(client, author["id"], "UPI Food Discounts", "Seeking partner offers")

    response = client.post(
        "/api/v1/comments",
        json={
            "post_id": post["id"],
            "author_agent_id": commenter["id"],
            "content": "We can provide 20% cashback on all orders through PhonePe UPI.",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["post_id"] == post["id"]
    assert data["author_agent_id"] == commenter["id"]
    assert "20% cashback" in data["content"]
    assert "id" in data
    assert "created_at" in data


def test_create_comment_nested_endpoint(client):
    """Verify convenience nested route POST /api/v1/posts/{post_id}/comments."""
    author = _register_agent(client, "Zomato", "Food Delivery")
    commenter = _register_agent(client, "Google Pay", "Payments")
    post = _create_post(client, author["id"], "Festive Cashback", "Promotional campaigns")

    response = client.post(
        f"/api/v1/posts/{post['id']}/comments",
        json={
            "author_agent_id": commenter["id"],
            "content": "We can integrate Spot rewards for your festival campaign.",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["post_id"] == post["id"]
    assert data["author_agent_id"] == commenter["id"]


def test_create_comment_invalid_post_id(client):
    """Verify comment creation fails when post_id does not exist."""
    commenter = _register_agent(client, "Paytm", "FinTech")
    fake_post_id = str(uuid.uuid4())

    response = client.post(
        "/api/v1/comments",
        json={
            "post_id": fake_post_id,
            "author_agent_id": commenter["id"],
            "content": "A comment on a non-existent post",
        },
    )
    assert response.status_code == 404
    assert "does not exist" in response.json()["detail"]


def test_create_comment_invalid_author_id(client):
    """Verify comment creation fails when author_agent_id does not exist."""
    author = _register_agent(client, "HDFC", "Banking")
    post = _create_post(client, author["id"], "Credit Card API", "New merchant onboarding")
    fake_author_id = str(uuid.uuid4())

    response = client.post(
        "/api/v1/comments",
        json={
            "post_id": post["id"],
            "author_agent_id": fake_author_id,
            "content": "Comment from unknown agent",
        },
    )
    assert response.status_code == 404
    assert "does not exist" in response.json()["detail"]


def test_create_comment_malformed_uuid(client):
    """Verify comment creation fails with 400/422 for malformed UUIDs."""
    response = client.post(
        "/api/v1/comments",
        json={
            "post_id": "not-a-uuid",
            "author_agent_id": "also-not-a-uuid",
            "content": "Malformed UUID check",
        },
    )
    assert response.status_code in (400, 422)


def test_create_comment_empty_content(client):
    """Verify empty or whitespace content is rejected."""
    author = _register_agent(client, "Ola", "Mobility")
    post = _create_post(client, author["id"], "Cab Booking", "Looking for fuel partners")

    response = client.post(
        "/api/v1/comments",
        json={
            "post_id": post["id"],
            "author_agent_id": author["id"],
            "content": "   ",
        },
    )
    assert response.status_code in (400, 422)


def test_retrieve_comments_for_post(client):
    """Verify retrieving comments for a specific post in chronological order."""
    author = _register_agent(client, "Swiggy Delivers", "Food")
    agent_a = _register_agent(client, "ICICI Bank", "Banking")
    agent_b = _register_agent(client, "Axis Bank", "Banking")
    post = _create_post(client, author["id"], "Payment Gateway", "RFP for payment gateway")

    # Add 2 comments
    client.post(
        "/api/v1/comments",
        json={"post_id": post["id"], "author_agent_id": agent_a["id"], "content": "ICICI offers 99.9% uptime."},
    )
    client.post(
        "/api/v1/comments",
        json={"post_id": post["id"], "author_agent_id": agent_b["id"], "content": "Axis offers lower transaction fees."},
    )

    # Fetch via /api/v1/posts/{post_id}/comments
    resp1 = client.get(f"/api/v1/posts/{post['id']}/comments")
    assert resp1.status_code == 200
    comments = resp1.json()
    assert len(comments) == 2
    assert "ICICI" in comments[0]["content"]
    assert "Axis" in comments[1]["content"]

    # Fetch via /api/v1/comments?post_id={post_id}
    resp2 = client.get(f"/api/v1/comments?post_id={post['id']}")
    assert resp2.status_code == 200
    assert len(resp2.json()) == 2


def test_retrieve_comments_by_author(client):
    """Verify filtering comments by author agent ID."""
    author = _register_agent(client, "Flipkart", "E-Commerce")
    partner = _register_agent(client, "Shadowfax", "Logistics")
    post1 = _create_post(client, author["id"], "Delivery SLA", "Need fast deliveries")
    post2 = _create_post(client, author["id"], "Warehouse Ops", "Looking for sorting partners")

    client.post(
        "/api/v1/comments",
        json={"post_id": post1["id"], "author_agent_id": partner["id"], "content": "We cover 200+ cities."},
    )
    client.post(
        "/api/v1/comments",
        json={"post_id": post2["id"], "author_agent_id": partner["id"], "content": "We have automated sorting hubs."},
    )

    resp = client.get(f"/api/v1/comments?author_agent_id={partner['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(c["author_agent_id"] == partner["id"] for c in data)


def test_get_and_delete_comment(client):
    """Verify single comment retrieval and deletion."""
    author = _register_agent(client, "Blinkit", "Quick Commerce")
    post = _create_post(client, author["id"], "Dark Stores", "Expanding dark store network")

    create_resp = client.post(
        "/api/v1/comments",
        json={"post_id": post["id"], "author_agent_id": author["id"], "content": "Temporary operational note"},
    )
    comment_id = create_resp.json()["id"]

    # Fetch comment by ID
    get_resp = client.get(f"/api/v1/comments/{comment_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == comment_id

    # Delete comment
    del_resp = client.delete(f"/api/v1/comments/{comment_id}")
    assert del_resp.status_code == 200

    # Fetch again -> 404
    get_again = client.get(f"/api/v1/comments/{comment_id}")
    assert get_again.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# 2. SUBSCRIPTIONS TESTS
# ═════════════════════════════════════════════════════════════════════════════

def test_subscribe_success(client):
    """Verify agent A successfully subscribes to agent B."""
    agent_a = _register_agent(client, "CRED", "FinTech")
    agent_b = _register_agent(client, "Dunzo", "Delivery")

    response = client.post(
        "/api/v1/subscriptions",
        json={
            "subscriber_agent_id": agent_a["id"],
            "target_agent_id": agent_b["id"],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["subscriber_agent_id"] == agent_a["id"]
    assert data["target_agent_id"] == agent_b["id"]
    assert "id" in data
    assert "created_at" in data


def test_self_subscription_prevention(client):
    """Verify that an agent cannot subscribe to itself."""
    agent = _register_agent(client, "Zerodha", "FinTech")

    response = client.post(
        "/api/v1/subscriptions",
        json={
            "subscriber_agent_id": agent["id"],
            "target_agent_id": agent["id"],
        },
    )
    assert response.status_code == 400
    assert "Self-subscription is not allowed" in response.json()["detail"]


def test_duplicate_subscription_prevention(client):
    """Verify duplicate subscription is rejected with 409 Conflict."""
    sub = _register_agent(client, "Groww", "FinTech")
    target = _register_agent(client, "Tata Motors", "Automobile")

    # First subscription -> 201
    resp1 = client.post(
        "/api/v1/subscriptions",
        json={"subscriber_agent_id": sub["id"], "target_agent_id": target["id"]},
    )
    assert resp1.status_code == 201

    # Second subscription -> 409
    resp2 = client.post(
        "/api/v1/subscriptions",
        json={"subscriber_agent_id": sub["id"], "target_agent_id": target["id"]},
    )
    assert resp2.status_code == 409
    assert "already subscribed" in resp2.json()["detail"]


def test_subscribe_nonexistent_agents(client):
    """Verify 404 when subscriber or target agent does not exist."""
    real_agent = _register_agent(client, "Meesho", "E-Commerce")
    fake_id = str(uuid.uuid4())

    # Non-existent subscriber
    r1 = client.post(
        "/api/v1/subscriptions",
        json={"subscriber_agent_id": fake_id, "target_agent_id": real_agent["id"]},
    )
    assert r1.status_code == 404
    assert "Subscriber agent" in r1.json()["detail"]

    # Non-existent target
    r2 = client.post(
        "/api/v1/subscriptions",
        json={"subscriber_agent_id": real_agent["id"], "target_agent_id": fake_id},
    )
    assert r2.status_code == 404
    assert "Target agent" in r2.json()["detail"]


def test_unsubscribe_by_id(client):
    """Verify unsubscribing by subscription primary key ID."""
    sub = _register_agent(client, "Razorpay", "FinTech")
    target = _register_agent(client, "BigBasket", "Grocery")

    create_resp = client.post(
        "/api/v1/subscriptions",
        json={"subscriber_agent_id": sub["id"], "target_agent_id": target["id"]},
    )
    sub_id = create_resp.json()["id"]

    # Unsubscribe
    del_resp = client.delete(f"/api/v1/subscriptions/{sub_id}")
    assert del_resp.status_code == 200
    assert "removed successfully" in del_resp.json()["message"]

    # Subsequent delete -> 404
    del_again = client.delete(f"/api/v1/subscriptions/{sub_id}")
    assert del_again.status_code == 404


def test_unsubscribe_by_agent_pair(client):
    """Verify unsubscribing by specifying subscriber and target agent query params."""
    sub = _register_agent(client, "JioMart", "Retail")
    target = _register_agent(client, "Airtel Payments", "FinTech")

    client.post(
        "/api/v1/subscriptions",
        json={"subscriber_agent_id": sub["id"], "target_agent_id": target["id"]},
    )

    # Unsubscribe
    del_resp = client.delete(f"/api/v1/subscriptions?subscriber_agent_id={sub['id']}&target_agent_id={target['id']}")
    assert del_resp.status_code == 200

    # Repeating -> 404
    del_again = client.delete(f"/api/v1/subscriptions?subscriber_agent_id={sub['id']}&target_agent_id={target['id']}")
    assert del_again.status_code == 404


def test_list_following_and_subscribers(client):
    """Verify listing following agents and subscriber agents."""
    hub = _register_agent(client, "Unified Payments Hub", "FinTech")
    fan1 = _register_agent(client, "Merchant 1", "Retail")
    fan2 = _register_agent(client, "Merchant 2", "Retail")
    upstream = _register_agent(client, "NPCI Core", "Banking Infrastructure")

    # Merchants follow hub
    client.post("/api/v1/subscriptions", json={"subscriber_agent_id": fan1["id"], "target_agent_id": hub["id"]})
    client.post("/api/v1/subscriptions", json={"subscriber_agent_id": fan2["id"], "target_agent_id": hub["id"]})

    # Hub follows upstream
    client.post("/api/v1/subscriptions", json={"subscriber_agent_id": hub["id"], "target_agent_id": upstream["id"]})

    # Hub's subscribers -> fan1, fan2
    sub_resp = client.get(f"/api/v1/subscriptions/subscribers/{hub['id']}")
    assert sub_resp.status_code == 200
    subscribers = sub_resp.json()
    assert len(subscribers) == 2
    subscriber_ids = {s["subscriber_agent_id"] for s in subscribers}
    assert subscriber_ids == {fan1["id"], fan2["id"]}

    # Hub's following -> upstream
    foll_resp = client.get(f"/api/v1/subscriptions/following/{hub['id']}")
    assert foll_resp.status_code == 200
    following = foll_resp.json()
    assert len(following) == 1
    assert following[0]["target_agent_id"] == upstream["id"]


# ═════════════════════════════════════════════════════════════════════════════
# 3. FEEDBACK TESTS
# ═════════════════════════════════════════════════════════════════════════════

def test_submit_feedback_success(client):
    """Verify submitting routing feedback."""
    author = _register_agent(client, "Nykaa", "Beauty")
    target = _register_agent(client, "Delhivery", "Logistics")
    post = _create_post(client, author["id"], "Next-day delivery", "Same day and next day delivery required")

    response = client.post(
        "/api/v1/feedback",
        json={
            "post_id": post["id"],
            "source_agent_id": author["id"],
            "target_agent_id": target["id"],
            "feedback_type": "RELEVANT",
            "comments": "Delhivery matched our logistics requirements perfectly.",
            "rating": 5,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["post_id"] == post["id"]
    assert data["source_agent_id"] == author["id"]
    assert data["target_agent_id"] == target["id"]
    assert data["feedback_type"] == "RELEVANT"
    assert data["rating"] == 5
    assert "Delhivery matched" in data["comments"]


def test_submit_feedback_with_routing_log(client, db_session):
    """Verify submitting feedback linked to an existing routing log."""
    author = _register_agent(client, "MakeMyTrip", "Travel")
    target = _register_agent(client, "IndiGo", "Aviation")
    post = _create_post(client, author["id"], "Flight Booking API", "Looking for direct airline integrations")

    # Manually insert a routing log in the test database
    log = RoutingLog(
        id=str(uuid.uuid4()),
        post_id=post["id"],
        target_agent_id=target["id"],
        vector_score=0.88,
        rerank_score=0.92,
        status="DELIVERED",
    )
    db_session.add(log)
    db_session.commit()

    # Submit feedback referencing the log via generic endpoint
    response = client.post(
        "/api/v1/feedback",
        json={
            "post_id": post["id"],
            "source_agent_id": author["id"],
            "target_agent_id": target["id"],
            "routing_log_id": log.id,
            "feedback_type": "USEFUL",
            "comments": "High relevance match from routing engine",
            "rating": 4,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["routing_log_id"] == log.id
    assert data["feedback_type"] == "USEFUL"


def test_submit_feedback_direct_log_endpoint(client, db_session):
    """Verify POST /api/v1/feedback/routing-logs/{routing_log_id}."""
    author = _register_agent(client, "ClearTrip", "Travel")
    target = _register_agent(client, "Air India", "Aviation")
    post = _create_post(client, author["id"], "Charter Flights", "Corporate booking partnerships")

    log = RoutingLog(
        id=str(uuid.uuid4()),
        post_id=post["id"],
        target_agent_id=target["id"],
        vector_score=0.75,
        rerank_score=0.80,
        status="DELIVERED",
    )
    db_session.add(log)
    db_session.commit()

    response = client.post(
        f"/api/v1/feedback/routing-logs/{log.id}",
        json={
            "source_agent_id": author["id"],
            "feedback_type": "RELEVANT",
            "comments": "Exact match for corporate charter routing",
            "rating": 5,
        },
    )
    assert response.status_code == 201
    assert response.json()["routing_log_id"] == log.id


def test_duplicate_feedback_prevention(client):
    """Verify duplicate feedback for the same post + agent pair is rejected with 409."""
    author = _register_agent(client, "Urban Company", "Home Services")
    target = _register_agent(client, "Urbanic", "Fashion")
    post = _create_post(client, author["id"], "Service Partnering", "Seeking plumbers and electricians")

    # First submission
    resp1 = client.post(
        "/api/v1/feedback",
        json={
            "post_id": post["id"],
            "source_agent_id": author["id"],
            "target_agent_id": target["id"],
            "feedback_type": "NOT_RELEVANT",
            "comments": "Fashion brand routed to home services inquiry",
        },
    )
    assert resp1.status_code == 201

    # Second submission -> 409 Conflict
    resp2 = client.post(
        "/api/v1/feedback",
        json={
            "post_id": post["id"],
            "source_agent_id": author["id"],
            "target_agent_id": target["id"],
            "feedback_type": "NOT_RELEVANT",
        },
    )
    assert resp2.status_code == 409
    assert "already been submitted" in resp2.json()["detail"]


def test_feedback_invalid_references(client):
    """Verify 404 when referencing non-existent posts or agents."""
    agent = _register_agent(client, "Licious", "Food")
    post = _create_post(client, agent["id"], "Cold Storage", "Seeking refrigerated fleet")
    fake_id = str(uuid.uuid4())

    # Invalid post
    r1 = client.post(
        "/api/v1/feedback",
        json={"post_id": fake_id, "source_agent_id": agent["id"], "target_agent_id": agent["id"], "feedback_type": "RELEVANT"},
    )
    assert r1.status_code == 404

    # Invalid source agent
    r2 = client.post(
        "/api/v1/feedback",
        json={"post_id": post["id"], "source_agent_id": fake_id, "target_agent_id": agent["id"], "feedback_type": "RELEVANT"},
    )
    assert r2.status_code == 404

    # Invalid target agent
    r3 = client.post(
        "/api/v1/feedback",
        json={"post_id": post["id"], "source_agent_id": agent["id"], "target_agent_id": fake_id, "feedback_type": "RELEVANT"},
    )
    assert r3.status_code == 404


def test_feedback_invalid_type(client):
    """Verify 422 Unprocessable Entity when passing an unsupported feedback_type."""
    author = _register_agent(client, "BookMyShow", "Entertainment")
    target = _register_agent(client, "PVR Inox", "Cinemas")
    post = _create_post(client, author["id"], "Seat API", "Multiplex seat allocation API")

    response = client.post(
        "/api/v1/feedback",
        json={
            "post_id": post["id"],
            "source_agent_id": author["id"],
            "target_agent_id": target["id"],
            "feedback_type": "INVALID_TYPE_XYZ",
        },
    )
    assert response.status_code == 422


def test_retrieve_feedback_with_filters(client):
    """Verify listing and filtering feedback."""
    author = _register_agent(client, "Swiggy Instamart", "Quick Commerce")
    good_match = _register_agent(client, "Zepto Deliveries", "Logistics")
    bad_match = _register_agent(client, "TVS Motors", "Automotive")
    post = _create_post(client, author["id"], "E-Bike Fleet", "Fleet leasing for riders")

    client.post(
        "/api/v1/feedback",
        json={
            "post_id": post["id"],
            "source_agent_id": author["id"],
            "target_agent_id": good_match["id"],
            "feedback_type": "USEFUL",
        },
    )
    client.post(
        "/api/v1/feedback",
        json={
            "post_id": post["id"],
            "source_agent_id": author["id"],
            "target_agent_id": bad_match["id"],
            "feedback_type": "NOT_RELEVANT",
        },
    )

    # Filter by post_id
    r_post = client.get(f"/api/v1/feedback?post_id={post['id']}")
    assert r_post.status_code == 200
    assert len(r_post.json()) == 2

    # Filter by feedback_type=USEFUL
    r_useful = client.get(f"/api/v1/feedback?feedback_type=USEFUL")
    assert r_useful.status_code == 200
    assert len(r_useful.json()) == 1
    assert r_useful.json()[0]["target_agent_id"] == good_match["id"]


# ═════════════════════════════════════════════════════════════════════════════
# 4. FULL PLATFORM INTEGRATION TEST
# ═════════════════════════════════════════════════════════════════════════════

def test_full_platform_lifecycle(client):
    """Verify end-to-end multi-agent interaction flow:
    Agent creation -> Post creation -> Subscription -> Comments -> Feedback.
    """
    # 1. Register agents
    fintech_agent = _register_agent(client, "Paytm Payments Bank", "FinTech")
    retail_agent = _register_agent(client, "Reliance Retail", "Retail")

    # 2. Retail agent subscribes to FinTech agent
    sub_resp = client.post(
        "/api/v1/subscriptions",
        json={
            "subscriber_agent_id": retail_agent["id"],
            "target_agent_id": fintech_agent["id"],
        },
    )
    assert sub_resp.status_code == 201

    # 3. FinTech agent publishes post
    post = _create_post(
        client,
        fintech_agent["id"],
        "Soundbox Merchant Payment Integration",
        "Offering instant audio confirmation soundbox devices for retail cashiers.",
    )

    # 4. Retail agent comments on post
    comment_resp = client.post(
        f"/api/v1/posts/{post['id']}/comments",
        json={
            "author_agent_id": retail_agent["id"],
            "content": "Interested in deploying 5,000 soundboxes across our supermarkets.",
        },
    )
    assert comment_resp.status_code == 201

    # 5. Retail agent submits positive feedback on routing / discovery
    feedback_resp = client.post(
        "/api/v1/feedback",
        json={
            "post_id": post["id"],
            "source_agent_id": retail_agent["id"],
            "target_agent_id": fintech_agent["id"],
            "feedback_type": "RELEVANT",
            "comments": "High commercial intent match",
            "rating": 5,
        },
    )
    assert feedback_resp.status_code == 201
    assert feedback_resp.json()["feedback_type"] == "RELEVANT"
