"""Deterministic rules for multilingual, after-hours order intake."""

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from maderaflow.config import (
    GERMANY_INBOUND_NUMBER,
    ORDER_INTAKE_CONFIG,
    ORDER_NOTIFICATION_WHATSAPP,
    ORDER_REVIEWER_NAME,
    PERU_INBOUND_NUMBER,
)
from maderaflow.models import OrderIntakeRequest


ORDER_REASONS = {
    "new_quote",
    "new_order_request",
    "drying_question",
    "sawn_wood_question",
    "peru_city_request",
    "export_question",
    "germany_request",
}

COMMON_ORDER_FIELDS = [
    "service_needed",
    "customer_has_wood",
    "supplier_coordination_needed",
    "species_common_name",
    "presentation",
    "dimensions",
    "dimension_unit",
    "quantity_or_volume",
    "final_use",
    "moisture_certificate_requested",
    "required_date",
    "quality_requirements",
    "photos_or_documents_available",
    "required_certifications_or_documents",
]

PERU_ORDER_FIELDS = [
    "current_wood_location",
    "destination_city_country",
    "estimated_plant_arrival_date",
    "inbound_transport_responsible",
    "outbound_collection_responsible",
    "peru_order_scope",
]

GERMANY_ORDER_FIELDS = [
    "destination_city_country",
    "preferred_destination_port",
    "approximate_volume_m3",
    "order_frequency",
    "required_shipping_date",
    "incoterm_preference",
    "has_importer_customs_agent_or_transporter",
    "required_certifications_or_documents",
    "sample_requested",
    "preferred_quote_currency",
]

