from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

# Define base analyzer result model
class AnalyzerResultBase(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True)
    diff_file_id = Column(Integer, ForeignKey('git_diff_file.id'), nullable=False)
    commit_id = Column(Integer, ForeignKey('git_commit.id'), nullable=False)
    count = Column(Integer, nullable=False)
    content = Column(JSON, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

# Define database models
class GitCommit(Base):
    __tablename__ = 'git_commit'
    id = Column(Integer, primary_key=True)
    commit_hash = Column(String(255), unique=True, nullable=False)
    branch = Column(String(255))
    commit_date = Column(DateTime)
    commit_message = Column(Text)
    author_name = Column(String(255))
    author_email = Column(String(255))

class GitFile(Base):
    __tablename__ = 'git_file'
    id = Column(Integer, primary_key=True)
    commit_id = Column(Integer, ForeignKey('git_commit.id'))
    file_path = Column(Text)
    file_type = Column(String(255))
    change_type = Column(String(1))
    char_length = Column(Integer)
    line_count = Column(Integer)
    blob_hash = Column(String(255))

class GitDiffFile(Base):
    __tablename__ = 'git_diff_file'
    id = Column(Integer, primary_key=True)
    commit_1_id = Column(Integer, ForeignKey('git_commit.id'))
    commit_2_id = Column(Integer, ForeignKey('git_commit.id'))
    file_path = Column(Text)
    file_type = Column(String(255))
    change_type = Column(String(1))
    line_count1 = Column(Integer)
    char_length1 = Column(Integer)
    blob_hash1 = Column(String(255))
    content_snapshot1 = Column(Text)
    line_count2 = Column(Integer)
    char_length2 = Column(Integer)
    blob_hash2 = Column(String(255))
    content_snapshot2 = Column(Text)
    tech_stack = Column(String(255))
