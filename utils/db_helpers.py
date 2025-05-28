# utils/db_helpers.py

from .db import SessionLocal, Customer, ConversationHistory
from sqlalchemy.exc import SQLAlchemyError

# Context manager style for safety
def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_customer(phone):
    with SessionLocal() as db:
        return db.query(Customer).filter(Customer.phone == phone).first()

def add_customer(phone, name=None, language=None, onboarding_step=None, service_interest=None):
    try:
        with SessionLocal() as db:
            customer = Customer(
                phone=phone,
                name=name,
                language=language,
                onboarding_step=onboarding_step,
                service_interest=service_interest
            )
            db.add(customer)
            db.commit()
    except SQLAlchemyError as e:
        print(f"Error adding customer: {e}")

def update_customer(phone, name=None, language=None, onboarding_step=None, service_interest=None):
    try:
        with SessionLocal() as db:
            customer = db.query(Customer).filter(Customer.phone == phone).first()
            if not customer:
                return None
            if name is not None:
                customer.name = name
            if language is not None:
                customer.language = language
            if onboarding_step is not None:
                customer.onboarding_step = onboarding_step
            if service_interest is not None:
                customer.service_interest = service_interest
            db.commit()
            return customer
    except SQLAlchemyError as e:
        print(f"Error updating customer: {e}")

def add_or_update_customer(phone, name=None, language=None, onboarding_step=None, service_interest=None):
    customer = get_customer(phone)
    if customer:
        return update_customer(phone, name, language, onboarding_step, service_interest)
    else:
        return add_customer(phone, name, language, onboarding_step, service_interest)

def add_message(phone, sender, message):
    try:
        with SessionLocal() as db:
            msg = ConversationHistory(phone=phone, sender=sender, message=message)
            db.add(msg)
            db.commit()
    except SQLAlchemyError as e:
        print(f"Error adding message: {e}")

def get_conversation(phone):
    with SessionLocal() as db:
        conv = db.query(ConversationHistory)\
            .filter(ConversationHistory.phone == phone)\
            .order_by(ConversationHistory.timestamp)\
            .all()
        return [
            {"sender": m.sender, "message": m.message, "timestamp": m.timestamp.isoformat()}
            for m in conv
        ]