QUESTION_TEXT = {
    "transcription_consent": {
        "es": "¿Autoriza que la conversación sea transcrita para registrar y revisar su solicitud?",
        "de": "Stimmen Sie zu, dass dieses Gespräch zur Bearbeitung Ihrer Anfrage transkribiert wird?",
        "en": "Do you agree to this conversation being transcribed to process your request?",
    },
    "contact_authorized": {
        "es": "¿Autoriza que la persona responsable se comunique con usted?",
        "de": "Darf sich die zuständige Person mit Ihnen in Verbindung setzen?",
        "en": "May the responsible person contact you?",
    },
    "contact_details": {
        "es": "¿Qué teléfono, WhatsApp o correo desea proporcionar para la respuesta?",
        "de": "Welche Telefonnummer, WhatsApp-Nummer oder E-Mail-Adresse dürfen wir für die Antwort verwenden?",
        "en": "Which phone number, WhatsApp number, or email may we use for the response?",
    },
    "call_reason": {
        "es": "¿Cuál es el motivo principal de su llamada?",
        "de": "Was ist der Hauptgrund für Ihren Anruf?",
        "en": "What is the main reason for your call?",
    },
    "customer_name": {
        "es": "¿Cuál es su nombre completo?",
        "de": "Wie lautet Ihr vollständiger Name?",
        "en": "What is your full name?",
    },
    "customer_country": {
        "es": "¿En qué país se encuentra?",
        "de": "In welchem Land befinden Sie sich?",
        "en": "Which country are you in?",
    },
    "customer_city": {
        "es": "¿En qué ciudad se encuentra?",
        "de": "In welcher Stadt befinden Sie sich?",
        "en": "Which city are you in?",
    },
    "preferred_contact_method": {
        "es": "¿Prefiere recibir la respuesta por teléfono, WhatsApp o correo?",
        "de": "Möchten Sie die Antwort per Telefon, WhatsApp oder E-Mail erhalten?",
        "en": "Would you prefer the response by phone, WhatsApp, or email?",
    },
    "best_contact_time": {
        "es": "¿Cuál es el mejor horario para contactarlo?",
        "de": "Wann können wir Sie am besten erreichen?",
        "en": "What is the best time to contact you?",
    },
    "service_needed": {
        "es": "¿Necesita aserrado, secado o ambos servicios?",
        "de": "Benötigen Sie Schnittholz, Holztrocknung oder beides?",
        "en": "Do you need sawing, kiln drying, or both?",
    },
    "customer_has_wood": {
        "es": "¿Ya tiene la madera?",
        "de": "Besitzen Sie das Holz bereits?",
        "en": "Do you already have the wood?",
    },
    "supplier_coordination_needed": {
        "es": "¿Necesita ayuda para coordinar con un proveedor?",
        "de": "Benötigen Sie Unterstützung bei der Koordination mit einem Lieferanten?",
        "en": "Do you need help coordinating with a supplier?",
    },
    "species_common_name": {
        "es": "¿Cuál es la especie de madera?",
        "de": "Um welche Holzart handelt es sich?",
        "en": "What is the wood species?",
    },
    "presentation": {
        "es": "¿La madera se presenta en tablas, listones u otra forma?",
        "de": "Liegt das Holz als Bretter, Leisten oder in einer anderen Form vor?",
        "en": "Is the wood in boards, strips, or another form?",
    },
    "dimensions": {
        "es": "¿Cuáles son el largo, ancho y espesor?",
        "de": "Wie lauten Länge, Breite und Stärke?",
        "en": "What are the length, width, and thickness?",
    },
    "dimension_unit": {
        "es": "¿Esas medidas están en milímetros, centímetros o pulgadas?",
        "de": "Sind diese Maße in Millimetern, Zentimetern oder Zoll angegeben?",
        "en": "Are those measurements in millimetres, centimetres, or inches?",
    },
    "quantity_or_volume": {
        "es": "¿Cuántas piezas tiene o cuál es el volumen aproximado en metros cúbicos?",
        "de": "Wie viele Stücke sind es oder wie groß ist das ungefähre Volumen in Kubikmetern?",
        "en": "How many pieces are there, or what is the approximate volume in cubic metres?",
    },
    "target_moisture_percentage": {
        "es": "¿Qué humedad final necesita?",
        "de": "Welche Endfeuchte benötigen Sie?",
        "en": "What final moisture level do you require?",
    },
    "final_use": {
        "es": "¿Cuál será el uso final de la madera?",
        "de": "Wofür wird das Holz letztlich verwendet?",
        "en": "What will the wood be used for?",
    },
    "moisture_certificate_requested": {
        "es": "¿Necesita un certificado de humedad?",
        "de": "Benötigen Sie ein Feuchtigkeitszertifikat?",
        "en": "Do you need a moisture certificate?",
    },
    "required_date": {
        "es": "¿Para qué fecha necesita el servicio o la madera?",
        "de": "Bis zu welchem Datum benötigen Sie die Leistung oder das Holz?",
        "en": "By what date do you need the service or wood?",
    },
    "quality_requirements": {
        "es": "¿Tiene algún requisito de calidad que debamos registrar?",
        "de": "Welche Qualitätsanforderungen sollen wir aufnehmen?",
        "en": "Are there any quality requirements we should record?",
    },
    "photos_or_documents_available": {
        "es": "¿Tiene fotografías o documentos disponibles?",
        "de": "Haben Sie Fotos oder Unterlagen zur Verfügung?",
        "en": "Do you have photos or documents available?",
    },
    "required_certifications_or_documents": {
        "es": "¿Qué documentos o certificaciones necesita?",
        "de": "Welche Dokumente oder Zertifizierungen benötigen Sie?",
        "en": "Which documents or certifications do you require?",
    },
    "current_wood_location": {
        "es": "¿Dónde se encuentra actualmente la madera?",
        "de": "Wo befindet sich das Holz derzeit?",
        "en": "Where is the wood currently located?",
    },
    "destination_city_country": {
        "es": "¿Cuál es la ciudad y el país de destino?",
        "de": "In welche Stadt und welches Land soll das Holz geliefert werden?",
        "en": "What are the destination city and country?",
    },
    "estimated_plant_arrival_date": {
        "es": "¿Cuándo estima que la madera llegará a la planta en Puerto Maldonado?",
        "de": "Wann wird das Holz voraussichtlich im Werk in Puerto Maldonado eintreffen?",
        "en": "When is the wood expected to arrive at the Puerto Maldonado facility?",
    },
    "inbound_transport_responsible": {
        "es": "¿Quién transportará la madera hasta Puerto Maldonado?",
        "de": "Wer transportiert das Holz nach Puerto Maldonado?",
        "en": "Who will transport the wood to Puerto Maldonado?",
    },
    "outbound_collection_responsible": {
        "es": "¿Quién recogerá la madera después del proceso?",
        "de": "Wer holt das Holz nach der Bearbeitung ab?",
        "en": "Who will collect the wood after processing?",
    },
    "peru_order_scope": {
        "es": "¿Desea procesar el lote completo o solo una parte?",
        "de": "Soll die gesamte Charge oder nur ein Teil bearbeitet werden?",
        "en": "Do you need the full lot or only part of it processed?",
    },
    "preferred_destination_port": {
        "es": "¿Cuál es su puerto de destino preferido?",
        "de": "Welchen Zielhafen bevorzugen Sie?",
        "en": "What is your preferred destination port?",
    },
    "approximate_volume_m3": {
        "es": "¿Cuál es el volumen total aproximado en metros cúbicos?",
        "de": "Wie groß ist das gesamte ungefähre Volumen in Kubikmetern?",
        "en": "What is the approximate total volume in cubic metres?",
    },
    "order_frequency": {
        "es": "¿Es un pedido único o recurrente, y con qué frecuencia?",
        "de": "Handelt es sich um eine einmalige oder regelmäßige Bestellung, und in welchem Rhythmus?",
        "en": "Is this a one-time or recurring order, and how often?",
    },
    "required_shipping_date": {
        "es": "¿Para qué fecha necesita el embarque?",
        "de": "Für welches Datum benötigen Sie den Versand?",
        "en": "What shipping date do you require?",
    },
    "incoterm_preference": {
        "es": "¿Desea una cotización FOB, CIF o todavía está por definir?",
        "de": "Wünschen Sie ein Angebot auf FOB- oder CIF-Basis, oder ist das noch offen?",
        "en": "Would you like an FOB or CIF quote, or is that undecided?",
    },
    "has_importer_customs_agent_or_transporter": {
        "es": "¿Ya cuenta con importador, agente aduanero o transportista?",
        "de": "Haben Sie bereits einen Importeur, Zollagenten oder Spediteur?",
        "en": "Do you already have an importer, customs agent, or transporter?",
    },
    "sample_requested": {
        "es": "¿Necesita una muestra?",
        "de": "Benötigen Sie ein Muster?",
        "en": "Do you need a sample?",
    },
    "preferred_quote_currency": {
        "es": "¿En qué moneda prefiere recibir la cotización?",
        "de": "In welcher Währung möchten Sie das Angebot erhalten?",
        "en": "Which currency would you prefer for the quote?",
    },
    "customer_confirmation": {
        "es": "Voy a resumir los datos registrados. ¿Son correctos?",
        "de": "Ich fasse die aufgenommenen Angaben zusammen. Sind diese korrekt?",
        "en": "I will summarize the recorded details. Are they correct?",
    },
}

