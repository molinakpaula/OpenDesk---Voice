# MaderaFlow Demo Video Script

This script produces a concise reviewer-facing demonstration of the fictional
MaderaFlow voice agent. Aim for 90–120 seconds after trimming loading time and
long pauses.

Every person, company, lot, measurement, and operational record shown in the
video is fictional.

## Before recording

- Use a 16:9 screen recording at 1080p if available.
- Open the public GitHub README and the ElevenLabs talk-to page in separate tabs.
- Confirm the Render health endpoint is awake before recording.
- Publish the latest ElevenLabs prompt and webhook configuration.
- Use headphones to prevent the agent's voice from feeding back into the
  microphone.
- Hide browser bookmarks, email addresses, API keys, secrets, authorization
  headers, and dashboard configuration.
- Start a fresh conversation for every language.

## Scene 1 — Context, 10–15 seconds

Show the top of the GitHub README and its architecture diagram.

Narration:

```text
MaderaFlow is a fictional multilingual voice-support prototype for wood drying
and cross-border logistics. ElevenLabs handles the conversation and voice,
while a FastAPI backend returns fictional, role-specific operational facts.
```

## Scene 2 — Spanish supplier, 25–30 seconds

Start a new voice conversation and say:

```text
Soy proveedor Perú uno. Quiero revisar la documentación del lote trescientos diecisiete.
```

Keep the agent's response in the recording. It should switch to Spanish,
confirm that the lot was received, report pending supplier documentation, and
say that the missing origin document must be submitted.

Optional narration after the response:

```text
The supplier receives documentation and action information, not buyer-only
moisture or shipment details.
```

## Scene 3 — English buyer, 25–30 seconds

Start a new conversation and say:

```text
I am US buyer one. What is the status of lot two hundred four?
```

The numeric phrase `US buyer 1` and the written lot ID `MF-204` are also valid
after backend version 0.5.0 is deployed.

Keep the response showing drying status, latest recorded moisture, target
moisture, estimated completion, and shipment readiness.

Optional narration:

```text
The buyer receives the operational status, but the estimated date is never
presented as a guarantee and the measurement is described as recorded, not live.
```

## Scene 4 — Portuguese transport partner, 25–30 seconds

Start a new conversation and say:

```text
Sou logística Brasil um. O transporte do lote quatrocentos e vinte e dois pode ser agendado?
```

Keep the response showing collection readiness, destination, and whether
transport can be scheduled. It must not expose buyer, procurement, pricing,
moisture, or estimated-completion information.

## Scene 5 — Close, 10–15 seconds

Return to the README architecture diagram or automated-test badge.

Narration:

```text
The prototype demonstrates that a natural voice becomes useful when it is
combined with business context, multilingual retrieval, privacy boundaries,
safe escalation, and a reliable backend tool. All demonstration data is
fictional, and real transfers, tickets, authentication, and customer data are
outside this milestone.
```

## What to include with the video

When sharing it, include:

- the GitHub repository link;
- the ElevenLabs talk-to link;
- the live FastAPI documentation link;
- a clear statement that all demonstration data is fictional; and
- an invitation for feedback about multilingual voice workflows and human
  handoff design.
