"""
Seeds the Resource & Capability catalog with 50 provider/capability/model
entries across LLMs, speech, storage, compute, and common SaaS
infrastructure (Stripe, Twilio, SendGrid, Auth0, Cloudflare, etc.), each
with its feature attributes and one ApiPricingRule.

All prices here are pricing_source="market_estimate" (not verified_catalog)
— they're realistic public list prices as of when this was written, in USD,
but haven't been checked against each vendor's live pricing page. Treat
them as a usable starting point for estimation, not as authoritative
numbers to quote a client without re-checking.

Idempotent: get-or-create by unique key at every level, safe to re-run —
running it again after editing a price here will NOT overwrite a price an
admin already edited via the catalog UI, since existing rows are left alone.

Usage (from backend/):
    python -m app.scripts.seed_resource_catalog_extended
"""
import logging

from app.database import SessionLocal, engine
from app.models.base import Base
from app.models.resource_catalog import (
    Capability, TechnologyProvider, TechnologyModel, ModelFeature, ApiPricingRule,
)

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


PROVIDERS = {
    "sarvam":     ("Sarvam AI", "https://www.sarvam.ai"),
    "openai":     ("OpenAI", "https://openai.com"),
    "anthropic":  ("Anthropic", "https://anthropic.com"),
    "aws":        ("Amazon Web Services", "https://aws.amazon.com"),
    "gcp":        ("Google Cloud Platform", "https://cloud.google.com"),
    "twilio":     ("Twilio", "https://twilio.com"),
    "sendgrid":   ("SendGrid", "https://sendgrid.com"),
    "stripe":     ("Stripe", "https://stripe.com"),
    "cloudflare": ("Cloudflare", "https://cloudflare.com"),
    "auth0":      ("Auth0", "https://auth0.com"),
}

CAPABILITIES = {
    "speech_to_text":    ("Speech-to-Text", "ai_service"),
    "text_to_speech":    ("Text-to-Speech", "ai_service"),
    "llm_inference":     ("LLM Inference", "ai_service"),
    "image_generation":  ("Image Generation", "ai_service"),
    "object_storage":    ("Object Storage", "infrastructure"),
    "relational_db":     ("Relational Database", "infrastructure"),
    "vector_database":   ("Vector Database", "infrastructure"),
    "serverless_compute": ("Serverless Compute", "infrastructure"),
    "sms_gateway":       ("SMS Gateway", "external_service"),
    "email_delivery":    ("Email Delivery", "external_service"),
    "payment_gateway":   ("Payment Gateway", "external_service"),
    "cdn_delivery":      ("CDN Delivery", "infrastructure"),
    "identity_auth":     ("Identity & Authentication", "external_service"),
    "video_transcoding": ("Video Transcoding", "infrastructure"),
    "push_notifications": ("Push Notifications", "external_service"),
}

