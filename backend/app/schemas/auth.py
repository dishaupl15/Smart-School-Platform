from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import RoleName


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)
    school_code: str | None = Field(default=None, max_length=50)

    @field_validator("identifier")
    @classmethod
    def identifier_is_not_whitespace(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Identifier is required.")
        return value


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=128)


class AuthenticatedUserResponse(BaseModel):
    id: UUID
    full_name: str
    email: str | None
    username: str | None
    school_id: UUID | None
    school_name: str | None
    roles: list[RoleName]

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: AuthenticatedUserResponse


class MessageResponse(BaseModel):
    message: str
