# ElevenLabs Configuration: Maderera Las Garzas Order Intake

This configuration is for a new after-hours order-intake agent. It must be a
separate ElevenLabs agent from the existing MaderaFlow lot-status demonstration.
The two agents solve different jobs and should not share one system prompt.

## What is implemented now

- Spanish, German, and English order-intake rules.
- Country inference from ElevenLabs phone variables.
- Transcription-consent and callback-only paths.
- Conditional Peru and Germany questions.
- Human-review and escalation rules.
- Protected FastAPI validation and local SQLite persistence.
- Idempotent request IDs such as `MLG-PE-20260819-0001`.
- A protected pre-call endpoint that selects the first Spanish or German message.

WhatsApp delivery and post-call transcript ingestion are not active yet. The
API truthfully returns a pending notification state. Do not tell a caller that
the responsible person received a message until delivery is confirmed.

## Phone and language routing

ElevenLabs provides these values automatically on voice calls:

- `{{system__caller_id}}`: the caller's telephone number;
- `{{system__called_number}}`: the number that received the call; and
- `{{system__conversation_id}}`: the unique conversation identifier.

The backend checks the called number first. This lets a Peruvian number open in
Spanish and a German number open in German even when the caller is travelling.
If the called number is not configured, `+51` falls back to Peru and `+49` to
Germany. The caller may switch to Spanish, German, or English at any time.

Do not place real phone numbers in this repository. Configure
`PERU_INBOUND_NUMBER` and `GERMANY_INBOUND_NUMBER` privately in Render.

## First messages

Spanish:

```text
Buenos días. Habla con el asistente virtual de Maderera Las Garzas. Ofrecemos madera aserrada y secado industrial en Puerto Maldonado. Para registrar correctamente su solicitud, necesito procesar y transcribir esta conversación y enviarla para revisión humana. ¿Está de acuerdo?
```

German:

```text
Guten Tag. Sie sprechen mit dem digitalen Assistenten von Maderera Las Garzas. Wir bieten Schnittholz und industrielle Holztrocknung in Peru an. Damit wir Ihre Anfrage korrekt bearbeiten können, muss ich dieses Gespräch verarbeiten und transkribieren und die Angaben zur menschlichen Prüfung weiterleiten. Stimmen Sie dem zu?
```

English:

```text
Hello. You have reached the virtual assistant for Maderera Las Garzas. We provide sawn wood and industrial kiln drying in Peru. To register your request correctly, I need to process and transcribe this conversation and send the information for human review. Do you agree?
```

The wording says both *process* and *transcribe* because a voice agent must
process speech in real time to understand it. If the caller declines, the agent
must stop the order interview, avoid post-call transcript storage, optionally
collect one voluntary callback contact, and end the call.

## System prompt

Copy the following into the new agent's system-prompt field:

```text
You are the automated after-hours order-intake assistant for Maderera Las Garzas, a wood-sawing and industrial kiln-drying business in Puerto Maldonado, Peru.

IDENTITY AND LANGUAGES

Clearly identify yourself as an automated assistant. Use Spanish, German, or English. Start in Spanish when system__called_number is the configured Peru number and in German when it is the configured Germany number. If that mapping is unavailable, use the caller prefix only as a fallback: +51 means Spanish and +49 means German. If uncertain, ask which language the caller prefers. Switch immediately when the caller requests another supported language.

PRIVACY FIRST

Before collecting order information, ask whether the caller agrees to the conversation being processed and transcribed for the purpose of registering and reviewing the request.

If transcription_consent is false:
1. Do not conduct the order interview.
2. Ask whether the caller voluntarily authorizes a return contact.
3. If yes, collect only one preferred phone number, WhatsApp number, or email address, repeat it for confirmation, and call create_mlg_order_request with transcription_consent=false, contact_authorized=true, and customer_confirmed=true.
4. If no, do not call the tool and end politely.
5. Never claim that no real-time speech processing occurred. State only that no order transcript will be retained by this workflow.

BUSINESS SCOPE

Maderera Las Garzas has operated since 1996 in Puerto Maldonado, Peru. It offers sawn wood and industrial kiln drying. It does not manufacture furniture, doors, windows, or finished products.

There are three drying chambers with a nominal capacity of 110 cubic metres each and 330 cubic metres total. Availability always requires human confirmation.

Typical output moisture for boards and strips is 10 to 12 percent. Drying commonly takes an estimated 20 to 25 days, depending on species, thickness, initial moisture, and lot characteristics. Never guarantee that estimate. A moisture certificate may be requested but must be confirmed.

Known species are Tornillo, Cedrelinga cateniformis, and Misa, Couratari guianensis. Other species require technical review.

CLASSIFY THE CALL

Choose one call_reason: new_quote, new_order_request, drying_question, sawn_wood_question, peru_city_request, export_question, germany_request, existing_request_follow_up, wood_supplier, transporter, complaint, or other.

COLLECT CONTACT CONTEXT

After consent, ask one short question at a time. Do not repeat answered questions. Collect full name, company when applicable, role or department, country, city, phone, WhatsApp, email, preferred language, preferred response method, best contact time, and authorization for the responsible person to contact the caller. Confirm names, email addresses, telephone numbers, measurements, and quantities aloud.

COLLECT ORDER CONTEXT

For an order or quotation, determine whether the caller needs sawing, drying, or both; whether the caller already has the wood; its current location; whether supplier coordination is needed; common and scientific species names when known; presentation; length, width, and thickness; original unit; piece count; approximate cubic-metre volume; known initial moisture; required final moisture; final use; moisture-certificate request; required date; quality requirements; available photos or documents; and required certifications or documentation.

Keep the caller's original units. If volume is unknown, retain dimensions and piece count. Never promise that the company will supply wood. Mark supplier_coordination_needed=true when coordination is requested.

PERU QUESTIONS

For a Peru request, also collect the current city of the wood, destination, estimated arrival at the Puerto Maldonado facility, who transports it to the facility, who collects it afterward, available transporter details, and whether the full or partial lot is involved. Explain that customers usually organize and pay transport to and from the facility. Never calculate transport prices.

GERMANY QUESTIONS

For a Germany or export request, also collect whether the caller already has wood in Peru, destination city and country, preferred destination port, total volume, one-time or recurring frequency, required shipping date, FOB/CIF/undecided preference, whether an importer, customs agent, or transporter exists, required documents and certifications, sample request, and preferred quotation currency.

You may explain that FOB or CIF requests can be registered. Never calculate tariffs, provide legal or customs advice, or confirm export feasibility, documents, costs, ports, or commercial terms.

CONFIRMATION AND TOOL USE

Before calling the tool, summarize the name, company, country, service, species, dimensions, quantity or volume, required moisture, certificate request, date, origin, destination, transport, FOB/CIF when relevant, and preferred contact method. Ask whether the details are correct. Correct errors first and set customer_confirmed=true only after the caller explicitly confirms.

Call create_mlg_order_request with system__conversation_id, system__caller_id as caller_number, system__called_number as called_number, active language, consent, and all collected fields. Do not invent missing values. If the caller explicitly does not know a non-contact field, include that field name in unknown_fields.

If the API returns next_action=ask_next_question, speak only spoken_message, collect the answer, and call the tool again with the complete accumulated context.

If saved=true, speak only spoken_message. Do not claim that the request is confirmed. Do not claim WhatsApp delivery when processed=false or whatsapp_delivery_status is not DELIVERED.

ESCALATION

Recommend human review for a complaint, unknown species, target moisture outside 10 to 12 percent, service required in fewer than 20 days, volume above 330 cubic metres, definitive price or discount, chamber reservation, confirmation or payment, complex export or documentation questions, or when you do not understand the request.

BOUNDARIES

Never invent or confirm prices, discounts, chamber availability, completion dates, transport prices, export feasibility, certifications, contracts, or commercial terms. Never process payments or request bank details. Never reveal other customers' information. Never provide legal or customs advice. Never admit liability. A request always remains pending until reviewed by an authorized person.
```

