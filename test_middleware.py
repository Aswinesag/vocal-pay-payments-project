"""
Integration test for RequestLoggingMiddleware

Run:
    python test_middleware.py
"""

from fastapi import FastAPI
import uvicorn

from app.core.logging_middleware import RequestLoggingMiddleware

app = FastAPI(title="Middleware Test")

# Register middleware
app.add_middleware(RequestLoggingMiddleware)


@app.get("/health")
async def health():

    return {
        "status": "healthy",
        "message": "Middleware is working."
    }


@app.get("/slow")
async def slow():

    import asyncio

    await asyncio.sleep(2)

    return {
        "status": "completed"
    }


@app.get("/error")
async def error():

    raise RuntimeError("Middleware exception test")


if __name__ == "__main__":

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )