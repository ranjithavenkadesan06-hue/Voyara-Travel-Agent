
from pydantic import BaseModel, EmailStr


# -----------------------------
# User Registration
# -----------------------------
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


# -----------------------------
# User Login
# -----------------------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# -----------------------------
# User Response
# -----------------------------
class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr

    class Config:
        from_attributes = True


# -----------------------------
# Authentication Token
# -----------------------------
class Token(BaseModel):
    access_token: str
    token_type: str

