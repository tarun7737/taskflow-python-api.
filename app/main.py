from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import create_db_tables
from app.routes import router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    create_db_tables()
    yield


app = FastAPI(title="TaskFlow API", lifespan=lifespan)
app.include_router(router)
