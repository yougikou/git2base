from contextlib import contextmanager
from datetime import datetime
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import os
import sys

from git2base.config import load_output_config

# SQLAlchemy setup
engine = None
Session = None


def init_output(
    mode: str | None = None, run_dir_data: str | None = None
) -> Engine | None:
    """Initialize SQLAlchemy database connection"""
    global engine, Session, current_csv_path

    config = load_output_config()

    db_url = ""
    if config["type"] == "csv":
        if not mode or not run_dir_data:
            return None

        os.makedirs(run_dir_data, exist_ok=True)

        return None
    elif config["type"] == "postgresql":
        db_url = f"postgresql+psycopg2://{config['postgresql']['user']}:{config['postgresql']['password']}@{config['postgresql']['host']}:{config['postgresql']['port']}/{config['postgresql']['database']}"
        engine = create_engine(db_url, pool_size=20, max_overflow=0)
    elif config["type"] == "sqlite":
        db_url = f"sqlite:///{config['sqlite']['database']}"
        os.makedirs(os.path.dirname(config["sqlite"]["database"]), exist_ok=True)
        engine = create_engine(
            db_url,
            pool_size=20,
            max_overflow=0,
            connect_args={"check_same_thread": False},
        )
    else:
        print(f"Unsupport output setting: {config['type']}")

    Session = scoped_session(sessionmaker(bind=engine))

    # Register cleanup on program exit
    import atexit

    atexit.register(close_db)

    print(f"Database connected: {db_url}")

    from git2base.database.model import create_tables

    create_tables(engine)

    return engine


def get_session():
    """Get a new session"""
    if Session is None:
        raise RuntimeError(
            "Session is not initialized. Please call initialize_db() first."
        )
    return Session()


def close_db():
    """Close database connection"""
    global engine, Session
    if Session is None:
        raise RuntimeError(
            "Session is not initialized. Please call initialize_db() first."
        )

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


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
