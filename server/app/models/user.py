from datetime import datetime
import email
from typing import Optional
from pydantic import BaseModel,Field, EmailStr

class User(BaseModel):
    id : str
    email : EmailStr
    created_at : Optional[datetime] = None
    
    email_confirmed_at : Optional[datetime] = None
    last_sign_in_at : Optional[datetime] = None

class TokenPayload(BaseModel):
    sub : str
    email:str
    exp : int
    iat : int