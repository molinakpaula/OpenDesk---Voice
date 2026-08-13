"""HTTP-level tests for the fictional MaderaFlow support API."""

import asyncio
import json
import unittest
from typing import Any
from urllib.parse import urlsplit

from main import LOTS, app


async def request(url: str) -> tuple[int, dict[str, Any]]:
    """Send one GET request directly through the ASGI application."""
    parsed_url = urlsplit(url)
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
        "path": parsed_url.path,
        "raw_path": parsed_url.path.encode("ascii"),
        "query_string": parsed_url.query.encode("ascii"),
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
    def get(self, url: str) -> tuple[int, dict[str, Any]]:
        return asyncio.run(request(url))

    def test_health_endpoint(self) -> None:
        status, body = self.get("/health")

        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "ok"})

    def test_organization_endpoint(self) -> None:
        status, body = self.get("/organization")

        self.assertEqual(status, 200)
        self.assertEqual(body["name"], "MaderaFlow")
        self.assertTrue(body["fictional"])
        self.assertEqual(body["headquarters"], "Puerto Maldonado, Peru")
        self.assertEqual(set(body["supported_languages"]), {"en", "es", "pt"})

    def test_configured_lots_contain_required_operational_fields(self) -> None:
        required_fields = {
            "species",
            "volume_board_feet",
            "current_moisture_percentage",
            "target_moisture_percentage",
            "drying_status",
            "estimated_completion_date",
            "destination",
            "documentation_status",
            "transport_readiness",
        }

        self.assertEqual({lot["lot_id"] for lot in LOTS.values()}, {
            "MF-204",
            "MF-317",
            "MF-422",
        })
        for lot in LOTS.values():
            with self.subTest(lot_id=lot["lot_id"]):
                self.assertTrue(required_fields.issubset(lot))

    def test_all_three_caller_profiles(self) -> None:
        expected_types = {
            "US-BUYER-001": "buyer",
            "PE-SUPPLIER-001": "supplier",
            "BR-LOGISTICS-001": "transport_partner",
        }

        for caller_id, caller_type in expected_types.items():
            with self.subTest(caller_id=caller_id):
                status, body = self.get(f"/callers/{caller_id}")
                self.assertEqual(status, 200)
                self.assertEqual(body["caller_id"], caller_id)
                self.assertEqual(body["caller_type"], caller_type)
                self.assertTrue(body["fictional"])

    def test_all_supported_languages(self) -> None:
        examples = {
            "US-BUYER-001": ("en", "The latest recorded moisture"),
            "PE-SUPPLIER-001": ("es", "El estado de la documentación"),
            "BR-LOGISTICS-001": ("pt", "A situação de coleta"),
        }

        for caller_id, (language, phrase) in examples.items():
            with self.subTest(language=language):
                status, body = self.get(f"/lots/MF-204?caller_id={caller_id}")
                self.assertEqual(status, 200)
                self.assertEqual(body["language"], language)
                self.assertIn(phrase, body["spoken_message"])

    def test_caller_id_is_case_insensitive(self) -> None:
        status, body = self.get("/callers/us-buyer-001")

        self.assertEqual(status, 200)
        self.assertEqual(body["caller_id"], "US-BUYER-001")

    def test_lot_id_is_case_insensitive(self) -> None:
        status, body = self.get("/lots/mf-204?caller_id=US-BUYER-001")

        self.assertEqual(status, 200)
        self.assertEqual(body["lot_id"], "MF-204")

    def test_buyer_receives_drying_and_shipment_information(self) -> None:
        status, body = self.get("/lots/MF-204?caller_id=US-BUYER-001")

        self.assertEqual(status, 200)
        self.assertEqual(body["caller_type"], "buyer")
        self.assertIn("drying_status", body)
        self.assertIn("latest_recorded_moisture_percentage", body)
        self.assertIn("target_moisture_percentage", body)
        self.assertIn("estimated_completion_date", body)
        self.assertIn("shipment_readiness", body)
        self.assertIn("not guaranteed", body["spoken_message"])

    def test_supplier_receives_receipt_document_and_action_information(self) -> None:
        status, body = self.get("/lots/MF-317?caller_id=PE-SUPPLIER-001")

        self.assertEqual(status, 200)
        self.assertEqual(body["caller_type"], "supplier")
        self.assertTrue(body["received"])
        self.assertEqual(body["documentation_status"], "supplier_documents_pending")
        self.assertTrue(body["supplier_action_required"])
        self.assertNotIn("latest_recorded_moisture_percentage", body)

    def test_transport_partner_receives_collection_information(self) -> None:
        status, body = self.get("/lots/MF-422?caller_id=BR-LOGISTICS-001")

        self.assertEqual(status, 200)
        self.assertEqual(body["caller_type"], "transport_partner")
        self.assertFalse(body["collection_ready"])
        self.assertEqual(body["destination"], "Rio Branco, Brazil")
        self.assertFalse(body["transport_can_be_scheduled"])

    def test_high_priority_buyer_escalation(self) -> None:
        delayed_status, delayed = self.get("/lots/MF-317?caller_id=US-BUYER-001")
        quality_status, quality = self.get("/lots/MF-422?caller_id=US-BUYER-001")
        normal_status, normal = self.get("/lots/MF-204?caller_id=US-BUYER-001")

        self.assertEqual((delayed_status, quality_status, normal_status), (200, 200, 200))
        self.assertTrue(delayed["escalation_recommended"])
        self.assertTrue(quality["escalation_recommended"])
        self.assertFalse(normal["escalation_recommended"])

    def test_unknown_caller_returns_404(self) -> None:
        status, body = self.get("/lots/MF-204?caller_id=UNKNOWN")

        self.assertEqual(status, 404)
        self.assertIn("Unknown fictional caller", body["detail"])

    def test_unknown_lot_returns_404(self) -> None:
        status, body = self.get("/lots/MF-999?caller_id=US-BUYER-001")

        self.assertEqual(status, 404)
        self.assertIn("Unknown fictional lot", body["detail"])

    def test_transport_response_excludes_confidential_buyer_information(self) -> None:
        status, body = self.get("/lots/MF-204?caller_id=BR-LOGISTICS-001")
        serialized_body = json.dumps(body).lower()

        self.assertEqual(status, 200)
        self.assertNotIn("price", serialized_body)
        self.assertNotIn("buyer", serialized_body)
        self.assertNotIn("procurement", serialized_body)
        self.assertNotIn("latest_recorded_moisture_percentage", body)
        self.assertNotIn("estimated_completion_date", body)


if __name__ == "__main__":
    unittest.main()