ORDER_OPENING_MESSAGES = {
    "es": (
        "Buenos días. Habla con el asistente virtual de Maderera Las Garzas. "
        "Ofrecemos madera aserrada y secado industrial en Puerto Maldonado. "
        "Para registrar correctamente su solicitud, necesito procesar y "
        "transcribir esta conversación y enviarla para revisión humana. "
        "¿Está de acuerdo?"
    ),
    "de": (
        "Guten Tag. Sie sprechen mit dem digitalen Assistenten von Maderera Las "
        "Garzas. Wir bieten Schnittholz und industrielle Holztrocknung in Peru an. "
        "Damit wir Ihre Anfrage korrekt bearbeiten können, muss ich dieses Gespräch "
        "verarbeiten und transkribieren und die Angaben zur menschlichen Prüfung "
        "weiterleiten. Stimmen Sie dem zu?"
    ),
    "en": (
        "Hello. You have reached the virtual assistant for Maderera Las Garzas. "
        "We provide sawn wood and industrial kiln drying in Peru. To register your "
        "request correctly, I need to process and transcribe this conversation and "
        "send the information for human review. Do you agree?"
    ),
}


def _phone_key(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def detect_caller_country(request: OrderIntakeRequest) -> str:
    """Infer PE or DE from explicit context, called number, then caller prefix."""
    if request.country is not None:
        return request.country

    called_key = _phone_key(request.called_number)
    configured_routes = {
        _phone_key(PERU_INBOUND_NUMBER): "PE",
        _phone_key(GERMANY_INBOUND_NUMBER): "DE",
    }
    configured_routes.pop("", None)
    if called_key in configured_routes:
        return configured_routes[called_key]

    for number in (request.called_number, request.caller_number):
        compact = (number or "").replace(" ", "")
        if compact.startswith("+51") or _phone_key(compact).startswith("51"):
            return "PE"
        if compact.startswith("+49") or _phone_key(compact).startswith("49"):
            return "DE"
    return "OTHER"


def detect_preferred_language(request: OrderIntakeRequest, country: str) -> str:
    """Respect an active language, otherwise use the country opening language."""
    if request.language is not None:
        return request.language
    return {"PE": "es", "DE": "de"}.get(country, "en")


def pre_call_response(
    *,
    caller_number: str | None,
    called_number: str | None,
    call_sid: str | None,
) -> dict[str, Any]:
    """Select the first message before audio connects to the agent."""
    context = OrderIntakeRequest(
        conversation_id=call_sid or "pre-call-without-call-sid",
        caller_number=caller_number,
        called_number=called_number,
    )
    country = detect_caller_country(context)
    language = detect_preferred_language(context, country)
    return {
        "type": "conversation_initiation_client_data",
        "conversation_config_override": {
            "agent": {
                "first_message": ORDER_OPENING_MESSAGES[language],
                "language": language,
            }
        },
        "dynamic_variables": {
            "caller_country": country,
            "opening_language": language,
        },
    }


def _answered(request: OrderIntakeRequest, field_name: str) -> bool:
    if field_name in request.unknown_fields:
        return True
    if field_name == "quantity_or_volume":
        return request.piece_count is not None or request.approximate_volume_m3 is not None
    value = getattr(request, field_name)
    return value is not None


def missing_order_fields(request: OrderIntakeRequest, country: str) -> list[str]:
    """Return unanswered fields in the exact order the agent should ask them."""
    if request.transcription_consent is None:
        return ["transcription_consent"]

    if request.transcription_consent is False:
        missing = []
        if request.contact_authorized is None:
            missing.append("contact_authorized")
        if request.contact_authorized and not any(
            (request.phone, request.whatsapp, request.email)
        ):
            missing.append("contact_details")
        if not missing and request.contact_authorized and not request.customer_confirmed:
            missing.append("customer_confirmation")
        return missing

    fields = [
        "call_reason",
        "customer_name",
        "customer_country",
        "customer_city",
        "preferred_contact_method",
        "best_contact_time",
        "contact_authorized",
    ]
    missing = [field for field in fields if not _answered(request, field)]

    if request.preferred_contact_method == "phone" and request.phone is None:
        missing.append("contact_details")
    elif request.preferred_contact_method == "whatsapp" and request.whatsapp is None:
        missing.append("contact_details")
    elif request.preferred_contact_method == "email" and request.email is None:
        missing.append("contact_details")

    if request.call_reason in ORDER_REASONS:
        order_fields = list(COMMON_ORDER_FIELDS)
        if request.customer_has_wood is True:
            order_fields.insert(2, "current_wood_location")
        if request.service_needed in {"drying", "both"}:
            order_fields.insert(
                order_fields.index("final_use"),
                "target_moisture_percentage",
            )
        if country == "PE":
            order_fields.extend(PERU_ORDER_FIELDS)
        elif country == "DE":
            order_fields.extend(GERMANY_ORDER_FIELDS)
        missing.extend(
            field
            for field in order_fields
            if field not in missing and not _answered(request, field)
        )

    if not missing and not request.customer_confirmed:
        missing.append("customer_confirmation")
    return missing


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )


