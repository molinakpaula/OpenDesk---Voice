"""Minimal API for the fictional OpenDesk IT support voice agent."""

from fastapi import FastAPI, HTTPException


app = FastAPI(
    title="OpenDesk Voice Support API",
    description="A fictional API for checking IT service outages.",
    version="0.1.0",
)


# For this first milestone, outage information lives in memory. This keeps the
# example simple and avoids connecting to real services or using real data.
OUTAGES = {
    "vpn": {
        "status": "operational",
        "message": "No fictional VPN outage is currently reported.",
    },
    "email": {
        "status": "degraded",
        "message": "The fictional email service is experiencing delivery delays.",
    },
    "identity": {
        "status": "operational",
        "message": "No fictional identity service outage is currently reported.",
    },
}


@app.get("/health")
def get_health() -> dict[str, str]:
    """Confirm that the backend is running and able to answer requests."""
    return {"status": "ok"}


@app.get("/outages/{service}")
def get_outage(service: str) -> dict[str, str]:
    """Return fictional outage information for a supported IT service."""
    normalized_service = service.lower()
    outage = OUTAGES.get(normalized_service)

    if outage is None:
        supported_services = ", ".join(OUTAGES)
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown service '{service}'. "
                f"Supported services: {supported_services}."
            ),
        )

    return {
        "service": normalized_service,
        "status": outage["status"],
        "message": outage["message"],
    }
