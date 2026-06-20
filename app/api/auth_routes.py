from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.models.db.user import User
from app.schemas.user_schema import UserCreate, UserLogin, UserResponse, TokenResponse
from app.services.security import hash_password, verify_password

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
        hashed_password=hashed
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
