from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import List, Optional
from bebcare.database import get_db
from bebcare.models.user import User
from bebcare.services.auth_service import (
    TOKEN_TYPE_ACCESS,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    get_user,
)
from bebcare.services.auth_dependency import get_current_admin_user, get_current_active_user
from bebcare.services.auth_scheme import oauth2_scheme
from bebcare.schemas.auth import Token, UserCreate, UserUpdate, UserResponse, RefreshTokenRequest
from bebcare.config.settings import settings
from bebcare.services.credit_grant_service import (
    ensure_signup_trial,
    remaining_credits,
)
from bebcare.billing.packs import is_billing_enabled
from bebcare.models.image_provider import ImageProviderConfig

router = APIRouter(prefix="/auth", tags=["auth"])


def _has_system_image_provider(db: Session) -> bool:
    return (
        db.query(ImageProviderConfig.id)
        .filter(
            ImageProviderConfig.is_system == True,  # noqa: E712
            ImageProviderConfig.is_active == True,  # noqa: E712
        )
        .first()
        is not None
    )


def _to_user_response(db: Session, user: User) -> UserResponse:
    return UserResponse(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        onboarding_completed_at=user.onboarding_completed_at,
        image_credits_remaining=remaining_credits(db, user.user_id),
        has_system_image_provider=_has_system_image_provider(db),
        billing_contact=settings.billing_contact or settings.admin_email,
        billing_enabled=is_billing_enabled(),
    )

@router.post("/login/")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.user_id, "is_admin": user.is_admin},
        expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(
        data={"sub": user.username, "user_id": user.user_id}
    )
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/register/", status_code=status.HTTP_201_CREATED)
def register_user(
    user: UserCreate,
    db: Session = Depends(get_db),
):
    if not settings.allow_public_signup:
        raise HTTPException(status_code=403, detail="Public signup is disabled")

    if not user.email or not user.email.strip():
        raise HTTPException(status_code=400, detail="Email is required")

    db_user = get_user(db, user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")

    db_email = db.query(User).filter(User.email == user.email.strip()).first()
    if db_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    new_user = User(
        username=user.username.strip(),
        email=user.email.strip(),
        hashed_password=hashed_password,
        is_admin=False,
    )

    db.add(new_user)
    db.flush()
    ensure_signup_trial(db, new_user.user_id)
    db.commit()
    db.refresh(new_user)

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": new_user.username, "user_id": new_user.user_id, "is_admin": new_user.is_admin},
        expires_delta=access_token_expires,
    )
    refresh_token = create_refresh_token(
        data={"sub": new_user.username, "user_id": new_user.user_id}
    )
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/refresh/")
def refresh_access_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    refresh_token = request.refresh_token
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(refresh_token, settings.secret_key, algorithms=[settings.algorithm])
        # Reject access tokens; allow legacy tokens that omit type
        if payload.get("type") == TOKEN_TYPE_ACCESS:
            raise credentials_exception
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = get_user(db, username=username)
    if user is None:
        raise credentials_exception
    
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.user_id, "is_admin": user.is_admin},
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return _to_user_response(db, current_user)


@router.post("/me/onboarding-complete")
def complete_onboarding(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    current_user.onboarding_completed_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    return {"status": "ok", "onboarding_completed_at": current_user.onboarding_completed_at}

@router.get("/users", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [_to_user_response(db, u) for u in users]

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    db_user = get_user(db, user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    if user.email:
        db_email = db.query(User).filter(User.email == user.email).first()
        if db_email:
            raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        is_admin=user.is_admin
    )
    
    db.add(new_user)
    db.flush()
    ensure_signup_trial(db, new_user.user_id)
    db.commit()
    db.refresh(new_user)
    
    return _to_user_response(db, new_user)

@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_update.email is not None:
        existing_email = db.query(User).filter(
            User.email == user_update.email,
            User.user_id != user_id
        ).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already registered")
        user.email = user_update.email
    
    if user_update.password is not None:
        user.hashed_password = get_password_hash(user_update.password)
    
    if user_update.is_active is not None:
        user.is_active = user_update.is_active
    
    if user_update.is_admin is not None:
        user.is_admin = user_update.is_admin
    
    db.commit()
    db.refresh(user)
    
    return _to_user_response(db, user)

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    if user_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()
    
    return None