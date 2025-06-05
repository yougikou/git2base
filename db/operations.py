from .models import Base, GitCommit, GitFile, GitDiffFile, AnalyzerResultBase
from .connection import Session, engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import aliased
import json

# 缓存已创建的模型类
_analyzer_model_cache = {}

def create_analyzer_result_model(analyzer_name: str) -> type:
    """Dynamically create analyzer result model class with caching"""
    if analyzer_name in _analyzer_model_cache:
        return _analyzer_model_cache[analyzer_name]
        
    class_name = f"{analyzer_name.capitalize()}Result"
    model = type(
        class_name,
        (AnalyzerResultBase,),
        {
            "__tablename__": f"{analyzer_name.lower()}_result",
            "__table_args__": {"extend_existing": True}
        }
    )
    
    _analyzer_model_cache[analyzer_name] = model
    return model

def reset_database():
    """Reset database by dropping and recreating all tables"""
    inspector = inspect(engine)
    all_tables = inspector.get_table_names()

    core_tables = [
        "git_diff_file",
        "git_file", 
        "git_commit"
    ]

    analyzer_tables = [
        table for table in all_tables
        if table.endswith('_result') and table != 'git_diff_file'
    ]

    table_order = analyzer_tables + core_tables

    try:
        with engine.connect() as conn:
            conn = conn.execution_options(isolation_level="AUTOCOMMIT")
            for table in table_order:
                conn.execute(text(f"DROP TABLE IF EXISTS {table};"))
        
        Base.metadata.create_all(engine)
        
        # 动态创建并注册analyzer结果表模型
        from ..git.config import load_analyzer_config
        for analyzer in load_analyzer_config():
            analyzer_name = analyzer['name'].lower()
            model = create_analyzer_result_model(analyzer_name)
            model.__table__.create(engine)
        
    except Exception as e:
        print(f"An error occurred: {e}")

def get_commit_id(commit_hash):
    session = Session()
    try:
        result = session.query(GitCommit.id)\
            .filter(GitCommit.commit_hash == commit_hash)\
            .first()
        return result[0] if result else None
    finally:
        session.close()

def insert_commit(commit_data):
    session = Session()
    try:
        from datetime import datetime
        commit = GitCommit(
            commit_hash=commit_data['commit_hash'],
            branch=commit_data['branch'],
            commit_date=datetime.fromtimestamp(commit_data['commit_date']),
            commit_message=commit_data['commit_message'],
            author_name=commit_data['author_name'],
            author_email=commit_data['author_email']
        )
        session.add(commit)
        session.commit()
        return commit.id
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

def insert_diff_file(diff_file_data):
    session = Session()
    try:
        diff_file = GitDiffFile(
            commit_1_id=diff_file_data['commit_1_id'],
            commit_2_id=diff_file_data['commit_2_id'],
            file_path=diff_file_data['file_path'],
            file_type=diff_file_data['file_type'],
            change_type=diff_file_data['change_type'],
            line_count1=diff_file_data['line_count1'],
            char_length1=diff_file_data['char_length1'],
            blob_hash1=diff_file_data['blob_hash1'],
            content_snapshot1=diff_file_data['content_snapshot1'],
            line_count2=diff_file_data['line_count2'],
            char_length2=diff_file_data['char_length2'],
            blob_hash2=diff_file_data['blob_hash2'],
            content_snapshot2=diff_file_data['content_snapshot2'],
            tech_stack=diff_file_data['tech_stack']
        )
        session.add(diff_file)
        session.commit()
        return diff_file.id
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

def insert_diff_files(diff_files_data):
    session = Session()
    try:
        diff_files = [
            GitDiffFile(
                commit_1_id=data['commit_1_id'],
                commit_2_id=data['commit_2_id'],
                file_path=data['file_path'],
                file_type=data['file_type'],
                change_type=data['change_type'],
                line_count1=data['line_count1'],
                char_length1=data['char_length1'],
                blob_hash1=data['blob_hash1'],
                content_snapshot1=data['content_snapshot1'],
                line_count2=data['line_count2'],
                char_length2=data['char_length2'],
                blob_hash2=data['blob_hash2'],
                content_snapshot2=data['content_snapshot2'],
                tech_stack=data['tech_stack']
            )
            for data in diff_files_data
        ]
        session.bulk_save_objects(diff_files)
        session.commit()
        return len(diff_files)
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

