from fastapi import FastAPI

from .api import files
from .db import Base, engine

Base.metadata.create_all(engine)
app = FastAPI(title="Geospatial File Measurement API", version="1.0.0")
app.include_router(files.router)


@app.get("/health")
def health():
    return {"status": "ok"}