from sqlalchemy import create_engine, Column, String, Integer, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Customer(Base):
    __tablename__ = "customers"
    phone = Column(String, primary_key=True, index=True)
    name = Column(String)
    language = Column(String)
    onboarding_step = Column(String)
    service_interest = Column(String)

class ConversationHistory(Base):
    __tablename__ = "conversation_history"
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String)
    sender = Column(String)
    message = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

# لو بتشتغل محلي شغل الملف ده مرة واحدة:
if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
