import re

from pydantic import BaseModel, field_validator

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_\u4e00-\u9fff]+$")


class RegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("用户名至少2个字符")
        if len(v) > 32:
            raise ValueError("用户名最多32个字符")
        if not USERNAME_RE.match(v):
            raise ValueError("用户名只能包含字母、数字、下划线或中文")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("密码至少8个字符")
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("密码需要包含至少一个字母")
        if not re.search(r"\d", v):
            raise ValueError("密码需要包含至少一个数字")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class UserResponse(BaseModel):
    id: int
    username: str
    created_at: str
