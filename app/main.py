from fastapi import FastAPI
from api.asr_router import router as asr_router

app = FastAPI(title="Voice Transaction ASR Service")

app.include_router(asr_router, prefix="/asr")