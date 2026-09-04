from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import hashlib
import hmac
import binascii
import os
import re
from sqlalchemy import func
from sqlalchemy.orm import Session
from bebcare.config.settings import settings
from bebcare.models.user import User

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

# Google-style format standards
# Email: local part starts/ends alphanumeric, separators (._%+-) single only;
# domain labels start/end alphanumeric (hyphen allowed inside), at least two labels.
GOOGLE_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9]+(?:[._%+-][A-Za-z0-9]+)*"
    r"@[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*(?:\.[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)+$"
)
# Username: starts with a letter, ends alphanumeric; only letters, digits,
# dots and underscores allowed, no consecutive separators.
GOOGLE_USERNAME_RE = re.compile(r"^[A-Za-z](?:[A-Za-z0-9]*(?:[._][A-Za-z0-9]+)*)$")


def is_valid_email(email: str) -> bool:
    return bool(email) and bool(GOOGLE_EMAIL_RE.fullmatch(email))


def is_valid_username(username: str) -> bool:
    return bool(username) and bool(GOOGLE_USERNAME_RE.fullmatch(username))


def looks_like_email(identifier: str) -> bool:
    return "@" in identifier


def hash_password(password: str) -> str:
    salt = hashlib.sha256(os.urandom(60)).hexdigest().encode('ascii')
    pwdhash = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'), salt, 100000)
    pwdhash = binascii.hexlify(pwdhash)
    return (salt + pwdhash).decode('ascii')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    salt = hashed_password[:64]
    stored_password = hashed_password[64:]
    pwdhash = hashlib.pbkdf2_hmac('sha512', plain_password.encode('utf-8'), salt.encode('ascii'), 100000)
    pwdhash = binascii.hexlify(pwdhash).decode('ascii')
    return hmac.compare_digest(pwdhash, stored_password)

def get_password_hash(password: str) -> str:
    return hash_password(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire, "type": TOKEN_TYPE_ACCESS})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire, "type": TOKEN_TYPE_REFRESH})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def get_user(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(func.lower(User.email) == email.lower()).first()


def get_user_by_identifier(db: Session, identifier: str) -> Optional[User]:
    if looks_like_email(identifier):
        return get_user_by_email(db, identifier)
    return get_user(db, identifier)


def authenticate_user(db: Session, identifier: str, password: str) -> Optional[User]:
    user = get_user_by_identifier(db, identifier)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user
