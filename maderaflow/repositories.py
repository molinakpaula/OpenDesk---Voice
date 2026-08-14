"""Speech-friendly identifiers and caller-to-record relationship lookups."""

import unicodedata
from typing import Any

from maderaflow.config import CALLERS, LOTS, TRANSPORTS
from maderaflow.errors import LotAssignmentError, UnknownCallerError, UnknownLotError


def voice_identifier_key(value: str) -> str:
    """Fold a spoken or typed identifier into a comparison-only key."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character
        for character in decomposed
        if character.isalnum() and not unicodedata.combining(character)
    )


def build_voice_aliases(
    alias_groups: dict[str, set[str]],
    configured_records: dict[str, dict[str, Any]],
    id_field: str,
) -> dict[str, str]:
    """Build an alias index and reject ambiguous speech mappings."""
    alias_index: dict[str, str] = {}
    for canonical_key, aliases in alias_groups.items():
        if canonical_key not in configured_records:
            raise RuntimeError(f"Voice alias references unknown ID: {canonical_key}")

        canonical_id = configured_records[canonical_key][id_field]
        for alias in aliases | {canonical_id}:
            alias_key = voice_identifier_key(alias)
            existing_key = alias_index.get(alias_key)
            if existing_key is not None and existing_key != canonical_key:
                raise RuntimeError(f"Voice alias is ambiguous: {alias}")
            alias_index[alias_key] = canonical_key
    return alias_index


CALLER_VOICE_ALIASES = build_voice_aliases(
    {
        "us-buyer-001": {
            "US buyer 1", "US buyer one", "United States buyer 1",
            "United States buyer one", "buyer 1", "buyer one",
            "comprador Estados Unidos 1", "comprador Estados Unidos uno",
            "comprador 1", "comprador uno",
        },
        "pe-supplier-001": {
            "PE supplier 1", "PE supplier one", "Peru supplier 1",
            "Peru supplier one", "supplier 1", "supplier one",
            "proveedor Peru 1", "proveedor Peru uno",
            "proveedor Peru cero cero uno", "proveedor 1", "proveedor uno",
            "fornecedor Peru 1", "fornecedor Peru um",
        },
        "br-logistics-001": {
            "BR logistics 1", "BR logistics one", "Brazil logistics 1",
            "Brazil logistics one", "logistics 1", "logistics one",
            "Brazil transport partner 1", "Brazil transport partner one",
            "logistica Brasil 1", "logistica Brasil um",
            "parceiro de transporte Brasil 1",
            "parceiro de transporte Brasil um",
        },
    },
    CALLERS,
    "caller_id",
)

LOT_VOICE_ALIASES = build_voice_aliases(
    {
        "mf-204": {
            "204", "lot 204", "lot two zero four", "lot two hundred four",
            "M F two zero four", "em eff two zero four", "lote 204",
            "lote dos cero cuatro", "lote doscientos cuatro",
            "eme efe dos cero cuatro", "lote dois zero quatro",
            "lote duzentos e quatro", "eme efe dois zero quatro",
        },
        "mf-317": {
            "317", "lot 317", "lot three one seven",
            "lot three hundred seventeen", "M F three one seven",
            "em eff three one seven", "lote 317", "lote tres uno siete",
            "lote trescientos diecisiete", "eme efe tres uno siete",
            "lote tres um sete", "lote trezentos e dezessete",
            "eme efe tres um sete",
        },
        "mf-422": {
            "422", "lot 422", "lot four two two",
            "lot four hundred twenty two", "M F four two two",
            "em eff four two two", "lote 422", "lote cuatro dos dos",
            "lote cuatrocientos veintidos", "eme efe cuatro dos dos",
            "lote quatro dois dois", "lote quatrocentos e vinte e dois",
            "eme efe quatro dois dois",
        },
    },
    LOTS,
    "lot_id",
)


def find_caller(caller_id: str) -> dict[str, Any]:
    """Return a configured caller from a canonical ID or approved alias."""
    caller_key = CALLER_VOICE_ALIASES.get(voice_identifier_key(caller_id))
    caller = CALLERS.get(caller_key) if caller_key else None
    if caller is None:
        raise UnknownCallerError(caller_id)
    return caller


def find_lot(lot_id: str) -> dict[str, Any]:
    """Return a configured lot from a canonical ID or approved alias."""
    lot_key = LOT_VOICE_ALIASES.get(voice_identifier_key(lot_id))
    lot = LOTS.get(lot_key) if lot_key else None
    if lot is None:
        raise UnknownLotError(lot_id)
    return lot


def transports_for_lot(
    lot_id: str,
    transporter_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return ordered movements for one lot and optional transporter."""
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


def lots_for_caller(caller: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve lots assigned to a buyer, provider, or transporter."""
    caller_id = caller["caller_id"]
    caller_type = caller["caller_type"]

    if caller_type == "buyer":
        assigned_ids = {
            lot["lot_id"] for lot in LOTS.values() if lot["buyer_id"] == caller_id
        }
    elif caller_type == "supplier":
        assigned_ids = {
            lot["lot_id"] for lot in LOTS.values() if lot["provider_id"] == caller_id
        }
    else:
        assigned_ids = {
            transport["lot_id"]
            for transport in TRANSPORTS.values()
            if transport["transporter_id"] == caller_id
        }

    return sorted(
        (lot for lot in LOTS.values() if lot["lot_id"] in assigned_ids),
        key=lambda lot: lot["lot_id"],
    )


def require_lot_assignment(caller: dict[str, Any], lot: dict[str, Any]) -> None:
    """Prevent callers from retrieving a lot outside their assignments."""
    assigned_ids = {assigned_lot["lot_id"] for assigned_lot in lots_for_caller(caller)}
    if lot["lot_id"] not in assigned_ids:
        raise LotAssignmentError()
