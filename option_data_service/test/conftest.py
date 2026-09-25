import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import event

from app.database import engine, SessionLocal
from app.main import app, get_db


@pytest.fixture
def db_session():
    """One test = one outer transaction that's rolled back at teardown, with a savepoint that
    restarts itself after each `session.commit()` inside the code under test - the standard
    SQLAlchemy recipe for testing code that calls commit() without leaking rows between tests."""
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            sess.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    from fastapi.testclient import TestClient

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
