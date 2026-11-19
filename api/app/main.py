from fastapi import FastAPI

app = FastAPI(title="luft api")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe: returns 200 as long as the service is up."""
    return {"status": "ok"}
