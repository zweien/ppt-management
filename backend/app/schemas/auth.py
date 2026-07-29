"""Auth schemas."""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


class UserOut(BaseModel):
    id: str
    username: str
    is_superuser: bool


from pydantic import model_validator  # noqa: E402

# forward ref
TokenResponse.model_rebuild()


class UserOutResolver:  # helper to avoid circular import order issues
    @staticmethod
    def from_model(user) -> UserOut:
        return UserOut(id=user.id, username=user.username, is_superuser=user.is_superuser)
