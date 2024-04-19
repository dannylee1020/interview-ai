from pydantic import BaseModel


class UserProfile(BaseModel):
    email: str
    name: str


class UserPreference(BaseModel):
    theme: str
    language: str
    model: str
