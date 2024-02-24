from pydantic import BaseModel


class UserProfile(BaseModel):
    email: str
    name: str
    username: str
