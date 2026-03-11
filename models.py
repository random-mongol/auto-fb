from sqlalchemy import Column, Integer, String, DateTime, func
from database import Base

class FBGroup(Base):
    __tablename__ = "fbgroups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    facebook = Column(String, unique=True, index=True, nullable=False)
    last_liked_date = Column(DateTime, nullable=True)
    last_marketed_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<FBGroup(name='{self.name}', facebook='{self.facebook}')>"
