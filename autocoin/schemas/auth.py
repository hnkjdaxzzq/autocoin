import re

from pydantic import BaseModel, field_validator

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_\u4e00-\u9fff]+$")


INVITE_CODE = "tarikz"


class RegisterRequest(BaseModel):
    username: str
    password: str
    invite_code: str

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

    @field_validator("invite_code")
    @classmethod
    def validate_invite_code(cls, v: str) -> str:
        if v != INVITE_CODE:
            raise ValueError("邀请码错误")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("old_password")
    @classmethod
    def validate_old_password(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("原密码不能为空")
        if len(v) > 128:
            raise ValueError("原密码过长")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("新密码至少8个字符")
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("新密码需要包含至少一个字母")
        if not re.search(r"\d", v):
            raise ValueError("新密码需要包含至少一个数字")
        return v


class UserResponse(BaseModel):
    id: int
    username: str
    created_at: str
