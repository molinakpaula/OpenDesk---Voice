# MaderaFlow Demo Video Script

This script produces a concise reviewer-facing demonstration of the MaderaFlow
voice agent. Aim for 90–120 seconds after trimming loading time and long pauses.
All records shown are sample data. Do not show real customer or operational
information.

## Before recording

- Use a 16:9 screen recording at 1080p if available.
- Open the GitHub README and ElevenLabs talk-to page in separate tabs.
- Wake the Render health endpoint before recording.
- Publish the latest ElevenLabs prompt and webhook configuration.
- Use headphones to avoid audio feedback.
- Hide bookmarks, email addresses, API keys, secrets, authorization headers,
  and dashboard configuration.
- Start a fresh conversation for every language.

## Scene 1 — Architecture, 10–15 seconds

Show the README architecture and relationship diagrams.

```text
MaderaFlow demonstrates multilingual voice support for wood drying and
cross-border logistics. ElevenLabs handles the conversation and voice, while a
FastAPI backend controls caller assignments, role-specific information, and
sample operational records.
```

## Scene 2 — Caller-ID-first lookup, 20–25 seconds

Start an English conversation and say:

```text
I am US buyer one.
```

The agent should call the backend immediately, identify the buyer profile, list
the assigned three-digit lot numbers, and ask which lot is needed. Reply:

```text
Two zero four.
```

The response should include drying status, latest recorded moisture, target
moisture, estimated completion, and shipment readiness. Explain that the caller
did not need to state their role or intent; the backend inferred both.

## Scene 3 — Spanish provider, 20–25 seconds

Start a new conversation and say:

```text
Soy proveedor Perú uno. Necesito revisar el lote trescientos diecisiete.
```

The response should switch to Spanish, confirm receipt, report pending provider
documentation, and state the required action. It should not reveal buyer-only
moisture or shipment details.

## Scene 4 — Portuguese transport partner, 20–25 seconds

Start a new conversation and say:

```text
Sou logística Brasil um. O lote quatrocentos e vinte e dois pode ser coletado?
```

The response should include only the assigned transport movement, collection
readiness, destination, and scheduling status. It must not expose buyer,
procurement, pricing, moisture, or estimated-completion information.

## Scene 5 — Data model and close, 15–20 seconds

Return to the relationship diagram.

```text
Wood lot is the central record. Each lot references its buyer, provider, wood
type, and drying status. Transport is separate so one lot can have several
movements, such as inbound delivery and outbound shipment. The result is a
contextual assistant grounded in business relationships rather than a generic
voice receptionist.
```

When sharing the video, include the GitHub repository, ElevenLabs agent, and
live API documentation links, plus a note that the demonstration uses sample
data and is not connected to live customers.
