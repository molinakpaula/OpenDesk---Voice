"""FastAPI wiring for the MaderaFlow voice-support application."""

import logging
import secrets
from time import perf_counter
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from maderaflow.config import (
    APP_ENV,
    LOG_LEVEL,
    MADERAFLOW_TOOL_TOKEN,
    ORGANIZATION,
    PUBLIC_BASE_URL,
    SUPPORTED_LANGUAGE_CODES,
    SUPPORT_HOURS,
    VOICE_AGENT,
)
from maderaflow.models import LanguageCode, SupportRequest
from maderaflow.errors import MaderaFlowNotFoundError
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

app = FastAPI(
    title="MaderaFlow Voice Support API",
    description=(
        "A multilingual demonstration API for wood-drying status and cross-border "
        "logistics coordination. It contains sample records and no real customer data."
    ),
    version="0.7.0",
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


@app.get("/health")
def get_health() -> dict[str, str]:
    """Confirm that the backend can answer requests."""
    return {"status": "ok"}


@app.get("/organization")
def get_organization() -> dict[str, Any]:
    """Return public information about the demonstration organization."""
    return ORGANIZATION


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
