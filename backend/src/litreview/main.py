from fastapi import FastAPI

from .routers import analysis_router, library_router, search_router, settings_router

app = FastAPI(title="LitReview backend")
app.include_router(settings_router.router)
app.include_router(search_router.router)
app.include_router(library_router.router)
app.include_router(analysis_router.router)
