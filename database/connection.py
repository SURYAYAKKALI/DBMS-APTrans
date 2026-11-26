"""
TransactionGuard Database Connection Manager
Supports both PostgreSQL and SQLite (with WAL mode & multi-session isolation emulation)
"""

import os
import sqlite3
import threading
from typing import Optional, Dict, Any, Generator
from contextlib import contextmanager
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import QueuePool, StaticPool

Base = declarative_base()

DEFAULT_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transactionguard.db")
DEFAULT_DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_DB_FILE}?check_same_thread=False")

class DatabaseManager:
    _instance: Optional['DatabaseManager'] = None
    _lock = threading.Lock()

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or DEFAULT_DATABASE_URL
        self.is_sqlite = "sqlite" in self.db_url
        self.is_postgres = "postgresql" in self.db_url or "postgres" in self.db_url
        self.is_mysql = "mysql" in self.db_url
        
        self._init_engine()

    def _init_engine(self):
        if self.is_sqlite:
            # Multi-threading SQLite configuration with WAL mode
            self.engine = create_engine(
                self.db_url,
                connect_args={"check_same_thread": False, "timeout": 30.0},
                poolclass=QueuePool,
                pool_size=20,
                max_overflow=30
            )

            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                cursor.execute("PRAGMA busy_timeout=15000;")
                cursor.close()
        elif self.is_postgres or self.is_mysql:
            # PostgreSQL or MySQL official database engine
            self.engine = create_engine(
                self.db_url,
                poolclass=QueuePool,
                pool_size=20,
                max_overflow=30,
                pool_pre_ping=True
            )
        else:
            self.engine = create_engine(self.db_url, pool_pre_ping=True)

        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    @classmethod
    def get_instance(cls, db_url: Optional[str] = None) -> 'DatabaseManager':
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db_url)
            elif db_url and cls._instance.db_url != db_url:
                cls._instance = cls(db_url)
            return cls._instance

    @classmethod
    def switch_database(cls, db_url: str) -> 'DatabaseManager':
        """Dynamically switches the active database connection to any official DB"""
        with cls._lock:
            cls._instance = cls(db_url)
            cls._instance.init_database()
            return cls._instance

    def get_raw_connection(self, isolation_level: str = "READ COMMITTED"):
        """
        Creates an independent database connection configured with a specific isolation level.
        Supports PostgreSQL, MySQL/MariaDB, and SQLite.
        """
        if self.is_postgres:
            conn = self.engine.raw_connection()
            iso_map = {
                "READ COMMITTED": "READ COMMITTED",
                "REPEATABLE READ": "REPEATABLE READ",
                "SERIALIZABLE": "SERIALIZABLE",
                "READ UNCOMMITTED": "READ UNCOMMITTED"
            }
            target_iso = iso_map.get(isolation_level.upper(), "READ COMMITTED")
            conn.set_isolation_level(target_iso)
            return conn
        elif self.is_mysql:
            conn = self.engine.raw_connection()
            cursor = conn.cursor()
            cursor.execute(f"SET SESSION TRANSACTION ISOLATION LEVEL {isolation_level.upper()}")
            cursor.close()
            return conn
        else:
            # SQLite raw connection
            db_path = self.db_url.replace("sqlite:///", "").split("?")[0]
            conn = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA busy_timeout=15000;")
            cursor.close()
            return conn

    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def init_database(self, force_recreate: bool = False):
        """Initializes tables from schema.sql and populates seed data"""
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
        seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed.sql")

        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        with open(seed_path, "r", encoding="utf-8") as f:
            seed_sql = f.read()

        with self.engine.connect() as conn:
            # Execute statement by statement
            for statement in schema_sql.split(";"):
                stmt = statement.strip()
                if stmt:
                    try:
                        conn.execute(text(stmt))
                    except Exception as e:
                        # Log or ignore table already exists in case of postgres types
                        pass
            
            # Execute seed data
            for statement in seed_sql.split(";"):
                stmt = statement.strip()
                if stmt:
                    try:
                        conn.execute(text(stmt))
                    except Exception as e:
                        pass
            conn.commit()

# Singleton shortcut
db_manager = DatabaseManager.get_instance()
