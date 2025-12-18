import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Dict, Optional, Literal

import bcrypt
import jwt
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr

from .config import get_settings
from .db import get_database, serialize_mongo_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class UserInDB(BaseModel):
    id: str
    email: EmailStr
    passwordHash: str
    name: str
    role: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Literal["CAREGIVER", "PATIENT"] | None = None


class RegisterResponse(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginUser(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str


class LoginResponse(BaseModel):
    token: str
    user: LoginUser


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _create_access_token(data: Dict[str, Any]) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_exp_days)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def _get_user_by_email(email: str) -> Optional[UserInDB]:
    db = get_database()
    db_name = db.name
    logger.info(f"[AUTH] Searching for user with email: {email} in database '{db_name}', collection 'User'")
    raw = await db["User"].find_one({"email": email})
    if raw:
        logger.info(f"[AUTH] ✓ Found user: email={email}, role={raw.get('role')}, _id={raw.get('_id')}")
    else:
        logger.warning(f"[AUTH] ✗ User not found with email: {email} in database '{db_name}', collection 'User'")
    serialized = serialize_mongo_document(raw)
    if not serialized:
        return None
    # Some legacy users may not have a role set; default to CAREGIVER to avoid validation failure.
    if not serialized.get("role"):
        logger.warning(f"[AUTH] User {email} is missing role; defaulting to CAREGIVER")
        serialized["role"] = "CAREGIVER"
    return UserInDB(**serialized)


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> Dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = payload.get("id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    db = get_database()
    raw = await db["User"].find_one({"_id": ObjectId(user_id)})
    user = serialize_mongo_document(raw)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_patient(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Dependency that ensures the authenticated user is a PATIENT."""
    if current_user.get("role") != "PATIENT":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patient access required")
    return current_user


async def get_current_caregiver(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Dependency that ensures the authenticated user is a CAREGIVER."""
    if current_user.get("role") != "CAREGIVER":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Caregiver access required")
    return current_user


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest) -> RegisterResponse:
    try:
        db = get_database()
        db_name = db.name
        role = req.role or "CAREGIVER"
        logger.info(f"[AUTH REGISTER] Attempting to register user: email={req.email}, name={req.name}, role={role}")
        logger.info(f"[AUTH REGISTER] Database: '{db_name}', Collection: 'User'")
        
        try:
            existing = await db["User"].find_one({"email": req.email})
        except Exception as e:
            logger.error(f"[AUTH REGISTER] ✗ Database connection error while checking existing user: {type(e).__name__}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Database connection error: {str(e)}"
            )
        
        if existing:
            logger.warning(f"[AUTH REGISTER] ✗ Email already exists: {req.email} in database '{db_name}'")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

        doc: Dict[str, Any] = {
            "email": req.email,
            "passwordHash": _hash_password(req.password),
            "name": req.name,
            "role": role,
            "createdAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc),
        }
        
        try:
            result = await db["User"].insert_one(doc)
            created = await db["User"].find_one({"_id": result.inserted_id})
        except Exception as e:
            logger.error(f"[AUTH REGISTER] ✗ Database error while creating user: {type(e).__name__}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Database error: {str(e)}"
            )
        
        user = serialize_mongo_document(created) or {}
        
        if not user or not user.get("id"):
            logger.error(f"[AUTH REGISTER] ✗ Failed to retrieve created user: email={req.email}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created user"
            )
        
        logger.info(f"[AUTH REGISTER] ✓ User created successfully: email={req.email}, role={role}, id={user.get('id')} in database '{db_name}', collection 'User'")

        return RegisterResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            role=user["role"],
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"[AUTH REGISTER] ✗ Unexpected error during registration: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest) -> LoginResponse:
    logger.info(f"[AUTH LOGIN] Login attempt for email: {req.email}")
    user = await _get_user_by_email(req.email)
    if not user or not _verify_password(req.password, user.passwordHash):
        logger.warning(f"[AUTH LOGIN] ✗ Login failed: Invalid credentials for email={req.email}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    logger.info(f"[AUTH LOGIN] ✓ Login successful: email={req.email}, role={user.role}, id={user.id}")
    token = _create_access_token({"id": user.id, "role": user.role, "email": user.email})
    return LoginResponse(
        token=token,
        user=LoginUser(id=user.id, email=user.email, name=user.name, role=user.role),
    )





