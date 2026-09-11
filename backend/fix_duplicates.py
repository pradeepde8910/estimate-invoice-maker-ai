from app.core.database import SessionLocal
from app.models.estimation import Document
from app.utils.letterhead import apply_letterhead
from app.services import organization_service as organization

def main():
    db = SessionLocal()
    try:
        profile = organization.get_organization_profile()
        documents = db.query(Document).filter(Document.type.in_(["quotation", "brd", "srs"])).all()
        updated = 0
        for doc in documents:
            if doc.content:
                lines = doc.content.split('\n')
                
                # Strip ALL letterheads from the top
                while True:
                    found_hr = -1
                    for i in range(min(40, len(lines))):
                        if lines[i].strip() == '---':
                            found_hr = i
                            break
                    
                    chunk = '\n'.join(lines[:found_hr])
                    if found_hr != -1 and "**ORGANIZATION DETAILS**" in chunk:
                        lines = lines[found_hr + 1:]
                        while lines and lines[0].strip() == "":
                            lines.pop(0)
                    else:
                        break
                
                # Strip ALL signature blocks from the bottom
                while True:
                    found_hr = -1
                    for i in range(len(lines) - 1, max(-1, len(lines) - 25), -1):
                        if lines[i].strip() == '---':
                            found_hr = i
                            break
                    
                    if found_hr != -1:
                        chunk = '\n'.join(lines[found_hr:])
                        if "Signatory" in chunk or "for " in chunk or "![" in chunk or "Signature" in chunk or len(chunk.split('\n')) <= 15:
                            lines = lines[:found_hr]
                            while lines and lines[-1].strip() == "":
                                lines.pop()
                        else:
                            break
                    else:
                        break

                stripped = '\n'.join(lines).strip()
                doc.content = apply_letterhead(stripped, profile)
                updated += 1
        db.commit()
        print(f"Updated {updated} documents.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
