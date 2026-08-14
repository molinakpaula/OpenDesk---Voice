# ADR 003: Transport Movements Are Separate from Lots

- Status: Accepted
- Date: 2026-08-14

## Context

A wood lot can move from a provider to a drying facility and later from that
facility to a buyer. One `transporter_id` field on the lot cannot represent
multiple movements cleanly.

## Decision

Represent transport as a separate entity with `lot_id`, `transporter_id`,
sequence, origin, destination, and status.

## Alternatives considered

- Put one transporter directly on `WOOD_LOT`.
- Store a free-form list of transport details inside the lot.

## Consequences

- One lot supports any number of ordered movements.
- Transport assignments can be filtered independently from buyer and provider
  assignments.
- Selecting the current movement requires an explicit rule; the demonstration
  uses the first incomplete movement in sequence order.
