"""Configurable fictional API for MaderaFlow wood-drying voice support."""

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException


CONFIG_PATH = Path(__file__).parent / "config" / "maderaflow.json"
SUPPORTED_CALLER_TYPES = {"buyer", "supplier", "transport_partner"}
SUPPORTED_LANGUAGE_CODES = {"en", "es", "pt"}
REQUIRED_CONFIG_SECTIONS = {
    "organization",
    "callers",
    "lots",
    "escalation_triggers",
}


def _load_configuration() -> dict[str, Any]:
    """Load and validate fictional business data when the application starts."""
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

    for config_key, lot in configuration["lots"].items():
        if config_key != lot.get("lot_id", "").lower():
            raise RuntimeError(f"Lot configuration key does not match {config_key}")

    return configuration


CONFIG = _load_configuration()
ORGANIZATION = CONFIG["organization"]
CALLERS = CONFIG["callers"]
LOTS = CONFIG["lots"]
ESCALATION_TRIGGERS = CONFIG["escalation_triggers"]


app = FastAPI(
    title="MaderaFlow Voice Support API",
    description=(
        "A fictional multilingual API for wood-drying status and cross-border "
        "logistics coordination. Every organization, caller, and lot is fictional."
    ),
    version="0.3.0",
)


def _find_caller(caller_id: str) -> dict[str, Any]:
    caller = CALLERS.get(caller_id.lower())
    if caller is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown fictional caller '{caller_id}'.",
        )
    return caller


def _find_lot(lot_id: str) -> dict[str, Any]:
    lot = LOTS.get(lot_id.lower())
    if lot is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown fictional lot '{lot_id}'.",
        )
    return lot


def _buyer_response(lot: dict[str, Any], language: str) -> dict[str, Any]:
    messages = {
        "en": (
            f"Lot {lot['lot_id']} is {lot['drying_status']}. The latest recorded "
            f"moisture is {lot['current_moisture_percentage']} percent, with a "
            f"target of {lot['target_moisture_percentage']} percent. Completion is "
            f"estimated for {lot['estimated_completion_date']}, but this date is not "
            f"guaranteed. Shipment readiness is {lot['transport_readiness']}."
        ),
        "es": (
            f"El lote {lot['lot_id']} está {lot['drying_status']}. La última humedad "
            f"registrada es {lot['current_moisture_percentage']} por ciento, con un "
            f"objetivo de {lot['target_moisture_percentage']} por ciento. La "
            f"finalización se estima para {lot['estimated_completion_date']}, pero la "
            f"fecha no está garantizada. El estado de envío es "
            f"{lot['transport_readiness']}."
        ),
        "pt": (
            f"O lote {lot['lot_id']} está {lot['drying_status']}. A última umidade "
            f"registrada é {lot['current_moisture_percentage']} por cento, com meta de "
            f"{lot['target_moisture_percentage']} por cento. A conclusão está estimada "
            f"para {lot['estimated_completion_date']}, mas a data não é garantida. A "
            f"situação para embarque é {lot['transport_readiness']}."
        ),
    }
    return {
        "drying_status": lot["drying_status"],
        "latest_recorded_moisture_percentage": lot["current_moisture_percentage"],
        "target_moisture_percentage": lot["target_moisture_percentage"],
        "estimated_completion_date": lot["estimated_completion_date"],
        "shipment_readiness": lot["transport_readiness"],
        "spoken_message": messages[language],
    }


def _supplier_response(lot: dict[str, Any], language: str) -> dict[str, Any]:
    action_required = lot["supplier_action_required"]
    action_messages = {
        "en": (
            f"Supplier action is required: {lot['supplier_action']}."
            if action_required
            else "No supplier action is currently required."
        ),
        "es": (
            f"Se requiere acción del proveedor: {lot['supplier_action']}."
            if action_required
            else "Actualmente no se requiere ninguna acción del proveedor."
        ),
        "pt": (
            f"É necessária uma ação do fornecedor: {lot['supplier_action']}."
            if action_required
            else "Nenhuma ação do fornecedor é necessária no momento."
        ),
    }
    messages = {
        "en": (
            f"Lot {lot['lot_id']} has been received. Documentation status is "
            f"{lot['documentation_status']}. {action_messages['en']}"
        ),
        "es": (
            f"El lote {lot['lot_id']} fue recibido. El estado de la documentación es "
            f"{lot['documentation_status']}. {action_messages['es']}"
        ),
        "pt": (
            f"O lote {lot['lot_id']} foi recebido. A situação da documentação é "
            f"{lot['documentation_status']}. {action_messages['pt']}"
        ),
    }
    return {
        "received": lot["received"],
        "documentation_status": lot["documentation_status"],
        "supplier_action_required": action_required,
        "supplier_action": lot["supplier_action"],
        "spoken_message": messages[language],
    }


