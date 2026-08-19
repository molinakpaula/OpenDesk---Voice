"""FastAPI wiring for the MaderaFlow voice-support application."""

import logging
import secrets
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from maderaflow.config import (
    APP_ENV,
    LOG_LEVEL,
    MADERAFLOW_TOOL_TOKEN,
    ORGANIZATION,
    ORDER_DATABASE_PATH,
    ORDER_INTAKE_CONFIG,
    ORDER_INTAKE_ENABLED,
    PUBLIC_BASE_URL,
    SUPPORTED_LANGUAGE_CODES,
    SUPPORT_HOURS,
    VOICE_AGENT,
)
from maderaflow.models import (
    ElevenLabsPreCallRequest,
    LanguageCode,
    OrderIntakeRequest,
    SupportRequest,
)
from maderaflow.errors import MaderaFlowNotFoundError
from maderaflow.order_intake import (
    build_whatsapp_message,
    creation_spoken_message,
    generate_spanish_summary,
    intake_preview,
    pre_call_response,
    utc_now,
    whatsapp_delivery_state,
)
from maderaflow.order_storage import SQLiteOrderRepository
from maderaflow.repositories import (
    find_caller,
    find_lot,
    lots_for_caller,
    require_lot_assignment,
)
from maderaflow.support import (
    OPENING_MESSAGES,
    SAFETY_BOUNDARIES,
    SUPPORTED_INTENTS,
    buyer_escalation_recommended,
    role_response,
    support_request_response,
)


logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
REQUEST_LOGGER = logging.getLogger("maderaflow.requests")
ORDER_REPOSITORY = SQLiteOrderRepository(ORDER_DATABASE_PATH)

app = FastAPI(
    title="Wood Operations Voice API",
    description=(
        "A multilingual API containing the MaderaFlow lot-status demonstration and "
        "an isolated, disabled-by-default Maderera Las Garzas order-intake milestone."
    ),
    version="0.8.0",
)


@app.exception_handler(MaderaFlowNotFoundError)
async def domain_not_found_handler(
    _request: Request,
    error: MaderaFlowNotFoundError,
) -> JSONResponse:
    """Translate framework-independent lookup errors into HTTP 404 responses."""
    return JSONResponse(status_code=404, content={"detail": str(error)})


@app.middleware("http")
async def log_request_metadata(request: Request, call_next):
    """Log safe metadata without IDs, query strings, or request bodies."""
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


def require_tool_token(authorization: str | None = Header(default=None)) -> None:
    """Require the shared integration token without exposing its value."""
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


def require_order_intake_enabled() -> None:
    """Fail closed in production until durable storage has been configured."""
    if not ORDER_INTAKE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail=(
                "Order intake is disabled. Configure durable storage and set "
                "ORDER_INTAKE_ENABLED=true before accepting customer data."
            ),
        )


@app.get("/health")
def get_health() -> dict[str, str]:
    """Confirm that the backend can answer requests."""
    return {"status": "ok"}


@app.get("/organization")
def get_organization() -> dict[str, Any]:
    """Return public information about the demonstration organization."""
    return ORGANIZATION


@app.get("/order-intake-config")
def get_order_intake_config() -> dict[str, Any]:
    """Return public order-intake facts without phone numbers or secrets."""
    return {
        "organization": ORDER_INTAKE_CONFIG["organization"],
        "supported_languages": ORDER_INTAKE_CONFIG["supported_languages"],
        "working_hours": ORDER_INTAKE_CONFIG["working_hours"],
        "country_routing": {
            "called_number_first": True,
            "caller_prefix_fallback": {"+51": "PE", "+49": "DE"},
            "unknown_country_action": "ask_caller_country",
        },
        "privacy": {
            "transcription_consent_required": True,
            "declined_consent_action": "callback_without_transcript",
            "personal_contact_values_exposed": False,
        },
        "human_confirmation_required_for": [
            "price",
            "availability",
            "timing",
            "transport",
            "documentation",
            "export_conditions",
        ],
        "tool": {
            "preview_url": f"{PUBLIC_BASE_URL}/order-intake/preview",
            "create_url": f"{PUBLIC_BASE_URL}/order-requests",
            "authentication": "bearer",
        },
    }


@app.get("/voice-agent-config")
def get_voice_agent_config() -> dict[str, Any]:
    """Return a public allow-listed voice-integration contract."""
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


@app.get("/callers/{caller_id}/lots")
def get_caller_lots(caller_id: str) -> dict[str, Any]:
    """Return assigned lot IDs without exposing operational details."""
    caller = find_caller(caller_id)
    lot_ids = [lot["lot_id"] for lot in lots_for_caller(caller)]
    return {
        "demonstration_data": True,
        "caller_id": caller["caller_id"],
        "caller_type": caller["caller_type"],
        "assigned_lot_count": len(lot_ids),
        "assigned_lot_ids": lot_ids,
    }


