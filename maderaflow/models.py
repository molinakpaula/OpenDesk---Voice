"""Typed request models shared by the API and business services."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


LanguageCode = Literal["en", "es", "pt"]
OrderLanguageCode = Literal["es", "de", "en"]
OrderCountryCode = Literal["PE", "DE", "OTHER"]
CallReason = Literal[
    "new_quote",
    "new_order_request",
    "drying_question",
    "sawn_wood_question",
    "peru_city_request",
    "export_question",
    "germany_request",
    "existing_request_follow_up",
    "wood_supplier",
    "transporter",
    "complaint",
    "other",
]
ServiceNeeded = Literal["sawing", "drying", "both", "other"]
PreferredContactMethod = Literal["phone", "whatsapp", "email"]
IncotermPreference = Literal["FOB", "CIF", "UNDECIDED"]


class SupportRequest(BaseModel):
    """Context supplied by the voice layer, beginning with a caller ID."""

    caller_id: str
    lot_id: str | None = None
    intent: str | None = None
    language: LanguageCode | None = None


class OrderIntakeRequest(BaseModel):
    """Structured information collected by the after-hours voice agent.

    Most fields are optional because callers may not know every technical or
    logistics detail. The business service decides which unanswered fields
    still need a question before a request can be created.
    """

    conversation_id: str = Field(min_length=1, max_length=200)
    called_number: str | None = Field(default=None, max_length=40)
    caller_number: str | None = Field(default=None, max_length=40)
    country: OrderCountryCode | None = None
    language: OrderLanguageCode | None = None
    transcription_consent: bool | None = None
    contact_authorized: bool | None = None
    customer_confirmed: bool = False
    call_reason: CallReason | None = None

    customer_name: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    job_title_or_department: str | None = Field(default=None, max_length=200)
    customer_country: str | None = Field(default=None, max_length=100)
    customer_city: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=40)
    whatsapp: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=320)
    preferred_contact_method: PreferredContactMethod | None = None
    best_contact_time: str | None = Field(default=None, max_length=200)

    service_needed: ServiceNeeded | None = None
    customer_has_wood: bool | None = None
    current_wood_location: str | None = Field(default=None, max_length=300)
    supplier_coordination_needed: bool | None = None
    species_common_name: str | None = Field(default=None, max_length=200)
    species_scientific_name: str | None = Field(default=None, max_length=200)
    presentation: str | None = Field(default=None, max_length=100)
    dimensions: str | None = Field(default=None, max_length=300)
    dimension_unit: str | None = Field(default=None, max_length=50)
    piece_count: int | None = Field(default=None, ge=1)
    approximate_volume_m3: float | None = Field(default=None, gt=0)
    initial_moisture_percentage: float | None = Field(default=None, ge=0, le=100)
    target_moisture_percentage: float | None = Field(default=None, ge=0, le=100)
    final_use: str | None = Field(default=None, max_length=500)
    moisture_certificate_requested: bool | None = None
    required_date: date | None = None
    quality_requirements: str | None = Field(default=None, max_length=1000)
    photos_or_documents_available: bool | None = None
    required_certifications_or_documents: str | None = Field(
        default=None,
        max_length=1000,
    )

    destination_city_country: str | None = Field(default=None, max_length=300)
    estimated_plant_arrival_date: date | None = None
    inbound_transport_responsible: str | None = Field(default=None, max_length=300)
    outbound_collection_responsible: str | None = Field(default=None, max_length=300)
    transporter_details: str | None = Field(default=None, max_length=500)
    peru_order_scope: Literal["full_lot", "partial_lot"] | None = None

    preferred_destination_port: str | None = Field(default=None, max_length=200)
    order_frequency: str | None = Field(default=None, max_length=200)
    required_shipping_date: date | None = None
    incoterm_preference: IncotermPreference | None = None
    has_importer_customs_agent_or_transporter: bool | None = None
    importer_customs_agent_or_transporter_details: str | None = Field(
        default=None,
        max_length=500,
    )
    sample_requested: bool | None = None
    preferred_quote_currency: str | None = Field(default=None, max_length=50)

    definitive_price_or_discount_requested: bool = False
    chamber_reservation_requested: bool = False
    confirmation_or_payment_requested: bool = False
    complex_export_or_documentation_question: bool = False
    agent_did_not_understand: bool = False
    additional_comments: str | None = Field(default=None, max_length=2000)
    unknown_fields: list[str] = Field(default_factory=list, max_length=50)

    @field_validator(
        "called_number",
        "caller_number",
        "customer_name",
        "company",
        "job_title_or_department",
        "customer_country",
        "customer_city",
        "phone",
        "whatsapp",
        "email",
        "best_contact_time",
        "current_wood_location",
        "species_common_name",
        "species_scientific_name",
        "presentation",
        "dimensions",
        "dimension_unit",
        "final_use",
        "quality_requirements",
        "required_certifications_or_documents",
        "destination_city_country",
        "inbound_transport_responsible",
        "outbound_collection_responsible",
        "transporter_details",
        "preferred_destination_port",
        "order_frequency",
        "importer_customs_agent_or_transporter_details",
        "preferred_quote_currency",
        "additional_comments",
        mode="before",
    )
    @classmethod
    def blank_strings_become_none(cls, value):
        """Treat empty webhook strings as missing conversation answers."""
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value

    @field_validator("unknown_fields")
    @classmethod
    def unknown_fields_cannot_bypass_identity_or_consent(
        cls,
        value: list[str],
    ) -> list[str]:
        """Allow honest unknown facts but never bypass consent or contact rules."""
        protected_fields = {
            "conversation_id",
            "called_number",
            "caller_number",
            "country",
            "language",
            "transcription_consent",
            "contact_authorized",
            "customer_confirmed",
            "customer_confirmation",
            "contact_details",
            "call_reason",
            "customer_name",
            "customer_country",
            "customer_city",
            "preferred_contact_method",
            "best_contact_time",
            "service_needed",
        }
        invalid = sorted(set(value) & protected_fields)
        if invalid:
            raise ValueError(
                "unknown_fields cannot replace required consent, identity, contact, "
                f"or service answers: {', '.join(invalid)}"
            )
        return list(dict.fromkeys(value))


class ElevenLabsPreCallRequest(BaseModel):
    """Phone metadata sent before an inbound ElevenLabs conversation starts."""

    caller_id: str | None = Field(default=None, max_length=40)
    called_number: str | None = Field(default=None, max_length=40)
    agent_id: str | None = Field(default=None, max_length=200)
    call_sid: str | None = Field(default=None, max_length=200)
