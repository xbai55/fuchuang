from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# SQLite 数据库配置
SQLALCHEMY_DATABASE_URL = "sqlite:///./fraud_detection.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# 数据库模型
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    user_role = Column(String(20), default="general")  # elderly/student/finance/general
    guardian_name = Column(String(100), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # 关系
    contacts = relationship("Contact", back_populates="user", cascade="all, delete-orphan")
    chat_history = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan")

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    contact_relationship = Column(String(50), default="亲友")  # 亲友/家人/同事/其他
    is_guardian = Column(Boolean, default=False)  # 是否为监护人
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    user = relationship("User", back_populates="contacts")

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

    # 关系
    user = relationship("User", back_populates="chat_history")

class FraudCase(Base):
    """清洗后的互联网诈骗案例知识库，供 RAG 检索使用。"""
    __tablename__ = "fraud_cases"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(100), nullable=False)          # 数据来源标识 (e.g. "csv_batch_2024")
    source_id = Column(String(100), unique=True, index=True)  # 原始来源 ID，防重复导入
    raw_text = Column(Text, nullable=False)               # 原始文本
    cleaned_text = Column(Text, nullable=False)           # 清洗后文本
    scam_type = Column(String(100), default="")           # LLM 自动标注诈骗类型
    risk_keywords = Column(Text, default="")              # JSON 数组，关键风险词
    legal_references = Column(Text, default="")           # 关联法律条文
    severity = Column(String(20), default="medium")       # high/medium/low 基准
    text_hash = Column(String(64), unique=True, index=True)  # SHA256，去重用
    is_synced = Column(Boolean, default=False)            # 是否已同步到 Coze 知识库
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# 初始化数据库
def init_db():
    Base.metadata.create_all(bind=engine)

# 获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
