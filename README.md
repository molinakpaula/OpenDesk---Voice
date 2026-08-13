# OpenDesk Voice

This project is the first backend milestone for a fictional multilingual IT
support voice agent. It provides a small API that reports fictional outage
information for `vpn`, `email`, and `identity`.

It does not connect to ElevenLabs, ServiceNow, OpenAI, or any real company or
employee data.

## Architecture

The planned request flow is:

```text
Caller -> ElevenLabs voice layer -> OpenDesk FastAPI -> fictional service status
```

This repository currently contains only the OpenDesk FastAPI component. A future
voice layer can turn speech into a service name, request an endpoint such as
`/outages/email`, and speak the returned message. No ElevenLabs credentials or
API calls are included in this milestone.

## What is an API endpoint?

An API endpoint is an address that another program can call to request data or
perform an action. For example, a `GET` request to `/outages/vpn` asks this
backend for the fictional status of the VPN service. The backend answers with
JSON, a structured text format that programs can easily read.

## Files

- `main.py` contains the FastAPI application, endpoints, and fictional outage
  data.
- `requirements.txt` lists the Python packages needed to run the backend.
- `.gitignore` prevents the local virtual environment, secret environment
  settings, and generated Python cache files from being committed to Git.
- `tests/test_main.py` checks successful and error responses using Python's
  built-in test tools.

## Set up the backend on Windows

Open PowerShell in this project directory.

Activate the existing virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the required packages if they are not already installed:

```powershell
python -m pip install -r requirements.txt
```

Start the development server:

```powershell
python -m uvicorn main:app --reload
```

In `main:app`, `main` refers to `main.py` and `app` is the FastAPI application
created in that file. The `--reload` option restarts the development server
when the code changes.

## Test the backend

Keep the server running and open these addresses in a browser:

- Health check: <http://127.0.0.1:8000/health>
- VPN outage: <http://127.0.0.1:8000/outages/vpn>
- Email outage: <http://127.0.0.1:8000/outages/email>
- Identity outage: <http://127.0.0.1:8000/outages/identity>
- Unknown service example: <http://127.0.0.1:8000/outages/printer>
- Interactive API documentation: <http://127.0.0.1:8000/docs>

The first four API requests should return JSON successfully. The unknown
service example should return HTTP status `404 Not Found` with a message listing
the supported services.

## Run the automated tests

With the virtual environment activated, run:

```powershell
python -m unittest discover -s tests -v
```

The tests send requests through the FastAPI application without opening a
network port. They verify the health check, every supported service,
case-insensitive service names, and the `404` response for an unknown service.

## Future voice-agent connection

Later, a voice system could convert a caller's speech into text, identify the
requested service, and call an endpoint such as `/outages/email`. This backend
would return outage data, and the voice system could turn that response into a
spoken answer. External speech, ticketing, and AI integrations are intentionally
outside this milestone.