# (provider_key, capability_key, model_key, model_name, features_dict, pricing_type, unit, price)
MODELS = [
    ("sarvam", "speech_to_text", "sarvam-saaras:v1", "Saaras STT",
     {"language": "Hindi, Tamil, Telugu, English", "quality": "standard"}, "USAGE", "MINUTE", "0.006"),
    ("sarvam", "text_to_speech", "sarvam-bulbul:v1", "Bulbul TTS",
     {"language": "Indic multilingual", "quality": "high"}, "USAGE", "CHARACTER", "0.000015"),
    ("openai", "llm_inference", "gpt-4o", "GPT-4o Omni",
     {"context_window": "128k", "modality": "multimodal"}, "USAGE", "1K_TOKENS", "0.005"),
    ("openai", "llm_inference", "gpt-4o-mini", "GPT-4o Mini",
     {"context_window": "128k", "speed": "fast"}, "USAGE", "1K_TOKENS", "0.00015"),
    ("openai", "image_generation", "dall-e-3", "DALL-E 3",
     {"resolution": "1024x1024", "quality": "hd"}, "FLAT", "IMAGE", "0.040"),
    ("anthropic", "llm_inference", "claude-3-5-sonnet", "Claude 3.5 Sonnet",
     {"tier": "flagship", "coding": "advanced"}, "USAGE", "1K_TOKENS", "0.003"),
    ("anthropic", "llm_inference", "claude-3-haiku", "Claude 3 Haiku",
     {"tier": "lightweight", "latency": "ultra-low"}, "USAGE", "1K_TOKENS", "0.00025"),
    ("aws", "object_storage", "aws-s3-standard", "Amazon S3 Standard",
     {"durability": "99.999999999%", "tier": "hot"}, "USAGE", "GB_MONTH", "0.023"),
    ("aws", "relational_db", "aws-rds-postgres", "Amazon RDS PostgreSQL",
     {"engine": "PostgreSQL 15", "managed": "true"}, "FLAT", "HOURLY", "0.041"),
    ("gcp", "vector_database", "gcp-vertex-vector-search", "Vertex AI Vector Search",
     {"scale": "billions of vectors", "latency": "low"}, "FLAT", "NODE_HOUR", "0.750"),
    ("gcp", "serverless_compute", "gcp-cloud-functions", "Google Cloud Functions v2",
     {"runtime": "Node.js / Python / Go", "scaling": "automatic"}, "USAGE", "MILLION_INVOCATIONS", "0.400"),
    ("twilio", "sms_gateway", "twilio-programmable-sms", "Programmable SMS API",
     {"global_reach": "180+ countries", "delivery_reports": "true"}, "USAGE", "MESSAGE", "0.0079"),
    ("twilio", "speech_to_text", "twilio-media-streams", "Media Streams STT",
     {"protocol": "WebSockets", "realtime": "true"}, "USAGE", "MINUTE", "0.020"),
    ("sendgrid", "email_delivery", "sendgrid-mail-send", "SendGrid Web API v3",
     {"deliverability": "high", "analytics": "advanced"}, "USAGE", "1K_EMAILS", "1.000"),
    ("stripe", "payment_gateway", "stripe-payments-api", "Stripe Payments & Checkout",
     {"compliance": "PCI-DSS Level 1", "methods": "cards, wallets"}, "USAGE", "PERCENTAGE_TXN", "2.9"),
    ("cloudflare", "cdn_delivery", "cloudflare-enterprise-cdn", "Cloudflare Enterprise CDN",
     {"edge_locations": "300+ cities", "ddos_protection": "unlimited"}, "FLAT", "MONTHLY", "5000.00"),
    ("cloudflare", "object_storage", "cloudflare-r2", "Cloudflare R2 Storage",
     {"egress_fees": "zero", "compatibility": "S3 API"}, "USAGE", "GB_MONTH", "0.015"),
    ("auth0", "identity_auth", "auth0-standard-tenant", "Auth0 M2M & User Auth",
     {"protocols": "OAuth2 / OIDC / SAML", "mfa": "supported"}, "FLAT", "MONTHLY", "230.00"),
    ("aws", "video_transcoding", "aws-elastic-transcoder", "AWS Elemental MediaConvert",
     {"codecs": "H.264, H.265, AV1", "resolution": "4K UHD"}, "USAGE", "TRANSCODE_MINUTE", "0.015"),
    ("gcp", "speech_to_text", "gcp-speech-to-text-v2", "Google Cloud STT v2",
     {"recognition_model": "chirp", "profanity_filter": "true"}, "USAGE", "MINUTE", "0.016"),
    ("openai", "speech_to_text", "whisper-large-v3", "Whisper Large v3 API",
     {"multilingual": "99 languages", "translation": "supported"}, "USAGE", "MINUTE", "0.006"),
    ("anthropic", "llm_inference", "claude-3-opus", "Claude 3 Opus",
     {"reasoning": "expert level", "analysis": "deep"}, "USAGE", "1K_TOKENS", "0.015"),
    ("twilio", "push_notifications", "twilio-notify", "Twilio Notify API",
     {"platforms": "FCM, APNS, WebPush", "multichannel": "true"}, "USAGE", "NOTIFICATION", "0.0025"),
    ("sendgrid", "email_delivery", "sendgrid-marketing-api", "SendGrid Marketing Campaigns",
     {"contacts": "segmented", "automation": "drip workflows"}, "FLAT", "MONTHLY", "15.00"),
    ("stripe", "payment_gateway", "stripe-billing", "Stripe Billing & Subscriptions",
     {"invoicing": "automated", "dunning": "smart retries"}, "USAGE", "PERCENTAGE_TXN", "0.7"),
    ("sarvam", "llm_inference", "sarvam-m-translate", "Sarvam Translate Model",
     {"domain": "Indic regional translation", "speed": "optimized"}, "USAGE", "1K_TOKENS", "0.001"),
    ("openai", "text_to_speech", "tts-1", "OpenAI Standard TTS",
     {"voices": "alloy, echo, fable, onyx", "latency": "real-time"}, "USAGE", "1K_CHARACTERS", "0.015"),
    ("openai", "text_to_speech", "tts-1-hd", "OpenAI High-Definition TTS",
     {"quality": "broadcast", "voices": "alloy, echo, fable"}, "USAGE", "1K_CHARACTERS", "0.030"),
    ("aws", "llm_inference", "aws-bedrock-claude", "Amazon Bedrock Claude 3",
     {"security": "enterprise-grade", "region": "multi-region"}, "USAGE", "1K_TOKENS", "0.003"),
    ("aws", "llm_inference", "aws-bedrock-llama3", "Amazon Bedrock Llama 3",
     {"open_weights": "true", "parameters": "70b"}, "USAGE", "1K_TOKENS", "0.0009"),
    ("gcp", "llm_inference", "gemini-1.5-pro", "Gemini 1.5 Pro",
     {"context_window": "2M tokens", "multimodal": "native"}, "USAGE", "1K_TOKENS", "0.0035"),
    ("gcp", "llm_inference", "gemini-1.5-flash", "Gemini 1.5 Flash",
     {"speed": "high", "cost_efficiency": "maximum"}, "USAGE", "1K_TOKENS", "0.00035"),
    ("twilio", "sms_gateway", "twilio-whatsapp-api", "Twilio WhatsApp Business API",
     {"templates": "pre-approved", "media": "supported"}, "USAGE", "CONVERSATION", "0.005"),
    ("cloudflare", "serverless_compute", "cloudflare-workers", "Cloudflare Workers Edge Compute",
     {"cold_starts": "zero", "global_distribution": "yes"}, "USAGE", "MILLION_REQUESTS", "0.500"),
    ("auth0", "identity_auth", "auth0-enterprise-federation", "Auth0 Enterprise SAML/SSO",
     {"protocols": "SAML 2.0 / WS-Fed", "directories": "Active Directory"}, "FLAT", "MONTHLY", "450.00"),
    ("stripe", "payment_gateway", "stripe-connect", "Stripe Connect Marketplace Payouts",
     {"payouts": "global", "split_payments": "supported"}, "USAGE", "PERCENTAGE_TXN", "0.25"),
    ("aws", "cdn_delivery", "aws-cloudfront", "Amazon CloudFront CDN",
     {"edge_servers": "450+", "lambda_at_edge": "supported"}, "USAGE", "GB_TRANSFERRED", "0.085"),
    ("gcp", "object_storage", "gcp-cloud-storage", "Google Cloud Storage Standard",
     {"redundancy": "multi-regional", "availability": "99.95%"}, "USAGE", "GB_MONTH", "0.026"),
    ("sendgrid", "email_delivery", "sendgrid-inbound-parse", "SendGrid Inbound Parse Webhook",
     {"parsing": "MIME to JSON", "realtime": "webhook dispatch"}, "FLAT", "MONTHLY", "50.00"),
    ("cloudflare", "vector_database", "cloudflare-vectorize", "Cloudflare Vectorize",
     {"embedding_dimensions": "up to 1536", "integration": "Workers AI"}, "USAGE", "MILLION_QUERIES", "1.00"),
    ("sarvam", "llm_inference", "sarvam-2b", "Sarvam 2B Indic LLM",
     {"optimized_for": "Indian languages", "size": "lightweight"}, "USAGE", "1K_TOKENS", "0.0004"),
    ("openai", "llm_inference", "gpt-3.5-turbo", "GPT-3.5 Turbo Legacy",
     {"legacy_support": "active", "speed": "fast"}, "USAGE", "1K_TOKENS", "0.0005"),
    ("anthropic", "llm_inference", "claude-3-haiku-bedrock", "Claude 3 Haiku via Bedrock",
     {"deployment": "AWS Managed", "latency": "fast"}, "USAGE", "1K_TOKENS", "0.0003"),
    ("aws", "relational_db", "aws-aurora-serverless", "Amazon Aurora Serverless v2",
     {"auto_scaling": "instantaneous", "compatible": "MySQL/Postgres"}, "USAGE", "ACU_HOUR", "0.060"),
    ("gcp", "relational_db", "gcp-cloud-sql", "Cloud SQL for PostgreSQL",
     {"failover": "automatic high availability", "backups": "automated"}, "FLAT", "HOURLY", "0.038"),
    ("twilio", "email_delivery", "twilio-sendgrid-relay", "SendGrid Email via Twilio Account",
     {"bundling": "unified billing", "analytics": "dashboard"}, "USAGE", "1K_EMAILS", "1.150"),
    ("cloudflare", "identity_auth", "cloudflare-zero-trust", "Cloudflare Access & Zero Trust",
     {"gateway": "secure web", "identity_providers": "Okta, Google, Azure AD"}, "FLAT", "USER_MONTH", "7.00"),
    ("stripe", "payment_gateway", "stripe-terminal", "Stripe Terminal In-Person Payments",
     {"hardware": "reader integration", "omnichannel": "true"}, "USAGE", "PERCENTAGE_TXN", "2.7"),
    ("aws", "serverless_compute", "aws-lambda", "AWS Lambda Functions",
     {"execution_time": "up to 15 mins", "layers": "supported"}, "USAGE", "MILLION_REQUESTS", "0.200"),
    ("gcp", "speech_to_text", "gcp-dialogflow-cx", "Dialogflow CX Conversational STT",
     {"agent_type": "virtual agent", "intent_matching": "advanced"}, "USAGE", "SESSION", "0.007"),
]

