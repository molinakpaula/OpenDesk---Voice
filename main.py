"""Configurable API for the MaderaFlow wood-drying voice-support demo."""

import json
import logging
import os
import secrets
import unicodedata
from datetime import datetime, time
from pathlib import Path
from time import perf_counter
from typing import Any, Literal
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel


CONFIG_PATH = Path(__file__).parent / "config" / "maderaflow.json"
APP_ENV = os.getenv("APP_ENV", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
MADERAFLOW_TOOL_TOKEN = os.getenv("MADERAFLOW_TOOL_TOKEN")
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
REQUEST_LOGGER = logging.getLogger("maderaflow.requests")
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


def _load_configuration() -> dict[str, Any]:
    """Load and validate demonstration business data at application startup."""
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
        drying_status["drying_status_id"]: drying_status
        for drying_status in configuration["drying_statuses"].values()
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

        # These readable values are derived from their referenced records. The
        # IDs remain the source of truth in the configuration file.
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


CONFIG = _load_configuration()
ORGANIZATION = CONFIG["organization"]
VOICE_AGENT = CONFIG["voice_agent"]
CALLERS = CONFIG["callers"]
WOOD_TYPES = CONFIG["wood_types"]
DRYING_STATUSES = CONFIG["drying_statuses"]
LOTS = CONFIG["lots"]
TRANSPORTS = CONFIG["transports"]
ESCALATION_TRIGGERS = CONFIG["escalation_triggers"]
SUPPORT_HOURS = CONFIG["support_hours"]


def _voice_identifier_key(value: str) -> str:
    """Fold one spoken or typed identifier into a comparison-only key.

    Speech-to-text tools commonly remove hyphens, insert spaces, or omit accent
    marks. This key removes those presentation differences without changing the
    canonical identifier stored in the demonstration data.
    """
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character
        for character in decomposed
        if character.isalnum() and not unicodedata.combining(character)
    )


def _build_voice_aliases(
    alias_groups: dict[str, set[str]],
    configured_records: dict[str, dict[str, Any]],
    id_field: str,
) -> dict[str, str]:
    """Build a collision-checked alias index for configured demonstration IDs."""
    alias_index: dict[str, str] = {}
    for canonical_key, aliases in alias_groups.items():
        if canonical_key not in configured_records:
            raise RuntimeError(f"Voice alias references unknown ID: {canonical_key}")

        canonical_id = configured_records[canonical_key][id_field]
        for alias in aliases | {canonical_id}:
            alias_key = _voice_identifier_key(alias)
            existing_key = alias_index.get(alias_key)
            if existing_key is not None and existing_key != canonical_key:
                raise RuntimeError(f"Voice alias is ambiguous: {alias}")
            alias_index[alias_key] = canonical_key
    return alias_index


CALLER_VOICE_ALIASES = _build_voice_aliases(
    {
        "us-buyer-001": {
            "US buyer 1",
            "US buyer one",
            "United States buyer 1",
            "United States buyer one",
            "buyer 1",
            "buyer one",
            "comprador Estados Unidos 1",
            "comprador Estados Unidos uno",
            "comprador 1",
            "comprador uno",
        },
        "pe-supplier-001": {
            "PE supplier 1",
            "PE supplier one",
            "Peru supplier 1",
            "Peru supplier one",
            "supplier 1",
            "supplier one",
            "proveedor Peru 1",
            "proveedor Peru uno",
            "proveedor Peru cero cero uno",
            "proveedor 1",
            "proveedor uno",
            "fornecedor Peru 1",
            "fornecedor Peru um",
        },
        "br-logistics-001": {
            "BR logistics 1",
            "BR logistics one",
            "Brazil logistics 1",
            "Brazil logistics one",
            "logistics 1",
            "logistics one",
            "Brazil transport partner 1",
            "Brazil transport partner one",
            "logistica Brasil 1",
            "logistica Brasil um",
            "parceiro de transporte Brasil 1",
            "parceiro de transporte Brasil um",
        },
    },
    CALLERS,
    "caller_id",
)

