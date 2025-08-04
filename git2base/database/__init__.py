"""
Database package for git2base.
Provides database connection and operations.
"""

from git2base.database.connection import init_output, session_scope
from git2base.database.model import (
    create_tables,
    reset_tables,
    Commit,
    CommitFile,
    DiffResult,
    AnalysisResult,
    FileSnapshot,
)
from git2base.database.operation import (
    insert_commits,
    insert_commit_files,
    insert_diff_results,
    insert_analysis_results,
    insert_file_snapshot,
)

__all__ = [
    "init_output",
    "session_scope",
    "Commit",
    "CommitFile",
    "DiffResult",
    "AnalysisResult",
    "FileSnapshot",
    "create_tables",
    "reset_tables",
    "insert_commits",
    "insert_commit_files",
    "insert_diff_results",
    "insert_analysis_results",
    "insert_file_snapshot",
]
