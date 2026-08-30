class TestRequestIdMiddleware:
    def test_response_carries_a_generated_request_id(self, client):
        response = client.get("/healthz")
        assert "X-Request-Id" in response.headers
        assert len(response.headers["X-Request-Id"]) > 0

    def test_client_supplied_request_id_is_echoed_back(self, client):
        response = client.get("/healthz", headers={"X-Request-Id": "test-correlation-id-123"})
        assert response.headers["X-Request-Id"] == "test-correlation-id-123"
