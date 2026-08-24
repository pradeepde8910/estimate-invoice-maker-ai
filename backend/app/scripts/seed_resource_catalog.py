"""
Seeds the Resource & Capability catalog with its first real example:
speech_to_text -> Sarvam AI -> a speech-to-text model.

Deliberately seeds structure only, NOT a price. Sarvam being a real
multilingual speech-to-text vendor is a safe fact to hardcode; a specific
₹/unit price is not — this catalog eventually feeds client quotations, and
an invented "placeholder" number left in place by accident would be far
worse than an admin having to look up and enter the real one once via the
admin UI. Add the actual verified pricing there (Billing Classifications-style
CRUD), with pricing_source='verified_catalog' and a real source_url, once
you've confirmed it against Sarvam's official pricing page.

Idempotent: get-or-create by unique key, safe to re-run.

Usage (from backend/app/):
    python -m scripts.seed_resource_catalog
"""
import logging

from app.database import SessionLocal, engine
from app.models.base import Base
from app.models.resource_catalog import Capability, TechnologyProvider, TechnologyModel, ModelFeature

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _get_or_create(session, model, defaults=None, **lookup):
    instance = session.query(model).filter_by(**lookup).first()
    if instance:
        return instance, False
    instance = model(**{**lookup, **(defaults or {})})
    session.add(instance)
    session.flush()
    return instance, True


def run_seed():
    Base.metadata.create_all(bind=engine)  # ensure tables exist even if migration hasn't run yet

    session = SessionLocal()
    try:
        capability, created = _get_or_create(
            session, Capability,
            key="speech_to_text",
            defaults={
                "name": "Speech-to-Text",
                "category": "ai_service",
                "description": "Converts spoken audio into text, optionally across multiple languages.",
            },
        )
        logger.info(f"Capability 'speech_to_text': {'created' if created else 'already existed'}")

        provider, created = _get_or_create(
            session, TechnologyProvider,
            key="sarvam",
            defaults={"name": "Sarvam AI", "website": "https://www.sarvam.ai"},
        )
        logger.info(f"Provider 'sarvam': {'created' if created else 'already existed'}")

        model_row, created = _get_or_create(
            session, TechnologyModel,
            model_key="saarika",
            provider_id=provider.id,
            capability_id=capability.id,
            defaults={
                "model_name": "Saarika (Sarvam Speech-to-Text)",
                "description": (
                    "Sarvam AI's multilingual speech-to-text model for Indian languages. "
                    "No pricing is seeded here — add a verified ApiPricingRule via the admin "
                    "catalog UI once confirmed against Sarvam's official pricing page."
                ),
            },
        )
        logger.info(f"Model 'saarika': {'created' if created else 'already existed'}")

        if created:
            for lang in ["Hindi", "Tamil", "Telugu", "Kannada", "Malayalam", "Bengali", "Marathi", "Gujarati", "Punjabi", "English"]:
                session.add(ModelFeature(model_id=model_row.id, feature_key="language", feature_value=lang))
            session.add(ModelFeature(model_id=model_row.id, feature_key="streaming", feature_value="true"))
            session.add(ModelFeature(model_id=model_row.id, feature_key="region", feature_value="India"))
            logger.info("Seeded language/feature rows for 'saarika'.")

        session.commit()
        logger.info(
            "Resource catalog seed complete. No pricing was added — use the admin UI "
            "to add a verified ApiPricingRule for the Saarika model before relying on it "
            "for cost estimation."
        )
    finally:
        session.close()


if __name__ == "__main__":
    run_seed()
