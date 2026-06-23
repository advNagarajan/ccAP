from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID

from app.db.session import get_db
from app.models.db.user import User
from app.schemas.user_schema import UserCreate, UserLogin, UserResponse, TokenResponse, UserRoleUpdate
from app.services.security import hash_password, verify_password
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=201)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    # Check if email already exists
    stmt = select(User).where(User.email == payload.email)
    existing_user = db.execute(stmt).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists."
        )

    # Hash the password
    hashed = hash_password(payload.password)

    # Create user
    new_user = User(
        email=payload.email,
        hashed_password=hashed,
        role="USER"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/login", response_model=TokenResponse)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    stmt = select(User).where(User.email == payload.email)
    user = db.execute(stmt).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    # Generate a simple bearer token which is the string representation of user_id
    token = f"token-{user.user_id}"

    return TokenResponse(
        access_token=token,
        user=user
    )


@router.get("/users", response_model=list[UserResponse])
def get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ("ADMIN", "OWNER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin or Owner permissions required."
        )
    stmt = select(User).order_by(User.created_at.desc())
    result = db.execute(stmt)
    return result.scalars().all()


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ("ADMIN", "OWNER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin or Owner permissions required."
        )

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    if user.role == "OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot delete the Owner account."
        )

    db.delete(user)
    db.commit()
    return


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: UUID,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ("ADMIN", "OWNER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin or Owner permissions required."
        )

    target_role = payload.role.upper()
    if target_role not in ("ADMIN", "USER"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'ADMIN' or 'USER'."
        )

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    if user.role == "OWNER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot modify the Owner's role."
        )

    user.role = target_role
    db.commit()
    db.refresh(user)
    return user