LOT_VOICE_ALIASES = _build_voice_aliases(
    {
        "mf-204": {
            "204",
            "lot 204",
            "lot two zero four",
            "lot two hundred four",
            "M F two zero four",
            "em eff two zero four",
            "lote 204",
            "lote dos cero cuatro",
            "lote doscientos cuatro",
            "eme efe dos cero cuatro",
            "lote dois zero quatro",
            "lote duzentos e quatro",
            "eme efe dois zero quatro",
        },
        "mf-317": {
            "317",
            "lot 317",
            "lot three one seven",
            "lot three hundred seventeen",
            "M F three one seven",
            "em eff three one seven",
            "lote 317",
            "lote tres uno siete",
            "lote trescientos diecisiete",
            "eme efe tres uno siete",
            "lote tres um sete",
            "lote trezentos e dezessete",
            "eme efe tres um sete",
        },
        "mf-422": {
            "422",
            "lot 422",
            "lot four two two",
            "lot four hundred twenty two",
            "M F four two two",
            "em eff four two two",
            "lote 422",
            "lote cuatro dos dos",
            "lote cuatrocientos veintidos",
            "eme efe cuatro dos dos",
            "lote quatro dois dois",
            "lote quatrocentos e vinte e dois",
            "eme efe quatro dois dois",
        },
    },
    LOTS,
    "lot_id",
)


class SupportRequest(BaseModel):
    """Context supplied by the voice layer, beginning with a caller ID."""

    caller_id: str
    lot_id: str | None = None
    intent: str | None = None
    language: Literal["en", "es", "pt"] | None = None


LABELS = {
    "drying_on_schedule": {
        "en": "drying on schedule",
        "es": "secándose según lo programado",
        "pt": "secando conforme o cronograma",
    },
    "delayed": {"en": "delayed", "es": "retrasado", "pt": "atrasado"},
    "quality_hold": {
        "en": "on quality hold",
        "es": "retenido por control de calidad",
        "pt": "retido para controle de qualidade",
    },
    "not_ready": {
        "en": "not ready",
        "es": "no listo",
        "pt": "não pronto",
    },
    "ready": {"en": "ready", "es": "listo", "pt": "pronto"},
    "complete": {"en": "complete", "es": "completa", "pt": "completa"},
    "supplier_documents_pending": {
        "en": "supplier documents pending",
        "es": "documentos del proveedor pendientes",
        "pt": "documentos do fornecedor pendentes",
    },
    "submit_missing_origin_document": {
        "en": "submit the missing origin document",
        "es": "presentar el documento de origen pendiente",
        "pt": "enviar o documento de origem pendente",
    },
    "none": {"en": "none", "es": "ninguna", "pt": "nenhuma"},
}

OPENING_MESSAGES = {
    "en": "Hello, you have reached MaderaFlow Support, an automated voice assistant. Please tell me your caller ID so I can find your assigned wood lots.",
    "es": "Hola, ha contactado con MaderaFlow Support, un asistente de voz automatizado. Indíqueme su ID de llamada para encontrar sus lotes de madera asignados.",
    "pt": "Olá, você entrou em contato com a MaderaFlow Support, uma assistente de voz automatizada. Informe seu ID de chamada para eu localizar seus lotes de madeira atribuídos.",
}

SUPPORTED_INTENTS = {
    "check_lot_status": "buyer",
    "check_documentation": "supplier",
    "check_transport_readiness": "transport_partner",
}

SAFETY_BOUNDARIES = [
    "Use only fixed demonstration records returned by the API.",
    "Never invent or describe a measurement as live.",
    "Never guarantee an estimated completion date.",
    "Do not give legal or customs advice.",
    "Do not admit liability.",
    "Return only information relevant to the caller's role.",
]


def _label(value: str, language: str) -> str:
    """Translate an internal operational code for speech without changing it."""
    return LABELS.get(value, {}).get(language, value.replace("_", " "))


app = FastAPI(
    title="MaderaFlow Voice Support API",
    description=(
        "A multilingual demonstration API for wood-drying status and cross-border "
        "logistics coordination. It contains sample records and no real customer data."
    ),
    version="0.6.0",
)


@app.middleware("http")
async def log_request_metadata(request: Request, call_next):
    """Log safe request metadata without IDs, query strings, or request bodies."""
    started_at = perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    route_template = getattr(route, "path", "unmatched_route")
    duration_ms = round((perf_counter() - started_at) * 1000, 2)
    REQUEST_LOGGER.info(
        "method=%s route=%s status=%s duration_ms=%s environment=%s",
        request.method,
        route_template,
        response.status_code,
        duration_ms,
        APP_ENV,
    )
    return response


