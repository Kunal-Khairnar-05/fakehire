"""Route layer: HTTP only. Parse the request, call the service, map errors to status codes."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from ..core.config import settings
from ..deps import get_auth_service, get_current_user
from ..models import User
from ..schemas import RegisterIn, TokenOut, UserOut
from ..services.auth_service import AuthService, EmailAlreadyRegistered, InvalidCredentials

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, auth: AuthService = Depends(get_auth_service)):
    try:
        return auth.register(body.email, body.password)
    except EmailAlreadyRegistered:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), auth: AuthService = Depends(get_auth_service)):
    # OAuth2 standard form fields are "username" and "password"; our username is the email.
    try:
        token = auth.login(form.username, form.password)
    except InvalidCredentials:
        # Same message for "no such email" and "wrong password": don't reveal which accounts exist
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password",
                            headers={"WWW-Authenticate": "Bearer"})
    return TokenOut(access_token=token, expires_in=settings.jwt_expire_minutes * 60)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
