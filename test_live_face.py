"""Manual entry point for live InsightFace hardware validation."""

import asyncio

from app.tools.face_validation import run_live_face_validation


if __name__ == "__main__":
    asyncio.run(run_live_face_validation())
