from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, func
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


class FBGroupActivity(Base):
    """Per-account activity tracking for groups (likes and marketing)."""
    __tablename__ = "fb_group_activity"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(String, nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("fbgroups.id"), nullable=False, index=True)
    last_liked_date = Column(DateTime, nullable=True)
    last_marketed_date = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("account_id", "group_id", name="uq_fb_group_activity_account_group"),
    )

    def __repr__(self):
        return f"<FBGroupActivity(account='{self.account_id}', group_id={self.group_id})>"


class PostedArticle(Base):
    __tablename__ = "posted_articles"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(String, nullable=True, index=True)
    url = Column(String, nullable=False)
    posted_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("account_id", "url", name="uq_posted_articles_account_url"),
    )

    def __repr__(self):
        return f"<PostedArticle(account='{self.account_id}', url='{self.url}')>"


class FBFriend(Base):
    __tablename__ = "fb_friends"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(String, nullable=True, index=True)
    name = Column(String, nullable=True)
    profile_url = Column(String, nullable=False)
    last_messaged_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("account_id", "profile_url", name="uq_fb_friends_account_profile"),
    )

    def __repr__(self):
        return f"<FBFriend(account='{self.account_id}', name='{self.name}', profile_url='{self.profile_url}')>"


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
