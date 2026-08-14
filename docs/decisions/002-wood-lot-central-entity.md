# ADR 002: Wood Lot Is the Central Entity

- Status: Accepted
- Date: 2026-08-14

## Context

Drying, procurement, supply, documentation, wood type, destination, and
transport coordination all concern a particular lot of wood.

## Decision

Use `WOOD_LOT` as the central record. Each lot references one buyer, provider,
wood type, and drying status.

## Alternatives considered

- Center the model on an order.
- Store unrelated caller-specific copies of each lot.

## Consequences

- Each role receives a different view of one consistent operational record.
- The model maps naturally to a later relational database.
- Order-level commercial details may require a separate entity in a future
  quotation or invoicing milestone.
