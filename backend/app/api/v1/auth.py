from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, session_dep, verify_bootstrap_token
from app.core.config import get_settings
from app.core.security import AdminAuthContext
from app.schemas.auth import (
    AdminUserRead,
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.admin_auth_service import AdminAuthService

router = APIRouter()


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _token_response(pair) -> TokenResponse:
    return TokenResponse(
        access_token=pair.access_token,
        refresh_token=pair.refresh_token,
        expires_in=pair.expires_in,
        user=pair.user,
    )


@router.post("/register", response_model=AdminUserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(session_dep),
):
    service = AdminAuthService(session, get_settings())
    if await service.has_users():
        verify_bootstrap_token(authorization)
    return await service.register(
        email=payload.email,
        username=payload.username,
        password=payload.password,
        display_name=payload.display_name,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(session_dep),
):
    service = AdminAuthService(session, get_settings())
    pair = await service.login(
        account=payload.account,
        password=payload.password,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    return _token_response(pair)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(session_dep),
):
    service = AdminAuthService(session, get_settings())
    pair = await service.refresh(
        refresh_token=payload.refresh_token,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    return _token_response(pair)


@router.get("/me", response_model=AdminUserRead)
async def me(auth: AdminAuthContext = Depends(require_admin)):
    return auth.user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, session: AsyncSession = Depends(session_dep)):
    await AdminAuthService(session, get_settings()).logout(payload.refresh_token)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    auth: AdminAuthContext = Depends(require_admin),
    session: AsyncSession = Depends(session_dep),
):
    await AdminAuthService(session, get_settings()).logout_all(auth.user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    auth: AdminAuthContext = Depends(require_admin),
    session: AsyncSession = Depends(session_dep),
):
    await AdminAuthService(session, get_settings()).change_password(
        user=auth.user,
        old_password=payload.old_password,
        new_password=payload.new_password,
    )
