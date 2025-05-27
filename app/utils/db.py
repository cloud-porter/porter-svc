from sqlalchemy import create_engine
from models import (
    x,
    y
)
from models import Base
from sqlalchemy.orm import declarative_base, sessionmaker

DB_FILE = "db.sqlite"
engine = create_engine(f"sqlite:///{DB_FILE}")
Base.metadata.create_all(
    engine, 
    tables=[
        # x.__table__,
        # y.__table__,
    ]
)

Session = sessionmaker(bind=engine)

def get_db_session():
    db_session = Session()
    try:
        yield db_session
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        raise
    finally:
        db_session.close()