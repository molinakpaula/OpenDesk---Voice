# MaderaFlow Voice Support API

MaderaFlow is a fictional wood-drying and cross-border logistics coordination
company headquartered in Puerto Maldonado, Peru. In this fictional scenario, it
serves wood suppliers, manufacturers, and logistics partners in Peru, Brazil,
and the United States.

This repository contains a small multilingual FastAPI backend for looking up
fictional wood-lot status. Every organization, caller, and lot in the project is
fictional. The project contains no real customer, employee, shipment, or sensor
data.

## Why caller context matters

The same lot should not produce one generic answer for everyone. The API uses a
fictional caller profile to select the caller's language and reveal only the
information relevant to that role:

- A **buyer** hears drying progress, the latest recorded moisture value, the
  target moisture, the estimated completion date, and shipment readiness.
- A **supplier** hears whether the lot was received, its documentation status,
  and whether supplier action is required.
- A **transport partner** hears collection readiness, the destination, and
  whether transport can be scheduled. Buyer-specific and pricing information is
  not returned.

This context filtering makes the backend useful for a specialized support agent
instead of a generic voice assistant.

## Supported languages

The caller profile determines the language of `spoken_message`:

| Code | Language |
| --- | --- |
| `en` | English |
| `es` | Spanish |
| `pt` | Portuguese |

## Fictional caller profiles

| Caller ID | Role | Location | Language | Priority |
| --- | --- | --- | --- | --- |
| `US-BUYER-001` | Buyer | Houston, United States | English | High |
| `PE-SUPPLIER-001` | Supplier | Puerto Maldonado, Peru | Spanish | Normal |
| `BR-LOGISTICS-001` | Transport partner | Rio Branco, Brazil | Portuguese | Normal |

Caller and lot IDs are case-insensitive, so `mf-204` and `MF-204` refer to the
same fictional lot.

## API endpoints

An API endpoint is an address where another program asks the backend for
information. A `GET` request retrieves information without changing it.

- `GET /health` confirms that the backend can respond.
- `GET /organization` returns the fictional organization and languages.
- `GET /callers/{caller_id}` returns one fictional caller profile.
- `GET /lots/{lot_id}?caller_id={caller_id}` returns a role- and
  language-specific lot response.
- `POST /support-requests` accepts structured context from a future voice layer
  and handles lot status, documentation, and transport-readiness intents.
- `GET /docs` opens FastAPI's interactive API documentation.

Unknown caller and lot IDs return `404 Not Found`, meaning the requested
fictional record does not exist.

## Example requests

After starting the server, these examples ask about the same lot from three
different perspectives.

English buyer response:

```text
http://127.0.0.1:8000/lots/MF-204?caller_id=US-BUYER-001
```

Spanish supplier response:

```text
http://127.0.0.1:8000/lots/MF-204?caller_id=PE-SUPPLIER-001
```

Portuguese transport-partner response:

```text
http://127.0.0.1:8000/lots/MF-204?caller_id=BR-LOGISTICS-001
```

The structured fields and `spoken_message` change because each caller has a
different role and preferred language.

## Voice-ready support requests

The future voice layer can send one JSON request after identifying the caller,
lot, and intent:

```json
{
  "caller_id": "PE-SUPPLIER-001",
  "lot_id": "MF-317",
  "intent": "check_documentation"
}
```

Supported intents are:

- `check_lot_status` for a buyer;
- `check_documentation` for a supplier; and
- `check_transport_readiness` for a transport partner.

The role restriction is intentional. A transport partner cannot use this
endpoint to request buyer-only status details. Spoken messages translate
internal operational codes into natural English, Spanish, or Portuguese, while
structured fields retain stable codes for software integrations.

## Human support and after-hours routing

Fictional support hours are Monday through Friday, 08:00–18:00 in the
`America/Lima` timezone. Holidays are not modeled yet. These hours are editable
in `config/maderaflow.json`.

If an intent is unsupported or inappropriate for the caller's role:

- during working hours, the response recommends a human handoff;
- after working hours, the response recommends opening a support ticket.

`ticket_created` remains `false`. This milestone recommends the next action but
does not create a real ticket or connect to an external ticketing system.

## Safety boundaries

The API uses fixed fictional records. It does not:

- invent or claim to retrieve live moisture measurements;
- guarantee an estimated completion date;
- provide legal or customs advice;
- admit liability; or
- expose information unrelated to the caller's role.

For a high-priority buyer, `escalation_recommended` becomes `true` when a lot is
delayed, is not transport-ready near its required date, or has a recorded
quality problem. This is a support-routing signal, not an admission of liability.

## Project files

- `main.py` defines the FastAPI application, fictional organization, caller and
  lot configuration loading, validation, context filtering, multilingual
  messages, and API endpoints.
- `config/maderaflow.json` contains editable fictional organization, caller,
  lot, escalation, and support-hours data. Keeping these facts outside Python
  makes the business context configurable without changing application logic.
- `tests/test_main.py` sends automated requests through the application and
  checks successful responses, errors, language selection, role-specific
  content, escalation, and confidentiality boundaries.
- `requirements.txt` pins FastAPI, Uvicorn, and timezone data needed to reproduce
  Lima working-hours checks consistently across platforms.
- `.gitignore` prevents virtual environments, environment secrets, editor
  settings, and generated Python cache files from being committed.

## Set up on Windows

Open PowerShell in the project directory and activate the existing virtual
environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the pinned requirements if needed:

```powershell
python -m pip install -r requirements.txt
```

No database, API key, or external account is required.

## Change fictional business data

Edit `config/maderaflow.json` to change fictional caller profiles, lot facts,
enabled escalation triggers, or support hours. Restart the development server
after saving the file. On startup, `main.py` checks that required sections exist,
IDs match their configuration keys, and every caller uses a supported role and
language.

Translations remain in `main.py`. This keeps operational wording and role-based
privacy behavior covered by automated tests. Do not put secrets or real
customer, shipment, employee, or sensor data in the configuration file.

## Start and try the backend

Start the development server:

```powershell
python -m uvicorn main:app --reload
```

In `main:app`, `main` means `main.py`, and `app` is the FastAPI application
inside that file. Visit <http://127.0.0.1:8000/docs> to try each endpoint in a
browser.

## Run the automated tests

```powershell
python -m unittest discover -s tests -v
```

The tests use Python's built-in testing tools, so no extra test package is
required.

## Future ElevenLabs integration

ElevenLabs is intentionally not connected in this milestone. A future voice
layer could follow this flow:

```text
Caller speech
    -> ElevenLabs voice layer
    -> caller and lot IDs supplied to MaderaFlow FastAPI
    -> context-aware spoken_message
    -> ElevenLabs speech response
```

The API already returns a `spoken_message` in the fictional caller's preferred
language. A future integration can speak that message while keeping business
rules, role filtering, and fictional lot context inside this backend. Twilio,
Supabase, authentication, and real customer data are also outside this
milestone.
