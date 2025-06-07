from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

from sqlalchemy import create_engine  # type: ignore
from sqlalchemy.orm import scoped_session, sessionmaker  # type: ignore
import yaml  # type: ignore
import os

# SQLAlchemy setup
engine: Any = None
Session: Any = None

def load_db_config() -> dict:
    with open('config.yaml', 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    return config['database']

@contextmanager
def get_db_connection() -> Generator[Any, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

def initialize_db() -> None:
    """Initialize SQLAlchemy database connection"""
    global engine, Session
    
    config = load_db_config()
    
    if config['type'] == 'postgresql':
        db_url = f"postgresql+psycopg2://{config['postgresql']['user']}:{config['postgresql']['password']}@{config['postgresql']['host']}:{config['postgresql']['port']}/{config['postgresql']['database']}"
    else:  # SQLite
        db_url = f"sqlite:///{config['sqlite']['database']}"
        os.makedirs(os.path.dirname(config['sqlite']['database']), exist_ok=True)
    
    if config['type'] == 'postgresql':
        engine = create_engine(db_url, pool_size=20, max_overflow=0)
    else:
        engine = create_engine(db_url, pool_size=20, max_overflow=0,
                        connect_args={"check_same_thread": False})
    
    Session = scoped_session(sessionmaker(bind=engine))
    
    # Register cleanup on program exit
    import atexit
    atexit.register(close_db)
    
    print(f"Database connected: {db_url}")

def close_db() -> None:
    """Close database connection"""
    global engine, Session
    if engine:
        try:
            Session.remove()
            engine.dispose()
            print("Database connection closed successfully")
        except Exception as e:
            print(f"Error closing database connection: {e}")
        finally:
            engine = None
            Session = None