def _find_caller(caller_id: str) -> dict[str, Any]:
    caller_key = CALLER_VOICE_ALIASES.get(_voice_identifier_key(caller_id))
    caller = CALLERS.get(caller_key) if caller_key else None
    if caller is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown caller '{caller_id}'.",
        )
    return caller


def _find_lot(lot_id: str) -> dict[str, Any]:
    lot_key = LOT_VOICE_ALIASES.get(_voice_identifier_key(lot_id))
    lot = LOTS.get(lot_key) if lot_key else None
    if lot is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown lot '{lot_id}'.",
        )
    return lot


def _transports_for_lot(
    lot_id: str,
    transporter_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return ordered transport movements for one lot and optional transporter."""
    movements = [
        transport
        for transport in TRANSPORTS.values()
        if transport["lot_id"] == lot_id
        and (
            transporter_id is None
            or transport["transporter_id"] == transporter_id
        )
    ]
    return sorted(movements, key=lambda movement: movement["sequence"])


def _lots_for_caller(caller: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve the wood lots assigned to a buyer, provider, or transporter."""
    caller_id = caller["caller_id"]
    caller_type = caller["caller_type"]

    if caller_type == "buyer":
        assigned_lot_ids = {
            lot["lot_id"] for lot in LOTS.values() if lot["buyer_id"] == caller_id
        }
    elif caller_type == "supplier":
        assigned_lot_ids = {
            lot["lot_id"] for lot in LOTS.values() if lot["provider_id"] == caller_id
        }
    else:
        assigned_lot_ids = {
            transport["lot_id"]
            for transport in TRANSPORTS.values()
            if transport["transporter_id"] == caller_id
        }

    return sorted(
        (lot for lot in LOTS.values() if lot["lot_id"] in assigned_lot_ids),
        key=lambda lot: lot["lot_id"],
    )


def _require_lot_assignment(
    caller: dict[str, Any],
    lot: dict[str, Any],
) -> None:
    """Prevent a caller from retrieving a lot outside their assignments."""
    assigned_ids = {assigned_lot["lot_id"] for assigned_lot in _lots_for_caller(caller)}
    if lot["lot_id"] not in assigned_ids:
        raise HTTPException(
            status_code=404,
            detail="The requested lot is not assigned to this caller.",
        )


def _lot_selection_response(
    caller: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    """Ask the caller to select a lot when their ID maps to several lots."""
    available_lots = [lot["lot_id"] for lot in _lots_for_caller(caller)]
    spoken_numbers = ", ".join(lot_id.removeprefix("MF-") for lot_id in available_lots)
    messages = {
        "en": (
            f"I found {len(available_lots)} wood lots assigned to your profile: "
            f"{spoken_numbers}. Which three-digit lot number do you need?"
        ),
        "es": (
            f"Encontré {len(available_lots)} lotes de madera asignados a su perfil: "
            f"{spoken_numbers}. ¿Qué número de lote de tres dígitos necesita?"
        ),
        "pt": (
            f"Encontrei {len(available_lots)} lotes de madeira atribuídos ao seu perfil: "
            f"{spoken_numbers}. Qual número de lote de três dígitos você precisa?"
        ),
    }
    return {
        "demonstration_data": True,
        "caller_id": caller["caller_id"],
        "caller_type": caller["caller_type"],
        "language": language,
        "resolved": False,
        "reason": "lot_selection_required",
        "next_action": "ask_for_lot",
        "available_lots": available_lots,
        "spoken_message": messages[language],
    }


def _buyer_response(lot: dict[str, Any], language: str) -> dict[str, Any]:
    drying_status = _label(lot["drying_status"], language)
    transport_readiness = _label(lot["transport_readiness"], language)
    messages = {
        "en": (
            f"Lot {lot['lot_id']} is {drying_status}. The latest recorded "
            f"moisture is {lot['current_moisture_percentage']} percent, with a "
            f"target of {lot['target_moisture_percentage']} percent. Completion is "
            f"estimated for {lot['estimated_completion_date']}, but this date is not "
            f"guaranteed. Shipment readiness is {transport_readiness}."
        ),
        "es": (
            f"El lote {lot['lot_id']} está {drying_status}. La última humedad "
            f"registrada es {lot['current_moisture_percentage']} por ciento, con un "
            f"objetivo de {lot['target_moisture_percentage']} por ciento. La "
            f"finalización se estima para {lot['estimated_completion_date']}, pero la "
            f"fecha no está garantizada. El estado de envío es "
            f"{transport_readiness}."
        ),
        "pt": (
            f"O lote {lot['lot_id']} está {drying_status}. A última umidade "
            f"registrada é {lot['current_moisture_percentage']} por cento, com meta de "
            f"{lot['target_moisture_percentage']} por cento. A conclusão está estimada "
            f"para {lot['estimated_completion_date']}, mas a data não é garantida. A "
            f"situação para embarque é {transport_readiness}."
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
    documentation_status = _label(lot["documentation_status"], language)
    supplier_action = _label(lot["supplier_action"], language)
    action_messages = {
        "en": (
            f"Supplier action is required: {supplier_action}."
            if action_required
            else "No supplier action is currently required."
        ),
        "es": (
            f"Se requiere acción del proveedor: {supplier_action}."
            if action_required
            else "Actualmente no se requiere ninguna acción del proveedor."
        ),
        "pt": (
            f"É necessária uma ação do fornecedor: {supplier_action}."
            if action_required
            else "Nenhuma ação do fornecedor é necessária no momento."
        ),
    }
    messages = {
        "en": (
            f"Lot {lot['lot_id']} has been received. Documentation status is "
            f"{documentation_status}. {action_messages['en']}"
        ),
        "es": (
            f"El lote {lot['lot_id']} fue recibido. El estado de la documentación es "
            f"{documentation_status}. {action_messages['es']}"
        ),
        "pt": (
            f"O lote {lot['lot_id']} foi recebido. A situação da documentação é "
            f"{documentation_status}. {action_messages['pt']}"
        ),
    }
    return {
        "received": lot["received"],
        "documentation_status": lot["documentation_status"],
        "supplier_action_required": action_required,
        "supplier_action": lot["supplier_action"],
        "spoken_message": messages[language],
    }


def _transport_response(
    lot: dict[str, Any],
    language: str,
    caller: dict[str, Any],
) -> dict[str, Any]:
    movements = _transports_for_lot(lot["lot_id"], caller["caller_id"])
    current_movement = next(
        (movement for movement in movements if movement["status"] != "completed"),
        movements[-1],
    )
    collection_ready = lot["transport_readiness"] == "ready"
    collection_status = _label(lot["transport_readiness"], language)
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
            f"{collection_status}. Destination: {current_movement['destination']}. "
            f"{schedule_text['en']}"
        ),
        "es": (
            f"La preparación para recoger el lote {lot['lot_id']} es "
            f"{collection_status}. Destino: {current_movement['destination']}. "
            f"{schedule_text['es']}"
        ),
        "pt": (
            f"A situação de coleta do lote {lot['lot_id']} é "
            f"{collection_status}. Destino: {current_movement['destination']}. "
            f"{schedule_text['pt']}"
        ),
    }
    return {
        "collection_ready": collection_ready,
        "collection_status": lot["transport_readiness"],
        "transport_id": current_movement["transport_id"],
        "movement_sequence": current_movement["sequence"],
        "origin": current_movement["origin"],
        "destination": current_movement["destination"],
        "transport_can_be_scheduled": collection_ready,
        "spoken_message": messages[language],
    }


def _role_response(
    caller: dict[str, Any],
    lot: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    """Build the allow-listed lot view for the caller's assigned role."""
    if caller["caller_type"] == "buyer":
        return _buyer_response(lot, language)
    if caller["caller_type"] == "supplier":
        return _supplier_response(lot, language)
    return _transport_response(lot, language, caller)


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


def _now_in_lima() -> datetime:
    """Return the current time in the configured support timezone."""
    return datetime.now(ZoneInfo(SUPPORT_HOURS["timezone"]))


def _support_is_open(now: datetime | None = None) -> bool:
    """Check demonstration weekday support hours; holidays are not modeled yet."""
    current = now or _now_in_lima()
    opens_at = time.fromisoformat(SUPPORT_HOURS["opens_at"])
    closes_at = time.fromisoformat(SUPPORT_HOURS["closes_at"])
    return (
        current.weekday() in SUPPORT_HOURS["working_days"]
        and opens_at <= current.time().replace(tzinfo=None) < closes_at
    )


def _fallback_response(language: str, reason: str) -> dict[str, Any]:
    support_open = _support_is_open()
    route = "human_handoff" if support_open else "open_ticket"
    messages = {
        "en": {
            "human_handoff": "I cannot safely complete this request. I recommend transferring you to a MaderaFlow support specialist.",
            "open_ticket": "MaderaFlow support is currently closed. I recommend opening a support ticket for follow-up during working hours.",
        },
        "es": {
            "human_handoff": "No puedo completar esta solicitud de forma segura. Recomiendo transferirle a un especialista de soporte de MaderaFlow.",
            "open_ticket": "El soporte de MaderaFlow está cerrado en este momento. Recomiendo abrir un ticket para seguimiento durante el horario laboral.",
        },
        "pt": {
            "human_handoff": "Não posso concluir esta solicitação com segurança. Recomendo transferir você para um especialista de suporte da MaderaFlow.",
            "open_ticket": "O suporte da MaderaFlow está fechado no momento. Recomendo abrir um ticket para acompanhamento durante o horário comercial.",
        },
    }
    return {
        "resolved": False,
        "reason": reason,
        "support_open": support_open,
        "next_action": route,
        "human_handoff_recommended": support_open,
        "ticket_recommended": not support_open,
        "ticket_created": False,
        "spoken_message": messages[language][route],
    }


def _require_tool_token(authorization: str | None = Header(default=None)) -> None:
    """Require the shared bearer token without logging or returning its value."""
    if not MADERAFLOW_TOOL_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="The support tool is not configured on this server.",
        )

    scheme, separator, provided_token = (authorization or "").partition(" ")
    valid_scheme = separator == " " and scheme.lower() == "bearer"
    valid_token = valid_scheme and secrets.compare_digest(
        provided_token,
        MADERAFLOW_TOOL_TOKEN,
    )
    if not valid_token:
        raise HTTPException(
            status_code=401,
            detail="A valid bearer token is required for this support tool.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _support_request_response(request: SupportRequest) -> dict[str, Any]:
    caller = _find_caller(request.caller_id)
    language = request.language or caller["preferred_language"]["code"]
    allowed_intent_by_role = {role: intent for intent, role in SUPPORTED_INTENTS.items()}
    supported_intents = set(SUPPORTED_INTENTS)
    assigned_lots = _lots_for_caller(caller)
    provided_lot_id = request.lot_id.strip() if request.lot_id else None
    provided_intent = request.intent.strip() if request.intent else None

    if provided_lot_id is None:
        if len(assigned_lots) != 1:
            return _lot_selection_response(caller, language)
        lot = assigned_lots[0]
    else:
        lot = _find_lot(provided_lot_id)
        _require_lot_assignment(caller, lot)

    inferred_intent = allowed_intent_by_role[caller["caller_type"]]
    intent = provided_intent or inferred_intent

    if intent not in supported_intents:
        fallback = _fallback_response(language, "unsupported_intent")
        return {
            "demonstration_data": True,
            "caller_id": caller["caller_id"],
            "lot_id": lot["lot_id"],
            "intent": intent,
            "language": language,
            **fallback,
        }

    if intent != inferred_intent:
        fallback = _fallback_response(language, "intent_not_available_for_caller_role")
        return {
            "demonstration_data": True,
            "caller_id": caller["caller_id"],
            "lot_id": lot["lot_id"],
            "intent": intent,
            "language": language,
            **fallback,
        }

    role_view = _role_response(caller, lot, language)
    escalation = (
        caller["caller_type"] == "buyer"
        and caller["support_priority"] == "high"
        and _buyer_escalation_recommended(lot)
    )
    return {
        "demonstration_data": True,
        "caller_id": caller["caller_id"],
        "lot_id": lot["lot_id"],
        "intent": intent,
        "intent_inferred": provided_intent is None,
        "language": language,
        "resolved": True,
        "escalation_recommended": escalation,
        "human_handoff_recommended": escalation,
        "ticket_recommended": False,
        "ticket_created": False,
        **role_view,
    }


@app.get("/health")
def get_health() -> dict[str, str]:
    """Confirm that the MaderaFlow demonstration backend can answer requests."""
    return {"status": "ok"}


@app.get("/organization")
def get_organization() -> dict[str, Any]:
    """Return public information about the demonstration organization."""
    return ORGANIZATION


@app.get("/voice-agent-config")
def get_voice_agent_config() -> dict[str, Any]:
    """Return a public allow-listed contract for a future voice integration."""
    return {
        "agent": {
            "name": VOICE_AGENT["name"],
            "automated_assistant": VOICE_AGENT["automated_assistant"],
            "opening_messages": OPENING_MESSAGES,
        },
        "organization": {
            "name": ORGANIZATION["name"],
            "industry": ORGANIZATION["industry"],
            "headquarters": ORGANIZATION["headquarters"],
            "demonstration_data": ORGANIZATION["demonstration_data"],
        },
        "supported_languages": ORGANIZATION["supported_languages"],
        "supported_intents": [
            {"name": intent, "allowed_caller_type": role}
            for intent, role in SUPPORTED_INTENTS.items()
        ],
        "tool": {
            "method": "POST",
            "path": "/support-requests",
            "url": f"{PUBLIC_BASE_URL}/support-requests",
            "authentication": {
                "type": "bearer",
                "header": "Authorization",
                "secret_required": True,
            },
            "required_fields": ["caller_id"],
            "optional_fields": ["lot_id", "intent", "language"],
            "language_values": sorted(SUPPORTED_LANGUAGE_CODES),
            "caller_lookup_flow": (
                "Send caller_id first. The API identifies the role and assigned lots. "
                "Send lot_id only after selection when several lots are available. "
                "Intent is inferred from the caller role when omitted."
            ),
        },
        "support_hours": {
            "timezone": SUPPORT_HOURS["timezone"],
            "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "opens_at": SUPPORT_HOURS["opens_at"],
            "closes_at": SUPPORT_HOURS["closes_at"],
            "holidays_modeled": SUPPORT_HOURS["holidays_modeled"],
        },
        "unresolved_request_routing": {
            "during_support_hours": "human_handoff",
            "outside_support_hours": "open_ticket_recommended",
            "creates_real_ticket": False,
        },
        "safety_boundaries": SAFETY_BOUNDARIES,
        "relationship_model": {
            "central_entity": "wood_lot",
            "lot_references": [
                "buyer_id",
                "provider_id",
                "wood_type_id",
                "drying_status_id",
            ],
            "transport_relationship": "wood_lot 1:N transport N:1 transporter",
        },
        "data_notice": (
            "All organizations, callers, lots, measurements, and operational "
            "records are demonstration data. Do not submit real customer data."
        ),
    }


@app.get("/callers/{caller_id}")
def get_caller(caller_id: str) -> dict[str, Any]:
    """Return one demonstration caller profile."""
    return _find_caller(caller_id)


@app.get("/callers/{caller_id}/lots")
def get_caller_lots(caller_id: str) -> dict[str, Any]:
    """Return the lot IDs assigned to one caller without exposing lot details."""
    caller = _find_caller(caller_id)
    lot_ids = [lot["lot_id"] for lot in _lots_for_caller(caller)]
    return {
        "demonstration_data": True,
        "caller_id": caller["caller_id"],
        "caller_type": caller["caller_type"],
        "assigned_lot_count": len(lot_ids),
        "assigned_lot_ids": lot_ids,
    }


@app.get("/lots/{lot_id}")
def get_lot(
    lot_id: str,
    caller_id: str,
    language: Literal["en", "es", "pt"] | None = None,
) -> dict[str, Any]:
    """Return an assigned lot view tailored to the caller's role and language."""
    caller = _find_caller(caller_id)
    lot = _find_lot(lot_id)
    _require_lot_assignment(caller, lot)
    response_language = language or caller["preferred_language"]["code"]

    role_view = _role_response(caller, lot, response_language)

    escalation_recommended = False
    if caller["caller_type"] == "buyer" and caller["support_priority"] == "high":
        escalation_recommended = _buyer_escalation_recommended(lot)

    return {
        "demonstration_data": True,
        "lot_id": lot["lot_id"],
        "caller_id": caller["caller_id"],
        "caller_type": caller["caller_type"],
        "language": response_language,
        "escalation_recommended": escalation_recommended,
        **role_view,
    }


@app.post("/support-requests")
def create_support_response(
    request: SupportRequest,
    _authorized: None = Depends(_require_tool_token),
) -> dict[str, Any]:
    """Resolve one voice-ready demonstration request or recommend follow-up."""
    return _support_request_response(request)
