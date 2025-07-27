from pygit2.repository import Repository
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    inspect,
    text,
    Index,
)
from sqlalchemy.ext.declarative import declarative_base

from database.connection import session_scope
from git.utils import get_git_file_snapshot

# SQLAlchemy setup
Base = declarative_base()


def create_tables(engine):
    """Create all tables in the database, if any tables already exist, this will be skiped and print log."""
    if engine is None:
        raise RuntimeError(
            "Database engine is not initialized. Please call initialize_db() first."
        )

    # Get tables from database
    existing_tables = inspect(engine).get_table_names()
    if existing_tables and len(existing_tables) > 0:
        print(f"Tables already exist: {existing_tables}. Skipping table creation.")
        return
    Base.metadata.create_all(engine)
    print(f"Table created successfully.")


def reset_tables(engine):
    """Reset database by dropping and recreating all tables"""
    if engine is None:
        raise RuntimeError(
            "Database engine is not initialized. Please call initialize_db() first."
        )

    # 定义表删除顺序（确保依赖表在前）
    table_order = [
        "git_file_snapshot",
        "git_analysis_result",
        "git_diff_result",
        "git_commit_file",
        "git_commit",
    ]

    try:
        with engine.connect() as conn:
            conn = conn.execution_options(isolation_level="AUTOCOMMIT")
            for table in table_order:
                print(f"DROP TABLE IF EXISTS {table};")
                conn.execute(text(f"DROP TABLE IF EXISTS {table};"))
        create_tables(engine)
    except Exception as e:
        print(f"An error occurred: {e}")


class FileSnapshot(Base):
    __tablename__ = "git_file_snapshot"
    id = Column(Integer, primary_key=True)
    commit_file_hash = Column(String(255), nullable=False)
    content_snapshot = Column(Text)


class AnalysisResult(Base):
    __tablename__ = "git_analysis_result"
    __table_args__ = (
        Index(
            "idx_commit_file_analyzer",
            "commit_hash",
            "path",
            "analyzer_type",
            unique=True,
        ),
    )
    id = Column(Integer, primary_key=True)
    commit_hash = Column(String(255), nullable=False)
    path = Column(Text)
    analyzer_type = Column(String(255), nullable=False)
    count = Column(Integer)
    content = Column(JSON)


class Commit(Base):
    __tablename__ = "git_commit"
    id = Column(Integer, primary_key=True)
    repository = Column(Text)
    branch = Column(String(255))
    hash = Column(String(255), nullable=False)
    message = Column(Text)
    author_name = Column(String(255))
    author_email = Column(String(255))
    author_date = Column(DateTime)
    committer_name = Column(String(255))
    committer_email = Column(String(255))
    commit_date = Column(DateTime)

    def is_exists(self) -> bool:
        try:
            # 查询是否存在指定hash的提交
            with session_scope() as session:
                result = session.query(Commit).filter(Commit.hash == self.hash).count()
                return result > 0
        except Exception as e:
            print(f"检查提交是否存在失败: {str(e)}")
            raise


class CommitFile(Base):
    __tablename__ = "git_commit_file"
    __table_args__ = (
        Index(
            "idx_hash_path",
            "commit_hash",
            "path",
            unique=True,
        ),
    )
    id = Column(Integer, primary_key=True)
    commit_hash = Column(String(255), nullable=False)
    path = Column(Text)
    tech_stack = Column(String(255))
    hash = Column(String(255), nullable=False)

    def is_exists(self) -> bool:
        try:
            # 查询是否存在指定hash和path的提交
            with session_scope() as session:
                result = (
                    session.query(CommitFile)
                    .filter(
                        CommitFile.commit_hash == self.commit_hash
                        and CommitFile.path == self.path
                    )
                    .count()
                )
                return result > 0
        except Exception as e:
            print(f"检查提交是否存在失败: {str(e)}")
            raise

    def get_file_git_snapshot(self, repo: Repository) -> str:
        if self.hash is not None:
            return get_git_file_snapshot(str(self.hash), repo)

        return "<invalid>"


class DiffResult(Base):
    __tablename__ = "git_diff_result"
    __table_args__ = (
        Index(
            "idx_base_target_hash",
            "base_commit_hash",
            "target_commit_hash",
            "target_path",
            unique=True,
        ),
    )
    id = Column(Integer, primary_key=True)
    base_commit_hash = Column(String(255))
    target_commit_hash = Column(String(255))
    base_path = Column(Text)
    target_path = Column(Text)
    diff_change_type = Column(String(30))
    base_tech_stack = Column(String(255))
    target_tech_stack = Column(String(255))
    base_file_hash = Column(String(255))
    target_file_hash = Column(String(255))
    hunk_char_count = Column(Integer)
    hunk_line_count = Column(Integer)

    def get_base_file_git_snapshot(self, repo: Repository) -> str:
        if self.hash is not None:
            return get_git_file_snapshot(str(self.base_file_hash), repo)

        return "<invalid>"

    def get_target_file_git_snapshot(self, repo: Repository) -> str:
        if self.hash is not None:
            return get_git_file_snapshot(str(self.target_file_hash), repo)

        return "<invalid>"
