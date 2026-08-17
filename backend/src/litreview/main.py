from fastapi import FastAPI

from .routers import settings_router

app = FastAPI(title="LitReview backend")
app.include_router(settings_router.router)
