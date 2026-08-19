"""Environment settings and validated demonstration business records."""

import json
import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "maderaflow.json"
ORDER_INTAKE_CONFIG_PATH = PROJECT_ROOT / "config" / "order_intake.json"
APP_ENV = os.getenv("APP_ENV", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
MADERAFLOW_TOOL_TOKEN = os.getenv("MADERAFLOW_TOOL_TOKEN")
ORDER_INTAKE_ENABLED = os.getenv(
    "ORDER_INTAKE_ENABLED",
    "false",
).casefold() == "true"
ORDER_DATABASE_PATH = Path(
    os.getenv(
        "ORDER_DATABASE_PATH",
        str(PROJECT_ROOT / ".data" / "order_requests.sqlite3"),
    )
)
ORDER_REVIEWER_NAME = os.getenv("ORDER_REVIEWER_NAME", "responsible manager")
ORDER_NOTIFICATION_WHATSAPP = os.getenv("ORDER_NOTIFICATION_WHATSAPP")
PERU_INBOUND_NUMBER = os.getenv("PERU_INBOUND_NUMBER")
GERMANY_INBOUND_NUMBER = os.getenv("GERMANY_INBOUND_NUMBER")

SUPPORTED_CALLER_TYPES = {"buyer", "supplier", "transport_partner"}
SUPPORTED_LANGUAGE_CODES = {"en", "es", "pt"}
REQUIRED_CONFIG_SECTIONS = {
    "organization",
    "voice_agent",
    "callers",
    "wood_types",
    "drying_statuses",
    "lots",
    "transports",
    "escalation_triggers",
    "support_hours",
}


def load_configuration() -> dict[str, Any]:
    """Load sample records and reject invalid relationships at startup."""
    try:
        with CONFIG_PATH.open(encoding="utf-8") as config_file:
            configuration = json.load(config_file)
    except FileNotFoundError as error:
        raise RuntimeError(f"Configuration file not found: {CONFIG_PATH}") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Configuration contains invalid JSON: {error}") from error

    missing_sections = REQUIRED_CONFIG_SECTIONS - configuration.keys()
    if missing_sections:
        missing = ", ".join(sorted(missing_sections))
        raise RuntimeError(f"Configuration is missing required sections: {missing}")

    organization = configuration["organization"]
    configured_languages = set(organization.get("supported_languages", {}))
    if configured_languages != SUPPORTED_LANGUAGE_CODES:
        raise RuntimeError("Configured languages must be exactly: en, es, pt")

    for config_key, caller in configuration["callers"].items():
        if config_key != caller.get("caller_id", "").lower():
            raise RuntimeError(f"Caller configuration key does not match {config_key}")
        if caller.get("caller_type") not in SUPPORTED_CALLER_TYPES:
            raise RuntimeError(f"Caller {config_key} has an unsupported caller type")
        language = caller.get("preferred_language", {}).get("code")
        if language not in SUPPORTED_LANGUAGE_CODES:
            raise RuntimeError(f"Caller {config_key} has an unsupported language")

    caller_ids = {
        caller["caller_id"]: caller for caller in configuration["callers"].values()
    }
    wood_types_by_id = {
        wood_type["wood_type_id"]: wood_type
        for wood_type in configuration["wood_types"].values()
    }
    drying_statuses_by_id = {
        status["drying_status_id"]: status
        for status in configuration["drying_statuses"].values()
    }

    lot_ids: set[str] = set()
    for config_key, lot in configuration["lots"].items():
        if config_key != lot.get("lot_id", "").lower():
            raise RuntimeError(f"Lot configuration key does not match {config_key}")

        lot_ids.add(lot["lot_id"])
        buyer = caller_ids.get(lot.get("buyer_id"))
        provider = caller_ids.get(lot.get("provider_id"))
        if buyer is None or buyer["caller_type"] != "buyer":
            raise RuntimeError(f"Lot {config_key} references an invalid buyer")
        if provider is None or provider["caller_type"] != "supplier":
            raise RuntimeError(f"Lot {config_key} references an invalid provider")

        wood_type = wood_types_by_id.get(lot.get("wood_type_id"))
        if wood_type is None:
            raise RuntimeError(f"Lot {config_key} references an invalid wood type")
        drying_status = drying_statuses_by_id.get(lot.get("drying_status_id"))
        if drying_status is None:
            raise RuntimeError(f"Lot {config_key} references an invalid drying status")

        # Readable values are derived from referenced records. IDs remain the
        # source of truth in the configuration file.
        lot["species"] = wood_type["name"]
        lot["drying_status"] = drying_status["code"]

    for config_key, transport in configuration["transports"].items():
        if config_key != transport.get("transport_id", "").lower():
            raise RuntimeError(
                f"Transport configuration key does not match {config_key}"
            )
        if transport.get("lot_id") not in lot_ids:
            raise RuntimeError(f"Transport {config_key} references an invalid lot")
        transporter = caller_ids.get(transport.get("transporter_id"))
        if transporter is None or transporter["caller_type"] != "transport_partner":
            raise RuntimeError(
                f"Transport {config_key} references an invalid transporter"
            )

    return configuration


def load_order_intake_configuration() -> dict[str, Any]:
    """Load public order-intake rules without secrets or personal contacts."""
    try:
        with ORDER_INTAKE_CONFIG_PATH.open(encoding="utf-8") as config_file:
            configuration = json.load(config_file)
    except FileNotFoundError as error:
        raise RuntimeError(
            f"Order-intake configuration file not found: {ORDER_INTAKE_CONFIG_PATH}"
        ) from error
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Order-intake configuration contains invalid JSON: {error}"
        ) from error

    required_sections = {
        "organization",
        "supported_languages",
        "working_hours",
        "order_rules",
        "escalation_rules",
    }
    missing_sections = required_sections - configuration.keys()
    if missing_sections:
        missing = ", ".join(sorted(missing_sections))
        raise RuntimeError(
            f"Order-intake configuration is missing required sections: {missing}"
        )

    if set(configuration["supported_languages"]) != {"es", "de", "en"}:
        raise RuntimeError("Order-intake languages must be exactly: de, en, es")

    intervals = configuration["working_hours"].get("intervals", [])
    if not intervals:
        raise RuntimeError("Order-intake working hours need at least one interval")
    for interval in intervals:
        if set(interval) != {"opens_at", "closes_at"}:
            raise RuntimeError("Every working-hours interval needs opens_at and closes_at")

    return configuration


CONFIG = load_configuration()
ORGANIZATION = CONFIG["organization"]
VOICE_AGENT = CONFIG["voice_agent"]
CALLERS = CONFIG["callers"]
WOOD_TYPES = CONFIG["wood_types"]
DRYING_STATUSES = CONFIG["drying_statuses"]
LOTS = CONFIG["lots"]
TRANSPORTS = CONFIG["transports"]
ESCALATION_TRIGGERS = CONFIG["escalation_triggers"]
SUPPORT_HOURS = CONFIG["support_hours"]
ORDER_INTAKE_CONFIG = load_order_intake_configuration()
