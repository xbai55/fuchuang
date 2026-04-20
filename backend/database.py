from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, create_engine, text
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, synonym


SQLALCHEMY_DATABASE_URL = "sqlite:///./fraud_detection.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    user_role = Column(String(20), default="general")
    age_group = Column(String(20), default="unknown")
    gender = Column(String(20), default="unknown")
    occupation = Column(String(40), default="other")
    guardian_name = Column(String(100), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    theme = Column(String(20), default="dark")
    notify_enabled = Column(Boolean, default=True)
    notify_high_risk = Column(Boolean, default=True)
    notify_guardian_alert = Column(Boolean, default=True)
    language = Column(String(10), default="zh-CN")
    font_size = Column(String(10), default="medium")
    privacy_mode = Column(Boolean, default=False)

    contacts = relationship("Contact", back_populates="user", cascade="all, delete-orphan")
    chat_history = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan")


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(100), default="")
    contact_relationship = Column(String(50), default="friend")
    is_guardian = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="contacts")
    relationship = synonym("contact_relationship")


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_message = Column(Text, nullable=False)
    bot_response = Column(Text, nullable=False)
    risk_score = Column(Integer, default=0)
    risk_level = Column(String(20), default="low")
    scam_type = Column(String(100), default="")
    guardian_alert = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="chat_history")


def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_user_profile_columns()
    _ensure_contact_columns()


def _ensure_user_profile_columns() -> None:
    expected_columns = {
        "age_group": "ALTER TABLE users ADD COLUMN age_group VARCHAR(20) DEFAULT 'unknown'",
        "gender": "ALTER TABLE users ADD COLUMN gender VARCHAR(20) DEFAULT 'unknown'",
        "occupation": "ALTER TABLE users ADD COLUMN occupation VARCHAR(40) DEFAULT 'other'",
    }

    with engine.begin() as conn:
        existing_columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()
        }
        for column_name, ddl in expected_columns.items():
            if column_name not in existing_columns:
                conn.execute(text(ddl))


def _ensure_contact_columns() -> None:
    expected_columns = {
        "email": "ALTER TABLE contacts ADD COLUMN email VARCHAR(100) DEFAULT ''",
    }

    with engine.begin() as conn:
        existing_columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(contacts)")).fetchall()
        }
        for column_name, ddl in expected_columns.items():
            if column_name not in existing_columns:
                conn.execute(text(ddl))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