def escalation_reasons(
    request: OrderIntakeRequest,
    now_lima: datetime | None = None,
) -> list[str]:
    """Apply the business-approved human-review triggers."""
    reasons: list[str] = []
    configured = ORDER_INTAKE_CONFIG["escalation_rules"]
    known_species = {
        _fold(species["common_name"])
        for species in ORDER_INTAKE_CONFIG["organization"]["known_species"]
    }
    if (
        configured["unknown_species"]
        and request.species_common_name
        and _fold(request.species_common_name) not in known_species
    ):
        reasons.append("unknown_species")

    moisture_range = ORDER_INTAKE_CONFIG["organization"]["usual_drying"]
    target = request.target_moisture_percentage
    if (
        configured["target_moisture_outside_usual_range"]
        and target is not None
        and not (
            moisture_range["target_moisture_percentage_min"]
            <= target
            <= moisture_range["target_moisture_percentage_max"]
        )
    ):
        reasons.append("target_moisture_outside_usual_range")

    current_lima = now_lima or datetime.now(
        ZoneInfo(ORDER_INTAKE_CONFIG["working_hours"]["timezone"])
    )
    if request.required_date is not None:
        days_until_required = (request.required_date - current_lima.date()).days
        if days_until_required < configured["required_in_less_than_days"]:
            reasons.append("required_in_less_than_20_days")

    if (
        request.approximate_volume_m3 is not None
        and request.approximate_volume_m3
        > configured["volume_above_cubic_metres"]
    ):
        reasons.append("volume_above_installed_capacity")
    if configured["complaint"] and request.call_reason == "complaint":
        reasons.append("complaint")
    flag_rules = {
        "definitive_price_or_discount_requested": "definitive_price_or_discount",
        "chamber_reservation_requested": "chamber_reservation",
        "confirmation_or_payment_requested": "confirmation_or_payment",
        "complex_export_or_documentation_question": "complex_export_or_documentation",
        "agent_did_not_understand": "agent_did_not_understand",
    }
    for request_field, reason in flag_rules.items():
        if getattr(request, request_field):
            reasons.append(reason)
    return reasons


