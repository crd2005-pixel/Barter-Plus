import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class Brand(Base):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    niche = Column(String, nullable=False)
    target_audience = Column(Text, nullable=False)
    brand_voice = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    pillars = relationship("ContentPillar", back_populates="brand", cascade="all, delete-orphan")
    posts = relationship("Post", back_populates="brand", cascade="all, delete-orphan")

class ContentPillar(Base):
    __tablename__ = "content_pillars"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    brand = relationship("Brand", back_populates="pillars")
    posts = relationship("Post", back_populates="pillar")

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)
    pillar_id = Column(Integer, ForeignKey("content_pillars.id"), nullable=True)
    format = Column(String, nullable=False)
    hook = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    cta = Column(String, nullable=False)
    hashtags = Column(Text, nullable=True)
    visual_idea = Column(Text, nullable=False)
    status = Column(String, default="draft")
    scheduled_for = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    brand = relationship("Brand", back_populates="posts")
    pillar = relationship("ContentPillar", back_populates="posts")
