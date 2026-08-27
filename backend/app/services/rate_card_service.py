"""
Developer rate card service — the RateCard DB table is the source of
truth; config.DEVELOPER_RATES is kept in sync as a read cache for code
that still reads rates off config directly (see app.core.database.
sync_rate_card, which runs at startup), not the other way around.
"""

from datetime import datetime

from app import config
from app.core.database import SessionLocal
from app.models.rate_card import RateCard


def get_rates() -> dict:
    return config.DEVELOPER_RATES


def update_rates(rates: dict) -> dict:
    """Applies a full rates payload: adds/updates changed roles (closing out
    the previous version and opening a new one, preserving history) and
    deactivates any active role no longer present in the payload. One
    transaction — either the whole update lands or none of it does."""
    db = SessionLocal()
    try:
        for key, value in rates.items():
            new_rate = value.get("rate_per_hour")
            new_label = value.get("label", key)
            if new_rate is None:
                continue

            current_active = db.query(RateCard).filter(
                RateCard.role_key == key, RateCard.is_active == True
            ).first()

            if current_active:
                if current_active.rate_per_hour != new_rate or current_active.role_label != new_label:
                    current_active.is_active = False
                    current_active.effective_to = datetime.utcnow()
                    db.add(RateCard(
                        role_key=key, role_label=new_label, rate_per_hour=new_rate,
                        effective_from=datetime.utcnow(), is_active=True,
                    ))
            else:
                db.add(RateCard(
                    role_key=key, role_label=new_label, rate_per_hour=new_rate,
                    effective_from=datetime.utcnow(), is_active=True,
                ))

            config.DEVELOPER_RATES[key] = {
                "rate_per_hour": new_rate,
                "label": new_label,
                "is_custom": key not in config.SYSTEM_ROLE_KEYS,
            }

        # Deletions: any currently-active role not present in the payload.
        active_roles = db.query(RateCard).filter(RateCard.is_active == True).all()
        for role in active_roles:
            if role.role_key not in rates:
                role.is_active = False
                role.effective_to = datetime.utcnow()
                config.DEVELOPER_RATES.pop(role.role_key, None)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return config.DEVELOPER_RATES
