import uuid
from sqlalchemy import Column, String, Text
from app.models.base import Base


class OrganizationProfile(Base):
    __tablename__ = "organization_profiles"

    id = Column(String(255), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), default="Pixous Technologies Pvt Ltd")
    tagline = Column(String(255), default="")
    address = Column(Text, default="")
    email = Column(String(100), default="")
    phone = Column(String(50), default="")
    website = Column(String(100), default="")
    gstin = Column(String(50), default="")
    registration_number = Column(String(50), default="")
    certifications = Column(Text, default="")
    bank_name = Column(String(100), default="")
    bank_account_number = Column(String(100), default="")
    bank_ifsc = Column(String(50), default="")
    bank_branch = Column(String(100), default="")
    upi_id = Column(String(100), default="")
    signatory_name = Column(String(100), default="")
    signatory_title = Column(String(100), default="Authorized Signatory")
    logo_path = Column(String(255), nullable=True)
    signature_path = Column(String(255), nullable=True)
    seal_path = Column(String(255), nullable=True)
    invoice_terms = Column(Text, default="")


class BrandingAsset(Base):
    __tablename__ = "branding_assets"

    slot = Column(String(50), primary_key=True)
    file_name = Column(String(255), nullable=False)
    data = Column(Text, nullable=False)  # Base64 encoded