def next_question(field_name: str | None, language: str) -> str | None:
    """Translate the next deterministic question for ElevenLabs to speak."""
    if field_name is None:
        return None
    return QUESTION_TEXT[field_name][language]


def intake_preview(request: OrderIntakeRequest) -> dict[str, Any]:
    """Tell the voice layer what remains before it may create a request."""
    country = detect_caller_country(request)
    language = detect_preferred_language(request, country)
    missing = missing_order_fields(request, country)
    contact_declined = request.contact_authorized is False
    next_field = missing[0] if missing else None
    escalation = escalation_reasons(request)
    return {
        "country": country,
        "language": language,
        "ready_to_create": not missing and not contact_declined,
        "contact_declined": contact_declined,
        "missing_fields": missing,
        "next_field": next_field,
        "next_question": next_question(next_field, language),
        "escalation_recommended": bool(escalation),
        "escalation_reasons": escalation,
    }


def generate_spanish_summary(request: OrderIntakeRequest, country: str) -> str:
    """Build a concise, deterministic Spanish summary for human review."""
    values = {
        "name": request.customer_name or "No indicado",
        "company": request.company or "No indicada",
        "location": ", ".join(
            part for part in (request.customer_city, request.customer_country) if part
        ) or "No indicada",
        "service": request.service_needed or "No indicado",
        "species": request.species_common_name or "No indicada",
        "dimensions": request.dimensions or "No indicadas",
        "volume": (
            f"{request.approximate_volume_m3} m³"
            if request.approximate_volume_m3 is not None
            else "No indicado"
        ),
        "target": (
            f"{request.target_moisture_percentage}%"
            if request.target_moisture_percentage is not None
            else "No indicada"
        ),
        "destination": request.destination_city_country or "No indicado",
        "date": str(request.required_date) if request.required_date else "No indicada",
        "incoterm": request.incoterm_preference or "No definido",
    }
    return (
        f"Solicitud procedente de {country}. Cliente: {values['name']}; empresa: "
        f"{values['company']}; ubicación: {values['location']}. Servicio: "
        f"{values['service']}; especie: {values['species']}; medidas: "
        f"{values['dimensions']}; volumen: {values['volume']}; humedad final: "
        f"{values['target']}; destino: {values['destination']}; fecha requerida: "
        f"{values['date']}; condición solicitada: {values['incoterm']}. "
        "Precio, disponibilidad, plazo y condiciones quedan pendientes de revisión humana."
    )


