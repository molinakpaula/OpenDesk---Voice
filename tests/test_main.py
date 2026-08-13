"""HTTP-level tests for the fictional OpenDesk outage API."""

import asyncio
import json
import unittest

from main import app


async def request(path: str) -> tuple[int, dict[str, str]]:
    """Send one GET request directly through the ASGI application."""
    response_messages: list[dict] = []
    request_sent = False

    async def receive() -> dict:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        response_messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("test-client", 1234),
        "server": ("test-server", 80),
    }

    await app(scope, receive, send)

    status = next(
        message["status"]
        for message in response_messages
        if message["type"] == "http.response.start"
    )
    body = b"".join(
        message.get("body", b"")
        for message in response_messages
        if message["type"] == "http.response.body"
    )
    return status, json.loads(body)


class ApiTests(unittest.TestCase):
    def get(self, path: str) -> tuple[int, dict[str, str]]:
        return asyncio.run(request(path))

    def test_health(self) -> None:
        status, body = self.get("/health")

        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "ok"})

    def test_supported_services(self) -> None:
        expected_statuses = {
            "vpn": "operational",
            "email": "degraded",
            "identity": "operational",
        }

        for service, expected_status in expected_statuses.items():
            with self.subTest(service=service):
                status, body = self.get(f"/outages/{service}")

                self.assertEqual(status, 200)
                self.assertEqual(body["service"], service)
                self.assertEqual(body["status"], expected_status)
                self.assertTrue(body["message"])

    def test_service_name_is_case_insensitive(self) -> None:
        status, body = self.get("/outages/VPN")

        self.assertEqual(status, 200)
        self.assertEqual(body["service"], "vpn")

    def test_unknown_service(self) -> None:
        status, body = self.get("/outages/printer")

        self.assertEqual(status, 404)
        self.assertIn("Unknown service 'printer'", body["detail"])
        self.assertIn("vpn, email, identity", body["detail"])


if __name__ == "__main__":
    unittest.main()
