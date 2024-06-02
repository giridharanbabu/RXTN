from fastapi import HTTPException
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt, JWTError
from typing import Union, Any
from pkg.config.config import settings
from pkg.database.database import database
user_collection = database.get_collection('users')

pwd_context = CryptContext(["sha256_crypt"])
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str):
    return pwd_context.verify(password, hashed_password)


def create_access_token(subject: Union[str, Any], name: str, role: str, expires_delta: int = None) -> str:
    if expires_delta is not None:
        expires_delta = datetime.utcnow() + expires_delta
    else:
        expires_delta = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expires_delta, "email": str(subject), "name": name, "role": role}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET, settings.ALGORITHM)
    return encoded_jwt


def generate_otp():
    import random
    otp = ''.join(random.choices('0123456789', k=6))
    expiration_time = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    reset_data = {
        "reset_otp": otp,
        "reset_otp_exp": expiration_time
    }
    return reset_data


def create_refresh_token(subject: Union[str, Any], name: str, role: str, expires_delta: int = None) -> str:
    if expires_delta is not None:
        expires_delta = datetime.utcnow() + expires_delta
    else:
        expires_delta = datetime.utcnow() + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)

    to_encode = {"exp": expires_delta, "email": str(subject), "name": name, "role": role}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET, settings.ALGORITHM)
    return encoded_jwt


def validate_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET, algorithms=["HS256"])
        # Check if the token has expired
        if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
            raise jwt.ExpiredSignatureError("Token has expired")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token")
