from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class AdminUserRead(BaseModel):
    id: int
    email: str
    username: str
    display_name: str | None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str = Field(min_length=10)
    display_name: str | None = None

    @field_validator("email", "username")
    @classmethod
    def normalize_account_field(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise ValueError("Field cannot be empty")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        value = value.strip()
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError("Password must contain letters and numbers")
        return value


class LoginRequest(BaseModel):
    account: str
    password: str

    @field_validator("account")
    @classmethod
    def normalize_account(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise ValueError("Account cannot be empty")
        return value


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=10)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        value = value.strip()
        if not any(char.isalpha() for char in value) or not any(char.isdigit() for char in value):
            raise ValueError("Password must contain letters and numbers")
        return value


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AdminUserRead
