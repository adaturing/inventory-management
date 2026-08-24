"""
Tests for restocking API endpoints.
"""
import pytest


class TestRestockingEndpoints:
    """Test suite for restocking-related endpoints."""

    def test_get_recommendations(self, client):
        """Test getting restock recommendations."""
        response = client.get("/api/restocking/recommendations")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        first = data[0]
        for field in [
            "item_sku", "item_name", "current_demand", "forecasted_demand",
            "trend", "warehouse", "category", "unit_cost", "urgency_score",
            "suggested_quantity", "suggested_cost"
        ]:
            assert field in first

    def test_recommendations_sorted_by_urgency(self, client):
        """Test that recommendations are sorted by urgency score descending."""
        response = client.get("/api/restocking/recommendations")
        data = response.json()

        scores = [item["urgency_score"] for item in data]
        assert scores == sorted(scores, reverse=True)

    def test_recommendations_by_warehouse(self, client):
        """Test filtering recommendations by warehouse."""
        response = client.get("/api/restocking/recommendations?warehouse=Tokyo")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0
        for item in data:
            assert item["warehouse"] == "Tokyo"

    def test_recommendations_by_category(self, client):
        """Test filtering recommendations by category."""
        response = client.get("/api/restocking/recommendations?category=actuators")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0
        for item in data:
            assert item["category"].lower() == "actuators"

    def test_recommendations_multiple_filters(self, client):
        """Test filtering recommendations with warehouse and category combined."""
        response = client.get(
            "/api/restocking/recommendations?warehouse=San Francisco&category=power supplies"
        )
        assert response.status_code == 200

        data = response.json()
        for item in data:
            assert item["warehouse"] == "San Francisco"
            assert item["category"].lower() == "power supplies"

    def test_recommendation_cost_calculation(self, client):
        """Test that suggested_cost matches suggested_quantity * unit_cost."""
        response = client.get("/api/restocking/recommendations")
        data = response.json()

        for item in data:
            expected_cost = item["suggested_quantity"] * item["unit_cost"]
            assert abs(item["suggested_cost"] - expected_cost) < 0.01

    def test_place_restock_order(self, client):
        """Test placing a restock order with valid items."""
        payload = {
            "items": [
                {"sku": "WDG-001", "name": "Industrial Widget Type A", "quantity": 50, "unit_cost": 12.50}
            ],
            "warehouse": "San Francisco"
        }
        response = client.post("/api/restocking/orders", json=payload)
        assert response.status_code == 201

        order = response.json()
        assert order["source"] == "restocking"
        assert order["status"] == "Processing"
        assert order["total_value"] == 625.0
        assert isinstance(order["lead_time_days"], int)
        assert 3 <= order["lead_time_days"] <= 14
        assert order["warehouse"] == "San Francisco"

    def test_restock_order_lead_time_matches_delivery_dates(self, client):
        """Test that expected_delivery is order_date plus lead_time_days."""
        from datetime import datetime

        payload = {
            "items": [
                {"sku": "SNR-420", "name": "Temperature Sensor Module", "quantity": 10, "unit_cost": 65.0}
            ]
        }
        response = client.post("/api/restocking/orders", json=payload)
        order = response.json()

        order_date = datetime.fromisoformat(order["order_date"])
        expected_delivery = datetime.fromisoformat(order["expected_delivery"])
        assert (expected_delivery - order_date).days == order["lead_time_days"]

    def test_restock_order_appears_in_orders(self, client):
        """Test that a placed restock order appears in the orders list."""
        payload = {
            "items": [
                {"sku": "CTL-330", "name": "Logic Controller Board", "quantity": 5, "unit_cost": 120.0}
            ]
        }
        create_response = client.post("/api/restocking/orders", json=payload)
        new_order = create_response.json()

        orders_response = client.get("/api/orders")
        all_orders = orders_response.json()
        matching = [o for o in all_orders if o["id"] == new_order["id"]]

        assert len(matching) == 1
        assert matching[0]["source"] == "restocking"

    def test_place_restock_order_empty_items(self, client):
        """Test that placing an order with no items is rejected."""
        response = client.post("/api/restocking/orders", json={"items": []})
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data
