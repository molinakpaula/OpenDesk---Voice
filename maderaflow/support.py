"""Role-aware business rules and multilingual voice-ready responses."""

from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from maderaflow.config import ESCALATION_TRIGGERS, SUPPORT_HOURS
from maderaflow.models import SupportRequest
from maderaflow.repositories import (
    find_caller,
    find_lot,
    lots_for_caller,
    require_lot_assignment,
    transports_for_lot,
)


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
    "not_ready": {"en": "not ready", "es": "no listo", "pt": "não pronto"},
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
    """Translate an internal operational code without changing stored data."""
    return LABELS.get(value, {}).get(language, value.replace("_", " "))


def _lot_selection_response(
    caller: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    """Ask for a lot selection when one caller maps to several lots."""
    available_lots = [lot["lot_id"] for lot in lots_for_caller(caller)]
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
            f"fecha no está garantizada. El estado de envío es {transport_readiness}."
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
    movements = transports_for_lot(lot["lot_id"], caller["caller_id"])
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
            f"Lot {lot['lot_id']} collection readiness is {collection_status}. "
            f"Destination: {current_movement['destination']}. {schedule_text['en']}"
        ),
        "es": (
            f"La preparación para recoger el lote {lot['lot_id']} es "
            f"{collection_status}. Destino: {current_movement['destination']}. "
            f"{schedule_text['es']}"
        ),
        "pt": (
            f"A situação de coleta do lote {lot['lot_id']} é {collection_status}. "
            f"Destino: {current_movement['destination']}. {schedule_text['pt']}"
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


def role_response(
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


def buyer_escalation_recommended(lot: dict[str, Any]) -> bool:
    """Apply configured delay, schedule-risk, and quality triggers."""
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


def now_in_lima() -> datetime:
    """Return the current time in the configured support timezone."""
    return datetime.now(ZoneInfo(SUPPORT_HOURS["timezone"]))


def support_is_open(now: datetime | None = None) -> bool:
    """Check demonstration weekday support hours."""
    current = now or now_in_lima()
    opens_at = time.fromisoformat(SUPPORT_HOURS["opens_at"])
    closes_at = time.fromisoformat(SUPPORT_HOURS["closes_at"])
    return (
        current.weekday() in SUPPORT_HOURS["working_days"]
        and opens_at <= current.time().replace(tzinfo=None) < closes_at
    )


def _fallback_response(language: str, reason: str) -> dict[str, Any]:
    support_open = support_is_open()
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


def support_request_response(request: SupportRequest) -> dict[str, Any]:
    """Resolve a caller-first voice request through deterministic rules."""
    caller = find_caller(request.caller_id)
    language = request.language or caller["preferred_language"]["code"]
    allowed_intent_by_role = {role: intent for intent, role in SUPPORTED_INTENTS.items()}
    assigned_lots = lots_for_caller(caller)
    provided_lot_id = request.lot_id.strip() if request.lot_id else None
    provided_intent = request.intent.strip() if request.intent else None

    if provided_lot_id is None:
        if len(assigned_lots) != 1:
            return _lot_selection_response(caller, language)
        lot = assigned_lots[0]
    else:
        lot = find_lot(provided_lot_id)
        require_lot_assignment(caller, lot)

    inferred_intent = allowed_intent_by_role[caller["caller_type"]]
    intent = provided_intent or inferred_intent

    if intent not in SUPPORTED_INTENTS:
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

    role_view = role_response(caller, lot, language)
    escalation = (
        caller["caller_type"] == "buyer"
        and caller["support_priority"] == "high"
        and buyer_escalation_recommended(lot)
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