@app.get("/callers/{caller_id}")
def get_caller(caller_id: str) -> dict[str, Any]:
    """Return one demonstration caller profile."""
    return find_caller(caller_id)


@app.get("/lots/{lot_id}")
def get_lot(
    lot_id: str,
    caller_id: str,
    language: LanguageCode | None = None,
) -> dict[str, Any]:
    """Return an assigned lot view scoped to caller role and language."""
    caller = find_caller(caller_id)
    lot = find_lot(lot_id)
    require_lot_assignment(caller, lot)
    response_language = language or caller["preferred_language"]["code"]
    scoped_view = role_response(caller, lot, response_language)

    escalation_recommended = False
    if caller["caller_type"] == "buyer" and caller["support_priority"] == "high":
        escalation_recommended = buyer_escalation_recommended(lot)

    return {
        "demonstration_data": True,
        "lot_id": lot["lot_id"],
        "caller_id": caller["caller_id"],
        "caller_type": caller["caller_type"],
        "language": response_language,
        "escalation_recommended": escalation_recommended,
        **scoped_view,
    }


@app.post("/support-requests")
def create_support_response(
    request: SupportRequest,
    _authorized: None = Depends(require_tool_token),
) -> dict[str, Any]:
    """Resolve a voice-ready request or recommend safe follow-up."""
    return support_request_response(request)


@app.post("/order-intake/preview")
def preview_order_intake(
    request: OrderIntakeRequest,
    _authorized: None = Depends(require_tool_token),
) -> dict[str, Any]:
    """Return the next required question without storing customer data."""
    return intake_preview(request)


@app.post("/elevenlabs/pre-call")
def configure_inbound_call(
    request: ElevenLabsPreCallRequest,
    _authorized: None = Depends(require_tool_token),
) -> dict[str, Any]:
    """Choose the opening language before an inbound phone call connects."""
    return pre_call_response(
        caller_number=request.caller_id,
        called_number=request.called_number,
        call_sid=request.call_sid,
    )


@app.post("/order-requests")
def create_order_request(
    request: OrderIntakeRequest,
    _authorized: None = Depends(require_tool_token),
    _enabled: None = Depends(require_order_intake_enabled),
) -> dict[str, Any]:
    """Validate and save one confirmed request without faking notification."""
    preview = intake_preview(request)
    if preview["contact_declined"]:
        return {
            **preview,
            "saved": False,
            "processed": False,
            "next_action": "end_without_storing_customer_request",
            "spoken_message": {
                "es": "Entendido. No registraré una solicitud de contacto. Gracias por llamar.",
                "de": "Verstanden. Ich speichere keine Kontaktanfrage. Vielen Dank für Ihren Anruf.",
                "en": "Understood. I will not store a contact request. Thank you for calling.",
            }[preview["language"]],
        }
    if not preview["ready_to_create"]:
        return {
            **preview,
            "saved": False,
            "processed": False,
            "next_action": "ask_next_question",
            "spoken_message": preview["next_question"],
        }

    country_for_id = preview["country"] if preview["country"] in {"PE", "DE"} else "OT"
    language = preview["language"]
    now_utc = utc_now()
    lima_timezone = ZoneInfo(ORDER_INTAKE_CONFIG["working_hours"]["timezone"])
    local_date = now_utc.astimezone(lima_timezone).date().isoformat()
    status = (
        ORDER_INTAKE_CONFIG["order_rules"]["callback_status"]
        if request.transcription_consent is False
        else ORDER_INTAKE_CONFIG["order_rules"]["initial_status"]
    )
    summary = generate_spanish_summary(request, preview["country"])
    delivery_status, alert_visible = whatsapp_delivery_state()
    stored = ORDER_REPOSITORY.create(
        request,
        country_code=country_for_id,
        language_code=language,
        status=status,
        spanish_summary=summary,
        escalation_reasons=preview["escalation_reasons"],
        whatsapp_message_factory=lambda request_id: build_whatsapp_message(
            request_id,
            request,
            preview["country"],
            summary,
            preview["escalation_reasons"],
        ),
        whatsapp_delivery_status=delivery_status,
        alert_visible=alert_visible,
        now_utc=now_utc,
        local_date=local_date,
    )
    return {
        "saved": True,
        "processed": stored["whatsapp_delivery_status"] == "DELIVERED",
        "request_id": stored["request_id"],
        "request_created": stored["created"],
        "status": stored["status"],
        "country": preview["country"],
        "language": language,
        "escalation_recommended": preview["escalation_recommended"],
        "escalation_reasons": preview["escalation_reasons"],
        "whatsapp_delivery_status": stored["whatsapp_delivery_status"],
        "alert_visible": stored["alert_visible"],
        "next_action": "internal_notification_pending",
        "spoken_message": creation_spoken_message(stored["request_id"], language),
    }
