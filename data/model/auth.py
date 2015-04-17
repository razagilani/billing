from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import Integer, String, Boolean, DateTime, Enum
from data.model.orm import Base
from hashlib import sha256
from sqlalchemy.sql.functions import func
from core import config

class User(Base):

    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)

    name = Column(Integer)
    email = Column(String(100))
    admin = Column(Boolean)
    password_sha256 = Column(String(64))
    time_inserted = Column(DateTime, server_default=func.now(), nullable=False)

    def __init__(self, name, email, password, admin=False):
        salt = config.get('http', 'secret_key')

        self.name = name
        self.email = email
        self.password_sha256 = sha256(password + salt).hexdigest()
        self.admin = admin