PRICING_TYPE_TO_MODEL = {"USAGE": "PER_UNIT", "FLAT": "FLAT"}


def run_seed():
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        provider_rows = {}
        for key, (name, website) in PROVIDERS.items():
            row, created = _get_or_create(
                session, TechnologyProvider, key=key,
                defaults={"name": name, "website": website},
            )
            provider_rows[key] = row
            logger.info(f"Provider '{key}': {'created' if created else 'already existed'}")

        capability_rows = {}
        for key, (name, category) in CAPABILITIES.items():
            row, created = _get_or_create(
                session, Capability, key=key,
                defaults={"name": name, "category": category},
            )
            capability_rows[key] = row
            logger.info(f"Capability '{key}': {'created' if created else 'already existed'}")

        model_created_count = 0
        pricing_created_count = 0
        for provider_key, capability_key, model_key, model_name, features, price_type, unit, price in MODELS:
            model_row, created = _get_or_create(
                session, TechnologyModel,
                model_key=model_key,
                provider_id=provider_rows[provider_key].id,
                capability_id=capability_rows[capability_key].id,
                defaults={"model_name": model_name},
            )
            if created:
                model_created_count += 1
                for feature_key, raw_value in features.items():
                    for value in [v.strip() for v in raw_value.split(",")]:
                        session.add(ModelFeature(model_id=model_row.id, feature_key=feature_key, feature_value=value))

            existing_pricing = session.query(ApiPricingRule).filter_by(
                model_id=model_row.id, unit_type=unit, pricing_source="market_estimate"
            ).first()
            if not existing_pricing:
                session.add(ApiPricingRule(
                    model_id=model_row.id,
                    pricing_model=PRICING_TYPE_TO_MODEL[price_type],
                    unit_type=unit,
                    price=price,
                    currency="USD",
                    pricing_source="market_estimate",
                ))
                pricing_created_count += 1

        session.commit()
        logger.info(
            f"Extended catalog seed complete: {model_created_count} new models, "
            f"{pricing_created_count} new pricing rules across {len(PROVIDERS)} providers "
            f"and {len(CAPABILITIES)} capabilities. All prices are pricing_source="
            f"'market_estimate' in USD — verify against vendor pricing pages before "
            f"quoting a client, then update to pricing_source='verified_catalog'."
        )
    finally:
        session.close()


if __name__ == "__main__":
    run_seed()