def build_whatsapp_message(
    request_id: str,
    request: OrderIntakeRequest,
    country: str,
    spanish_summary: str,
    escalation: list[str],
) -> str:
    """Format the structured Spanish notification without sending it."""
    contact = request.whatsapp or request.phone or request.email or "No indicado"
    escalation_text = ", ".join(escalation) if escalation else "ninguno"
    return (
        "NUEVA SOLICITUD — MADERERA LAS GARZAS\n\n"
        f"Solicitud: {request_id}\n"
        f"Origen: {country}\n"
        f"Idioma: {request.language or 'inferido'}\n"
        f"Cliente: {request.customer_name or 'No indicado'}\n"
        f"Empresa: {request.company or 'No indicada'}\n"
        f"Contacto preferido: {request.preferred_contact_method or 'No indicado'}\n"
        f"Dato de contacto: {contact}\n\n"
        f"Servicio: {request.service_needed or 'No indicado'}\n"
        f"Especie: {request.species_common_name or 'No indicada'}\n"
        f"Medidas: {request.dimensions or 'No indicadas'} "
        f"{request.dimension_unit or ''}\n"
        f"Piezas: {request.piece_count or 'No indicadas'}\n"
        f"Volumen: {request.approximate_volume_m3 or 'No indicado'} m³\n"
        f"Humedad final: {request.target_moisture_percentage or 'No indicada'}%\n"
        f"Destino: {request.destination_city_country or 'No indicado'}\n"
        f"FOB/CIF: {request.incoterm_preference or 'Por definir'}\n\n"
        f"Escalamiento: {escalation_text}\n\n"
        f"RESUMEN EN ESPAÑOL\n{spanish_summary}\n\n"
        "LA PERSONA RESPONSABLE DEBE CONFIRMAR\n"
        "Viabilidad técnica, disponibilidad, plazo, precio, transporte, "
        "documentación y condiciones comerciales."
    )


def creation_spoken_message(request_id: str, language: str) -> str:
    """Confirm storage while avoiding a false WhatsApp-delivery claim."""
    reviewer = ORDER_REVIEWER_NAME
    messages = {
        "es": (
            f"Hemos guardado su solicitud con el número {request_id}. {reviewer} "
            "revisará la información antes de confirmar precio, disponibilidad, plazo "
            "y condiciones. La notificación interna todavía está pendiente."
        ),
        "de": (
            f"Ihre Anfrage wurde unter der Nummer {request_id} gespeichert. "
            f"{reviewer} prüft die Angaben, bevor Preis, Verfügbarkeit, Termin und "
            "Bedingungen bestätigt werden. Die interne Benachrichtigung steht noch aus."
        ),
        "en": (
            f"Your request has been saved as {request_id}. {reviewer} will review the "
            "information before price, availability, timing, and terms are confirmed. "
            "The internal notification is still pending."
        ),
    }
    return messages[language]


def whatsapp_delivery_state() -> tuple[str, bool]:
    """Expose honest delivery state until a real WhatsApp sender is configured."""
    if ORDER_NOTIFICATION_WHATSAPP:
        return "PENDING_SENDER_IMPLEMENTATION", True
    return "PENDING_CONFIGURATION", True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
