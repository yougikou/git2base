from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    JSON,
    inspect,
    text,
    Index,
)
from sqlalchemy.ext.declarative import declarative_base

from git2base.database import session_scope

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

    def to_dict(self) -> dict[str, str]:
        return {
            "commit_hash": str(self.commit_hash) if self.commit_hash is not None else "",
            "path": str(self.path) if self.path is not None else "",
            "analyzer_type": str(self.analyzer_type) if self.analyzer_type is not None else "",
            "count": str(self.count) if self.count is not None else "",
            "content": str(self.content) if self.content is not None else "",
        }


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

    def to_dict(self) -> dict[str, str]:
        return {
            "repository": str(self.repository) if self.repository is not None else "",
            "branch": str(self.branch) if self.branch is not None else "",
            "hash": str(self.hash) if self.hash is not None else "",
            "message": str(self.message) if self.message is not None else "",
            "author_name": str(self.author_name) if self.author_name is not None else "",
            "author_email": str(self.author_email) if self.author_email is not None else "",
            "author_date": self.author_date.isoformat() if self.author_date is not None else "",
            "committer_name": str(self.committer_name) if self.committer_name is not None else "",
            "committer_email": str(self.committer_email) if self.committer_email is not None else "",
            "commit_date": self.commit_date.isoformat() if self.commit_date is not None else "",
        }


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

    def to_dict(self) -> dict[str, str]:
        return {
            "commit_hash": str(self.commit_hash) if self.commit_hash is not None else "",
            "path": str(self.path) if self.path is not None else "",
            "tech_stack": str(self.tech_stack) if self.tech_stack is not None else "",
            "hash": str(self.hash) if self.hash is not None else "",
        }


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

    def to_dict(self) -> dict[str, str]:
        return {
            "base_commit_hash": str(self.base_commit_hash) if self.base_commit_hash is not None else "",
            "target_commit_hash": str(self.target_commit_hash) if self.target_commit_hash is not None else "",
            "base_path": str(self.base_path) if self.base_path is not None else "",
            "target_path": str(self.target_path) if self.target_path is not None else "",
            "diff_change_type": str(self.diff_change_type) if self.diff_change_type is not None else "",
            "base_tech_stack": str(self.base_tech_stack) if self.base_tech_stack is not None else "",
            "target_tech_stack": str(self.target_tech_stack) if self.target_tech_stack is not None else "",
            "base_file_hash": str(self.base_file_hash) if self.base_file_hash is not None else "",
            "target_file_hash": str(self.target_file_hash) if self.target_file_hash is not None else "",
            "hunk_char_count": str(self.hunk_char_count) if self.hunk_char_count is not None else "",
            "hunk_line_count": str(self.hunk_line_count) if self.hunk_line_count is not None else "",
        }