def remove_diff_file_snapshot(diff_id):
    session = Session()
    try:
        diff_file = session.query(GitDiffFile)\
            .filter(GitDiffFile.id == diff_id)\
            .first()
        if diff_file:
            diff_file.content_snapshot1 = None
            diff_file.content_snapshot2 = None
            session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

def insert_commit_and_files(commit_data, file_data_list):
    session = Session()
    try:
        from datetime import datetime
        commit = GitCommit(
            commit_hash=commit_data['commit_hash'],
            branch=commit_data['branch'],
            commit_date=datetime.fromtimestamp(commit_data['commit_date']),
            commit_message=commit_data['commit_message'],
            author_name=commit_data['author_name'],
            author_email=commit_data['author_email']
        )
        session.add(commit)
        session.flush()
        
        files = [
            GitFile(
                commit_id=commit.id,
                file_path=file_data['file_path'],
                file_type=file_data['file_type'],
                change_type=file_data['change_type'],
                char_length=file_data['char_length'],
                line_count=file_data['line_count'],
                blob_hash=file_data['blob_hash']
            )
            for file_data in file_data_list
        ]
        session.bulk_save_objects(files)
        session.commit()
        return commit.id
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

def get_latest_commit_hash_from_db(branch):
    session = Session()
    try:
        result = session.query(GitCommit.commit_hash)\
            .filter(GitCommit.branch == branch)\
            .order_by(GitCommit.commit_date.desc())\
            .first()
        return result[0] if result else None
    except Exception as e:
        raise
    finally:
        session.close()

def commit_exists_in_db(commit_hash):
    session = Session()
    try:
        result = session.query(GitCommit)\
            .filter(GitCommit.commit_hash == commit_hash)\
            .first()
        return result is not None
    except Exception as e:
        raise
    finally:
        session.close()

def get_diff_data(commit_hash1, commit_hash2):
    session = Session()
    try:
        commit1 = aliased(GitCommit)
        commit2 = aliased(GitCommit)
        
        result = session.query(GitDiffFile)\
            .join(commit1, GitDiffFile.commit_1_id == commit1.id)\
            .filter(commit1.commit_hash == commit_hash1)\
            .join(commit2, GitDiffFile.commit_2_id == commit2.id)\
            .filter(commit2.commit_hash == commit_hash2)\
            .all()
        return result
    except Exception as e:
        raise
    finally:
        session.close()

def save_analysis_result(analyzer_name: str, diff_id: int, commit_1_id: int, commit_2_id: int, count1: int, result1: dict, count2: int, result2: dict) -> bool:
    if not isinstance(analyzer_name, str) or not analyzer_name.replace('_', '').isalnum():
        raise ValueError(f"Invalid analyzer name: {analyzer_name}")
        
    if not all(isinstance(id, int) and id > 0 for id in [diff_id, commit_1_id, commit_2_id]):
        raise ValueError("IDs must be positive integers")
        
    session = Session()
    try:
        model = create_analyzer_result_model(analyzer_name)
        
        inspector = inspect(engine)
        if model.__tablename__ not in inspector.get_table_names():
            model.__table__.create(engine)
        
        result1_obj = model(
            diff_file_id=diff_id,
            commit_id=commit_1_id,
            count=count1,
            content=result1
        )
        session.add(result1_obj)
        
        result2_obj = model(
            diff_file_id=diff_id,
            commit_id=commit_2_id,
            count=count2,
            content=result2
        )
        session.add(result2_obj)
        
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        return False
    finally:
        session.close()
    
def analysis_exists(analyzer_name: str, diff_id: int) -> bool:
    session = Session()
    try:
        if not isinstance(analyzer_name, str) or not analyzer_name.replace('_', '').isalnum():
            raise ValueError(f"Invalid analyzer name: {analyzer_name}")
            
        if not isinstance(diff_id, int) or diff_id <= 0:
            raise ValueError("diff_id must be a positive integer")
            
        model = create_analyzer_result_model(analyzer_name)
        
        inspector = inspect(engine)
        if model.__tablename__ not in inspector.get_table_names():
            return False
            
        exists = session.query(
            session.query(model)
            .filter_by(diff_file_id=diff_id)
            .exists()
        ).scalar()
        
        return exists
    except Exception as e:
        raise
    finally:
        session.close()
