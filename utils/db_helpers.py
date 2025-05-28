from .db import SessionLocal, Customer, ConversationHistory

def get_customer(phone):
    db = SessionLocal()
    customer = db.query(Customer).filter(Customer.phone == phone).first()
    db.close()
    return customer

def add_or_update_customer(phone, name=None, language=None, onboarding_step=None, service_interest=None):
    db = SessionLocal()
    customer = db.query(Customer).filter(Customer.phone == phone).first()
    if not customer:
        customer = Customer(phone=phone)
        db.add(customer)
    if name is not None:
        customer.name = name
    if language is not None:
        customer.language = language
    if onboarding_step is not None:
        customer.onboarding_step = onboarding_step
    if service_interest is not None:
        customer.service_interest = service_interest
    db.commit()
    db.close()

def add_message(phone, sender, message):
    db = SessionLocal()
    msg = ConversationHistory(phone=phone, sender=sender, message=message)
    db.add(msg)
    db.commit()
    db.close()

def get_conversation(phone):
    db = SessionLocal()
    conv = db.query(ConversationHistory).filter(ConversationHistory.phone == phone).order_by(ConversationHistory.timestamp).all()
    db.close()
    return [{"sender": m.sender, "message": m.message, "timestamp": m.timestamp.isoformat()} for m in conv]
