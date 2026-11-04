import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


async def user_from_credentials(creds: HTTPAuthorizationCredentials | None, db: AsyncSession) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise unauthorized
    try:
        payload = decode_token(creds.credentials)
    except jwt.PyJWTError:
        raise unauthorized
    if payload.get("type") != "access":
        raise unauthorized
    user = await db.get(User, int(payload["sub"]))
    if user is None:
        raise unauthorized
    return user


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await user_from_credentials(creds, db)
