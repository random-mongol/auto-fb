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

class PostedArticle(Base):
    __tablename__ = "posted_articles"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True, nullable=False)
    posted_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<PostedArticle(url='{self.url}')>"

class FBFriend(Base):
    __tablename__ = "fb_friends"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    profile_url = Column(String, unique=True, index=True, nullable=False)
    last_messaged_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<FBFriend(name='{self.name}', profile_url='{self.profile_url}')>"


class GeneratedReel(Base):
    __tablename__ = "generated_reels"

    id = Column(Integer, primary_key=True, index=True)
    source_url = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    artifact_dir = Column(String, nullable=False)
    status = Column(String, nullable=False, server_default="topic")
    script_word_count = Column(Integer, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    error_message = Column(String, nullable=True)
    topic_generated_at = Column(DateTime, nullable=True)
    script_generated_at = Column(DateTime, nullable=True)
    voice_generated_at = Column(DateTime, nullable=True)
    visuals_generated_at = Column(DateTime, nullable=True)
    edited_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<GeneratedReel(source_url='{self.source_url}', status='{self.status}')>"
