from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(UUID, primary_key=True)
    name = Column(String)
    access_token = Column(String)


class Audio(Base):
    __tablename__ = 'audios'
    id = Column(UUID, primary_key=True)
    user_id = Column(UUID)
    file_path = Column(String)
