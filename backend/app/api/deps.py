from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db


async def verify_api_key(x_api_key: Annotated[Optional[str], Header()] = None) -> None:
    settings = get_settings()
    if settings.app_env == "development" and not x_api_key:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


DbSession = Annotated[AsyncSession, Depends(get_db)]
