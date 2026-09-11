from app.core.database import SessionLocal
from app.models.estimation import Document

db = SessionLocal()
doc = db.query(Document).filter(Document.type.in_(["quotation", "brd", "srs"])).first()
if doc and doc.content:
    lines = doc.content.split('\n')
    for i, line in enumerate(lines[:60]):
        print(f"{i}: {line}")
db.close()
