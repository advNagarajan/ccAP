from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID

from app.core.settings import settings
from app.db.session import get_db
from app.models.db.user import User

# HTTPBearer with auto_error=False to allow dev mode fallback when headers are missing
security_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    # 1. Check if token credentials were provided in Authorization header
    if credentials is not None:
        token = credentials.credentials
        if token.startswith("token-"):
            user_id_str = token.replace("token-", "")
            try:
                user_uuid = UUID(user_id_str)
                user = db.get(User, user_uuid)
                if user:
                    return user
            except ValueError:
                pass
        
        # If token was provided but failed checks, raise 401
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials."
        )

    # 2. If no header was provided, fallback if in DEV_MODE
    if settings.DEV_MODE:
        stmt = select(User).where(User.email == "dev-engineer@sutherland.com")
        dev_user = db.execute(stmt).scalar_one_or_none()
        if not dev_user:
            # Create a default dev user if not exists
            from app.services.security import hash_password
            dev_user = User(
                email="dev-engineer@sutherland.com",
                hashed_password=hash_password("DevPassword123!"),
                role="OWNER"
            )
            db.add(dev_user)
            db.commit()
            db.refresh(dev_user)
        return dev_user
        
    # 3. Raise 401 if header is missing and not in DEV_MODE
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated."
    )