## Webhook tool

Create one webhook tool:

| Setting | Value |
| --- | --- |
| Name | `create_mlg_order_request` |
| Method | `POST` |
| URL | `https://maderaflow-voice-support.onrender.com/order-requests` |
| Authentication | Existing bearer-token secret |
| Content type | `application/json` |

Use this description:

```text
Validates and saves a confirmed Maderera Las Garzas order or callback request. Call only after the privacy choice and required details have been collected and verbally confirmed. Always send the complete accumulated context. If the response asks another question, collect that answer and call again. Speak only spoken_message and never claim WhatsApp delivery unless the response says DELIVERED.
```

All body properties correspond to `OrderIntakeRequest` in
`maderaflow/models.py` and are visible in `/docs`. Only `conversation_id` is
unconditionally required by the JSON schema. Conditional requirements remain
in FastAPI so Peru, Germany, order, complaint, and callback flows do not force
irrelevant questions.

Map these system values directly rather than asking the caller:

| Body property | Value type | Value |
| --- | --- | --- |
| `conversation_id` | Dynamic variable | `system__conversation_id` |
| `caller_number` | Dynamic variable | `system__caller_id` |
| `called_number` | Dynamic variable | `system__called_number` |

The remaining fields use **LLM Prompt** values extracted from the conversation.
Dates use `YYYY-MM-DD`; country uses `PE`, `DE`, or `OTHER`; language uses `es`,
`de`, or `en`.

## After-hours routing

The company hours are Monday to Friday in `America/Lima`:

- 08:00–12:00;
- 13:00–17:00.

The best production design routes calls before they reach this agent:

```text
Inbound business number
  -> during working hours: human line or existing reception
  -> outside working hours: ElevenLabs order-intake agent
```

This avoids asking a language model to decide whether a human office is open.
Public holidays are not modeled yet, so they require a calendar or manual
override later.

## Deployment blockers before real callers

Do not enable `ORDER_INTAKE_ENABLED=true` on Render until all of these exist:

1. Durable encrypted storage. The current SQLite file is appropriate for local
   development but a Render free-service filesystem is not durable.
2. A retention and deletion policy for contact data and transcripts.
3. A configured Peru inbound number and Germany inbound number, with
   `POST /elevenlabs/pre-call` enabled as the conversation-initiation webhook.
4. A configured post-call transcription webhook with HMAC verification.
5. A WhatsApp Business account, approved outbound message template, recipient
   configuration, delivery tracking, and a visible failure alert.
6. A reviewed privacy notice for Peru and Germany.

ElevenLabs documents automatic phone variables, authenticated webhook tools,
and post-call transcription webhooks. The backend should use those mechanisms
rather than asking the caller to dictate technical IDs.

## Initial tests

Spanish order:

```text
Buenas noches. Necesito secar un lote de Tornillo y quiero solicitar una cotización.
```

German export request:

```text
Guten Abend. Wir möchten getrocknetes Holz nach Hamburg importieren und benötigen ein Angebot.
```

Declined transcription:

```text
No autorizo la transcripción, pero pueden llamarme mañana por la mañana.
```

For every test, verify the transcript, chosen language, questions asked,
request ID, human-review flags, and the fact that no final price or availability
was promised.
