import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean,
    DateTime, Text, Enum, JSON
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

_DB_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '3306')}"
    f"/{os.getenv('DB_NAME', 'newsbot')}?charset=utf8mb4"
)

engine = create_engine(_DB_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    name            = Column(String(255), nullable=False)
    feed_url        = Column(String(512))
    site_url        = Column(String(512), nullable=False)
    active          = Column(Boolean, default=True)
    scrape_fallback = Column(Boolean, default=False)


class Article(Base):
    __tablename__ = "articles"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    url          = Column(String(1024), nullable=False, unique=True)
    title        = Column(String(512))
    source_name  = Column(String(255))
    published_at = Column(DateTime)
    fetched_at   = Column(DateTime, default=datetime.utcnow)
    full_text    = Column(LONGTEXT)
    status       = Column(Enum("pending", "evaluated", "error"), default="pending")
    is_relevant  = Column(Boolean)
    summary      = Column(Text)
    tags         = Column(JSON)
    emailed_at   = Column(DateTime)
