"""
Regression test for a real production bug: app/api/system.py's
get_analytics() and app/services/client_service.py's list_derived_clients()
both closed their DB session immediately after querying Estimation rows,
then accessed est.client (a lazy-loaded relationship) afterward — raising
sqlalchemy.orm.exc.DetachedInstanceError as soon as there was a real
Estimation row to iterate.

This class of bug is invisible against an empty test database (an empty
list never touches the lazy attribute), which is exactly how it slipped
past the rest of the test suite — these tests deliberately seed at least
one real row with a client so the lazy-load actually gets exercised.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.master import Client
from app.models.estimation import Estimation


@pytest.fixture
def SessionLocal():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = Session()
    client = Client(company_name="Acme Test Corp")
    db.add(client)
    db.commit()
    db.refresh(client)

    est = Estimation(
        id="test-est-1", estimation_number="EST-2026-000001", client_id=client.id,
        project_name="Test Project", status="Completed", grand_total=1000.0,
    )
    db.add(est)
    db.commit()
    db.close()

    return Session


def test_analytics_does_not_raise_on_detached_client_access(SessionLocal, monkeypatch):
    from app.api import system
    import asyncio

    monkeypatch.setattr(system, "SessionLocal", SessionLocal)

    # Calling the endpoint function directly (bypassing FastAPI's request
    # cycle) exercises the exact query + post-close access pattern that
    # broke — `user`'s Depends() default is never touched by the function
    # body, so passing None in its place is safe here.
    result = asyncio.run(system.get_analytics(user=None))
    assert result["total_estimations"] == 1
    assert result["recent"][0]["client_name"] == "Acme Test Corp"


def test_list_derived_clients_does_not_raise_on_detached_client_access(SessionLocal, monkeypatch):
    from app.services import client_service

    monkeypatch.setattr(client_service, "SessionLocal", SessionLocal)

    clients = client_service.list_derived_clients()
    assert len(clients) == 1
    assert clients[0]["client_name"] == "Acme Test Corp"
