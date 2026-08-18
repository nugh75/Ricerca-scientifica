from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import analysis_router, export_router, library_router, search_router, settings_router

app = FastAPI(title="LitReview backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Identity probe: lets a second launch tell our backend from a stranger."""
    return {"app": "litreview"}


app.include_router(settings_router.router)
app.include_router(search_router.router)
app.include_router(library_router.router)
app.include_router(analysis_router.router)
app.include_router(export_router.router)
