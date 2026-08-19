"""Tests for the Spanish/German after-hours order-intake milestone."""

import asyncio
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import urlsplit

os.environ.setdefault("MADERAFLOW_TOOL_TOKEN", "test-only-token")

from main import app
from maderaflow.models import OrderIntakeRequest
from maderaflow.order_intake import escalation_reasons, intake_preview
from maderaflow.order_storage import SQLiteOrderRepository


async def request(
    url: str,
    method: str = "GET",
    json_body: dict[str, Any] | None = None,
    authenticated: bool = False,
) -> tuple[int, dict[str, Any]]:
    """Send an HTTP request directly through the ASGI application."""
    parsed_url = urlsplit(url)
    encoded_body = json.dumps(json_body).encode("utf-8") if json_body else b""
    response_messages: list[dict] = []
    request_sent = False

    async def receive() -> dict:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": encoded_body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        response_messages.append(message)

    headers = []
    if json_body is not None:
        headers.append((b"content-type", b"application/json"))
    if authenticated:
        headers.append((b"authorization", b"Bearer test-only-token"))

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": parsed_url.path,
            "raw_path": parsed_url.path.encode("ascii"),
            "query_string": parsed_url.query.encode("ascii"),
            "root_path": "",
            "headers": headers,
            "client": ("test-client", 1234),
            "server": ("test-server", 80),
        },
        receive,
        send,
    )
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


def complete_order(country: str, language: str, conversation_id: str) -> dict[str, Any]:
    """Return a complete safe test request with no real customer information."""
    body: dict[str, Any] = {
        "conversation_id": conversation_id,
        "called_number": "+51 000 000 000" if country == "PE" else "+49 000 000000",
        "caller_number": "+00 000 000000",
        "country": country,
        "language": language,
        "transcription_consent": True,
        "contact_authorized": True,
        "customer_confirmed": True,
        "call_reason": "new_quote",
        "customer_name": "Test Customer",
        "company": "Example Company",
        "customer_country": "Peru" if country == "PE" else "Germany",
        "customer_city": "Example City",
        "phone": "+00 000 000000",
        "preferred_contact_method": "phone",
        "best_contact_time": "Tomorrow morning",
        "service_needed": "drying",
        "customer_has_wood": True,
        "current_wood_location": "Example warehouse",
        "supplier_coordination_needed": False,
        "species_common_name": "Tornillo",
        "species_scientific_name": "Cedrelinga cateniformis",
        "presentation": "boards",
        "dimensions": "2 x 10 x 200",
        "dimension_unit": "centimetres",
        "piece_count": 120,
        "approximate_volume_m3": 25.0,
        "initial_moisture_percentage": 28,
        "target_moisture_percentage": 11,
        "final_use": "interior manufacturing",
        "moisture_certificate_requested": True,
        "required_date": "2026-10-20",
        "quality_requirements": "No visible defects",
        "photos_or_documents_available": True,
        "required_certifications_or_documents": "To be reviewed",
        "destination_city_country": "Example destination",
    }
    if country == "PE":
        body.update(
            {
                "estimated_plant_arrival_date": "2026-09-10",
                "inbound_transport_responsible": "Customer",
                "outbound_collection_responsible": "Customer",
                "peru_order_scope": "full_lot",
            }
        )
    else:
        body.update(
            {
                "preferred_destination_port": "Hamburg",
                "order_frequency": "one-time order",
                "required_shipping_date": "2026-10-01",
                "incoterm_preference": "FOB",
                "has_importer_customs_agent_or_transporter": True,
                "importer_customs_agent_or_transporter_details": "Details pending",
                "sample_requested": True,
                "preferred_quote_currency": "EUR",
            }
        )
    return body


class OrderIntakeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "orders.sqlite3"
        self.repository = SQLiteOrderRepository(database_path)
        self.repository_patch = patch("maderaflow.api.ORDER_REPOSITORY", self.repository)
        self.repository_patch.start()
        self.enabled_patch = patch("maderaflow.api.ORDER_INTAKE_ENABLED", True)
        self.enabled_patch.start()
        self.now_patch = patch(
            "maderaflow.api.utc_now",
            return_value=datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc),
        )
        self.now_patch.start()

    def tearDown(self) -> None:
        self.now_patch.stop()
        self.enabled_patch.stop()
        self.repository_patch.stop()
        self.temporary_directory.cleanup()

    def get(self, url: str) -> tuple[int, dict[str, Any]]:
        return asyncio.run(request(url))

    def post(
        self,
        url: str,
        body: dict[str, Any],
        authenticated: bool = True,
    ) -> tuple[int, dict[str, Any]]:
        return asyncio.run(
            request(url, method="POST", json_body=body, authenticated=authenticated)
        )

    def test_public_config_has_business_rules_but_no_private_contact(self) -> None:
        status, body = self.get("/order-intake-config")
        serialized = json.dumps(body).casefold()

        self.assertEqual(status, 200)
        self.assertEqual(body["organization"]["name"], "Maderera Las Garzas")
        self.assertEqual(set(body["supported_languages"]), {"es", "de", "en"})
        self.assertNotIn("personal_whatsapp", serialized)
        self.assertNotIn("tax_number", serialized)
        self.assertNotIn("api_key", serialized)

    def test_country_and_opening_language_are_inferred_from_phone_prefix(self) -> None:
        peru = intake_preview(
            OrderIntakeRequest(
                conversation_id="country-pe",
                called_number="+51 000 000 000",
            )
        )
        germany = intake_preview(
            OrderIntakeRequest(
                conversation_id="country-de",
                caller_number="+49 000 000000",
            )
        )

        self.assertEqual((peru["country"], peru["language"]), ("PE", "es"))
        self.assertEqual((germany["country"], germany["language"]), ("DE", "de"))
        self.assertEqual(peru["next_field"], "transcription_consent")
        self.assertIn("Autoriza", peru["next_question"])
        self.assertIn("Stimmen Sie", germany["next_question"])

    def test_pre_call_webhook_selects_first_message_before_audio_connects(self) -> None:
        peru_status, peru = self.post(
            "/elevenlabs/pre-call",
            {
                "caller_id": "+00 000 000000",
                "called_number": "+51 000 000 000",
                "call_sid": "call-pe",
            },
        )
        german_status, german = self.post(
            "/elevenlabs/pre-call",
            {
                "caller_id": "+00 000 000000",
                "called_number": "+49 000 000000",
                "call_sid": "call-de",
            },
        )

        self.assertEqual((peru_status, german_status), (200, 200))
        self.assertEqual(
            peru["conversation_config_override"]["agent"]["language"],
            "es",
        )
        self.assertEqual(
            german["conversation_config_override"]["agent"]["language"],
            "de",
        )
        self.assertIn(
            "Maderera Las Garzas",
            german["conversation_config_override"]["agent"]["first_message"],
        )

    def test_preview_is_protected(self) -> None:
        status, body = self.post(
            "/order-intake/preview",
            {"conversation_id": "unauthorized"},
            authenticated=False,
        )

        self.assertEqual(status, 401)
        self.assertIn("valid bearer token", body["detail"])

    def test_declined_contact_ends_without_storing_request(self) -> None:
        status, body = self.post(
            "/order-requests",
            {
                "conversation_id": "no-contact",
                "country": "PE",
                "language": "es",
                "transcription_consent": False,
                "contact_authorized": False,
            },
        )

        self.assertEqual(status, 200)
        self.assertFalse(body["saved"])
        self.assertEqual(body["next_action"], "end_without_storing_customer_request")
        self.assertIsNone(self.repository.find_by_conversation_id("no-contact"))

    def test_declined_transcription_can_create_callback_without_transcript(self) -> None:
        status, body = self.post(
            "/order-requests",
            {
                "conversation_id": "callback-only",
                "caller_number": "+51 000 000 000",
                "transcription_consent": False,
                "contact_authorized": True,
                "customer_confirmed": True,
                "phone": "+00 000 000000",
                "preferred_contact_method": "phone",
            },
        )

        stored = self.repository.find_by_conversation_id("callback-only")
        self.assertEqual(status, 200)
        self.assertTrue(body["saved"])
        self.assertEqual(body["status"], "DEVOLUCION_DE_LLAMADA")
        self.assertTrue(body["request_id"].startswith("MLG-PE-20260819-"))
        self.assertIsNotNone(stored)
        self.assertNotIn("transcript", json.loads(stored["payload_json"]))

    def test_spanish_order_is_saved_with_honest_pending_notification(self) -> None:
        status, body = self.post(
            "/order-requests",
            complete_order("PE", "es", "spanish-order"),
        )

        self.assertEqual(status, 200)
        self.assertTrue(body["saved"])
        self.assertFalse(body["processed"])
        self.assertTrue(body["request_id"].startswith("MLG-PE-20260819-"))
        self.assertIn("Hemos guardado", body["spoken_message"])
        self.assertIn("PENDING", body["whatsapp_delivery_status"])
        self.assertTrue(body["alert_visible"])

    def test_german_order_is_saved_and_confirmed_in_german(self) -> None:
        status, body = self.post(
            "/order-requests",
            complete_order("DE", "de", "german-order"),
        )

        self.assertEqual(status, 200)
        self.assertEqual(body["country"], "DE")
        self.assertEqual(body["language"], "de")
        self.assertTrue(body["request_id"].startswith("MLG-DE-20260819-"))
        self.assertIn("Ihre Anfrage wurde", body["spoken_message"])

    def test_repeated_webhook_call_does_not_duplicate_request(self) -> None:
        payload = complete_order("DE", "de", "same-conversation")
        _, first = self.post("/order-requests", payload)
        _, second = self.post("/order-requests", payload)

        self.assertEqual(first["request_id"], second["request_id"])
        self.assertTrue(first["request_created"])
        self.assertFalse(second["request_created"])

    def test_missing_data_returns_one_next_question(self) -> None:
        payload = complete_order("DE", "de", "missing-port")
        payload.pop("preferred_destination_port")
        payload["customer_confirmed"] = False

        status, body = self.post("/order-requests", payload)

        self.assertEqual(status, 200)
        self.assertFalse(body["saved"])
        self.assertEqual(body["next_action"], "ask_next_question")
        self.assertEqual(body["next_field"], "preferred_destination_port")
        self.assertIn("Zielhafen", body["spoken_message"])

    def test_business_rules_recommend_human_escalation(self) -> None:
        request_model = OrderIntakeRequest.model_validate(
            {
                **complete_order("DE", "de", "escalation"),
                "species_common_name": "Unknown sample species",
                "target_moisture_percentage": 7,
                "approximate_volume_m3": 400,
                "required_date": "2026-08-25",
            }
        )
        reasons = escalation_reasons(
            request_model,
            now_lima=datetime(2026, 8, 19, 8, 0),
        )

        self.assertIn("unknown_species", reasons)
        self.assertIn("target_moisture_outside_usual_range", reasons)
        self.assertIn("volume_above_installed_capacity", reasons)
        self.assertIn("required_in_less_than_20_days", reasons)


if __name__ == "__main__":
    unittest.main()
