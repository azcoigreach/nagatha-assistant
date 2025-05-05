from nagatha_assistant.db import engine, SessionLocal, Base

def test_db_components_exist():
    assert engine is not None
    assert SessionLocal is not None
    assert Base is not None