def _transport_response(lot: dict[str, Any], language: str) -> dict[str, Any]:
    collection_ready = lot["transport_readiness"] == "ready"
    schedule_text = {
        "en": (
            "Transport can be scheduled."
            if collection_ready
            else "Transport cannot be scheduled yet."
        ),
        "es": (
            "Se puede programar el transporte."
            if collection_ready
            else "El transporte todavía no se puede programar."
        ),
        "pt": (
            "O transporte pode ser agendado."
            if collection_ready
            else "O transporte ainda não pode ser agendado."
        ),
    }
    messages = {
        "en": (
            f"Lot {lot['lot_id']} collection readiness is "
            f"{lot['transport_readiness']}. Destination: {lot['destination']}. "
            f"{schedule_text['en']}"
        ),
        "es": (
            f"La preparación para recoger el lote {lot['lot_id']} es "
            f"{lot['transport_readiness']}. Destino: {lot['destination']}. "
            f"{schedule_text['es']}"
        ),
        "pt": (
            f"A situação de coleta do lote {lot['lot_id']} é "
            f"{lot['transport_readiness']}. Destino: {lot['destination']}. "
            f"{schedule_text['pt']}"
        ),
    }
    return {
        "collection_ready": collection_ready,
        "collection_status": lot["transport_readiness"],
        "destination": lot["destination"],
        "transport_can_be_scheduled": collection_ready,
        "spoken_message": messages[language],
    }


def _buyer_escalation_recommended(lot: dict[str, Any]) -> bool:
    delayed = (
        ESCALATION_TRIGGERS["delayed_lot"]
        and lot["drying_status"] == "delayed"
    )
    schedule_risk = (
        ESCALATION_TRIGGERS["not_transport_ready_near_required_date"]
        and lot["near_required_date"]
        and lot["transport_readiness"] != "ready"
    )
    quality_problem = (
        ESCALATION_TRIGGERS["quality_problem_recorded"]
        and lot["quality_problem_recorded"]
    )
    return delayed or schedule_risk or quality_problem


@app.get("/health")
def get_health() -> dict[str, str]:
    """Confirm that the fictional MaderaFlow backend can answer requests."""
    return {"status": "ok"}


@app.get("/organization")
def get_organization() -> dict[str, Any]:
    """Return public information about the fictional organization."""
    return ORGANIZATION


@app.get("/callers/{caller_id}")
def get_caller(caller_id: str) -> dict[str, Any]:
    """Return one fictional caller profile."""
    return _find_caller(caller_id)


@app.get("/lots/{lot_id}")
def get_lot(lot_id: str, caller_id: str) -> dict[str, Any]:
    """Return a fictional lot view tailored to the caller's role and language."""
    caller = _find_caller(caller_id)
    lot = _find_lot(lot_id)
    language = caller["preferred_language"]["code"]

    response_builders = {
        "buyer": _buyer_response,
        "supplier": _supplier_response,
        "transport_partner": _transport_response,
    }
    role_view = response_builders[caller["caller_type"]](lot, language)

    escalation_recommended = False
    if caller["caller_type"] == "buyer" and caller["support_priority"] == "high":
        escalation_recommended = _buyer_escalation_recommended(lot)

    return {
        "fictional": True,
        "lot_id": lot["lot_id"],
        "caller_id": caller["caller_id"],
        "caller_type": caller["caller_type"],
        "language": language,
        "escalation_recommended": escalation_recommended,
        **role_view,
    }
