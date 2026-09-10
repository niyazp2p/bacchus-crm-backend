from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate, UserPasswordChange
from app.dependencies.auth import get_current_active_user

router = APIRouter(prefix="/profile", tags=["Profile"])

@router.get("/me", response_model=UserResponse)
async def fetch_my_profile(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return current_user

@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    payload: UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if payload.name is not None:
        current_user.name = payload.name
    if payload.territory is not None:
        current_user.territory = payload.territory

    await db.flush()
    await db.refresh(current_user)
    return current_user

@router.post("/me/change-password")
async def rotate_password(
    payload: UserPasswordChange,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is not correct.",
        )

    current_user.password_hash = get_password_hash(payload.new_password)
    await db.flush()
    return {"message": "Password updated successfully."}