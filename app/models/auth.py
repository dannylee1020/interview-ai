from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class TokenData(BaseModel):
    sub: str
    iat: str
    exp: str


class ResetPassword(BaseModel):
    email: str
    new_password: str


class RefreshToken(BaseModel):
    token: str


class Message(BaseModel):
    message: str


class OAuthCred(BaseModel):
    email: str
    name: str
    token: str
    provider: str
