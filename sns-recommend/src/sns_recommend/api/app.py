from __future__ import annotations

from fastapi import FastAPI

from sns_recommend.api.routers import feeds, health, metrics


def create_app() -> FastAPI:
    app = FastAPI(title="SNS Recommend", version="0.1.0")
    app.include_router(health.router)
    for router in (feeds.router, metrics.router):
        app.include_router(router, prefix="/internal")
    return app


app = create_app()
