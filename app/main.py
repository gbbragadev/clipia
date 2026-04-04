from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

app = FastAPI(title="ClipIA API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restringir para dominio do frontend em producao
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
