"""HTTP-level tests for the fictional MaderaFlow support API."""

import asyncio
import json
import unittest
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit
from unittest.mock import patch
from zoneinfo import ZoneInfo

from main import LOTS, app


async def request(
    url: str,
    method: str = "GET",
    json_body: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Send one GET request directly through the ASGI application."""
    parsed_url = urlsplit(url)
    encoded_body = json.dumps(json_body).encode("utf-8") if json_body else b""
    response_messages: list[dict] = []
    request_sent = False

    async def receive() -> dict:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {
                "type": "http.request",
                "body": encoded_body,
                "more_body": False,
            }
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        response_messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": parsed_url.path,
        "raw_path": parsed_url.path.encode("ascii"),
        "query_string": parsed_url.query.encode("ascii"),
        "root_path": "",
        "headers": (
            [(b"content-type", b"application/json")]
            if json_body is not None
            else []
        ),
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

    def post(self, url: str, body: dict[str, str]) -> tuple[int, dict[str, Any]]:
        return asyncio.run(request(url, method="POST", json_body=body))

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

    def test_voice_agent_config_exposes_public_contract(self) -> None:
        status, body = self.get("/voice-agent-config")

        self.assertEqual(status, 200)
        self.assertEqual(body["agent"]["name"], "MaderaFlow Support")
        self.assertTrue(body["agent"]["automated_assistant"])
        self.assertEqual(set(body["agent"]["opening_messages"]), {"en", "es", "pt"})
        self.assertIn("automated voice assistant", body["agent"]["opening_messages"]["en"])
        self.assertIn("automatizado", body["agent"]["opening_messages"]["es"])
        self.assertIn("automatizada", body["agent"]["opening_messages"]["pt"])
        self.assertEqual(body["tool"]["method"], "POST")
        self.assertEqual(body["tool"]["path"], "/support-requests")
        self.assertEqual(
            body["tool"]["required_fields"],
            ["caller_id", "lot_id", "intent"],
        )

    def test_voice_agent_config_does_not_expose_caller_or_lot_records(self) -> None:
        status, body = self.get("/voice-agent-config")
        serialized_body = json.dumps(body).lower()

        self.assertEqual(status, 200)
        self.assertNotIn("callers", body)
        self.assertNotIn("lots", body)
        self.assertNotIn("us-buyer-001", serialized_body)
        self.assertNotIn("pe-supplier-001", serialized_body)
        self.assertNotIn("br-logistics-001", serialized_body)
        self.assertNotIn("mf-204", serialized_body)
        self.assertNotIn("12.8", serialized_body)
        self.assertNotIn("houston", serialized_body)

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
        self.assertIn("documentos del proveedor pendientes", body["spoken_message"])
        self.assertNotIn("supplier_documents_pending", body["spoken_message"])

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

    def test_support_endpoint_resolves_all_three_intents(self) -> None:
        examples = {
            "check_lot_status": "US-BUYER-001",
            "check_documentation": "PE-SUPPLIER-001",
            "check_transport_readiness": "BR-LOGISTICS-001",
        }

        for intent, caller_id in examples.items():
            with self.subTest(intent=intent):
                status, body = self.post(
                    "/support-requests",
                    {"caller_id": caller_id, "lot_id": "MF-204", "intent": intent},
                )
                self.assertEqual(status, 200)
                self.assertTrue(body["resolved"])
                self.assertEqual(body["intent"], intent)
                self.assertTrue(body["spoken_message"])
                self.assertFalse(body["ticket_created"])

    def test_unresolved_request_recommends_human_during_working_hours(self) -> None:
        working_time = datetime(2026, 8, 13, 10, 0, tzinfo=ZoneInfo("America/Lima"))

        with patch("main._now_in_lima", return_value=working_time):
            status, body = self.post(
                "/support-requests",
                {
                    "caller_id": "PE-SUPPLIER-001",
                    "lot_id": "MF-317",
                    "intent": "unknown_request",
                },
            )

        self.assertEqual(status, 200)
        self.assertFalse(body["resolved"])
        self.assertTrue(body["support_open"])
        self.assertEqual(body["next_action"], "human_handoff")
        self.assertTrue(body["human_handoff_recommended"])
        self.assertFalse(body["ticket_recommended"])
        self.assertIn("especialista", body["spoken_message"])

    def test_unresolved_request_recommends_ticket_after_hours(self) -> None:
        after_hours = datetime(2026, 8, 13, 20, 0, tzinfo=ZoneInfo("America/Lima"))

        with patch("main._now_in_lima", return_value=after_hours):
            status, body = self.post(
                "/support-requests",
                {
                    "caller_id": "BR-LOGISTICS-001",
                    "lot_id": "MF-422",
                    "intent": "check_documentation",
                },
            )

        self.assertEqual(status, 200)
        self.assertFalse(body["resolved"])
        self.assertFalse(body["support_open"])
        self.assertEqual(body["next_action"], "open_ticket")
        self.assertTrue(body["ticket_recommended"])
        self.assertFalse(body["ticket_created"])
        self.assertIn("ticket", body["spoken_message"])


if __name__ == "__main__":
    unittest.main()
