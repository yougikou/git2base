from sqlalchemy import JSON, create_engine, Column, Integer, String, Text, DateTime, ForeignKey, func, inspect, text
from sqlalchemy.orm import sessionmaker, scoped_session, aliased
from sqlalchemy.ext.declarative import declarative_base
from contextlib import contextmanager

@contextmanager
def get_db_connection():
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

import yaml
from contextlib import contextmanager
import json
import os

# SQLAlchemy setup
Base = declarative_base()
engine = None
Session = None

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

# Load database configuration
def load_db_config():
    with open('config.yaml', 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    return config['database']

def load_analyzer_config():
    with open('config.yaml', 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    return config['analyzers']

def initialize_db():
    """Initialize SQLAlchemy database connection"""
    global engine, Session
    
    config = load_db_config()
    
    # Determine database URL based on config type
    if config['type'] == 'postgresql':
        db_url = f"postgresql+psycopg2://{config['postgresql']['user']}:{config['postgresql']['password']}@{config['postgresql']['host']}:{config['postgresql']['port']}/{config['postgresql']['database']}"
    else:  # SQLite
        db_url = f"sqlite:///{config['sqlite']['database']}"
        # Create directory for SQLite if needed
        os.makedirs(os.path.dirname(config['sqlite']['database']), exist_ok=True)
    
    if config['type'] == 'postgresql':
        engine = create_engine(db_url, pool_size=20, max_overflow=0)
    else:
        # SQLite specific configuration
        engine = create_engine(db_url, pool_size=20, max_overflow=0,
                        connect_args={"check_same_thread": False})
    
    Session = scoped_session(sessionmaker(bind=engine))
    
    # Create tables if they don't exist
    Base.metadata.create_all(engine)
    
    # Register cleanup on program exit
    import atexit
    atexit.register(close_db)
    
    print(f"Database connected: {db_url}")

def close_db():
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


# Database operations SQL
# 缓存已创建的模型类
_analyzer_model_cache = {}

def create_analyzer_result_model(analyzer_name: str) -> type:
    """Dynamically create analyzer result model class with caching
    
    Args:
        analyzer_name: Name of the analyzer
        
    Returns:
        type: SQLAlchemy model class for the analyzer results
        
    Note:
        This function caches created models to ensure consistent types
        and improve performance when called multiple times with the same
        analyzer name.
    """
    # 检查缓存
    if analyzer_name in _analyzer_model_cache:
        return _analyzer_model_cache[analyzer_name]
        
    # 创建新模型类
    class_name = f"{analyzer_name.capitalize()}Result"
    model = type(
        class_name,
        (AnalyzerResultBase,),
        {
            "__tablename__": f"{analyzer_name.lower()}_result",
            "__table_args__": {"extend_existing": True}
        }
    )
    
    # 缓存模型类
    _analyzer_model_cache[analyzer_name] = model
    
    return model

def reset_database():
    """Reset database by dropping and recreating all tables"""
    config = load_db_config()

    # 获取所有表名
    inspector = inspect(engine)
    all_tables = inspector.get_table_names()

    # 定义表删除顺序（确保依赖表在前）
    core_tables = [
        "git_diff_file",
        "git_file", 
        "git_commit"
    ]

    # 获取所有analyzer结果表（以analyzer name开头，以_result结尾）
    analyzer_tables = [
        table for table in all_tables
        if table.endswith('_result') and table != 'git_diff_file'
    ]

    # 合并表删除顺序
    table_order = analyzer_tables + core_tables

    try:
        with engine.connect() as conn:
            conn = conn.execution_options(isolation_level="AUTOCOMMIT")
            for table in table_order:
                print(f"DROP TABLE IF EXISTS {table};")
                conn.execute(text(f"DROP TABLE IF EXISTS {table};"))
        
        # 重新创建核心表
        Base.metadata.create_all(engine)
        print(f"Table created (core): {', '.join(core_tables)}")
        
        # 动态创建并注册analyzer结果表模型
        for analyzer in load_analyzer_config():
            analyzer_name = analyzer['name'].lower()
            table_name = f"{analyzer_name}_result"
            
            model = create_analyzer_result_model(analyzer_name)
            model.__table__.create(engine)
            print(f"Table created (analysis result): {table_name}")
        
        print("Database reset complete")
    except Exception as e:
        print(f"An error occurred: {e}")

def get_commit_id(commit_hash):
    session = Session()
    try:
        result = session.query(GitCommit.id)\
            .filter(GitCommit.commit_hash == commit_hash)\
            .first()
        if result:
            return result[0]
        else:
            raise ValueError(f"Commit hash {commit_hash} not found in git_commit table.")
    finally:
        session.close()

def insert_commit(commit_data):
    session = Session()
    try:
        # 创建新的GitCommit对象
        from datetime import datetime
        commit = GitCommit(
            commit_hash=commit_data['commit_hash'],
            branch=commit_data['branch'],
            commit_date=datetime.fromtimestamp(commit_data['commit_date']),
            commit_message=commit_data['commit_message'],
            author_name=commit_data['author_name'],
            author_email=commit_data['author_email']
        )
        
        # 添加到session并提交
        session.add(commit)
        session.commit()
        
        # 返回新插入的commit ID
        return commit.id
    except Exception as e:
        session.rollback()
        print(f"插入提交记录失败: {str(e)}")
        raise
    finally:
        session.close()

def insert_diff_file(diff_file_data):
    session = Session()
    try:
        # 创建新的GitDiffFile对象
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
        
        # 添加到session并提交
        session.add(diff_file)
        session.commit()
        
        # 返回新插入的diff文件ID
        return diff_file.id
    except Exception as e:
        session.rollback()
        print(f"插入diff文件记录失败: {str(e)}")
        raise
    finally:
        session.close()

def insert_diff_files(diff_files_data):
    session = Session()
    try:
        # 批量创建GitDiffFile对象
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
        
        # 批量添加到session并提交
        session.bulk_save_objects(diff_files)
        session.commit()
        
        # 返回插入的记录数
        return len(diff_files)
    except Exception as e:
        session.rollback()
        print(f"批量插入diff文件记录失败: {str(e)}")
        raise
    finally:
        session.close()

def remove_diff_file_snapshot(diff_id):
    session = Session()
    try:
        # 获取要更新的diff文件
        diff_file = session.query(GitDiffFile)\
            .filter(GitDiffFile.id == diff_id)\
            .first()
        
        if diff_file:
            # 清空快照内容
            diff_file.content_snapshot1 = None
            diff_file.content_snapshot2 = None
            session.commit()
    except Exception as e:
        session.rollback()
        print(f"清除diff文件快照失败: {str(e)}")
        raise
    finally:
        session.close()

def insert_commit_and_files(commit_data, file_data_list):
    session = Session()
    try:
        # 创建并插入提交记录
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
        session.flush()  # 获取commit ID
        
        # 批量创建并插入文件记录
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
        print(f"插入提交及文件记录失败: {str(e)}")
        raise
    finally:
        session.close()

def get_latest_commit_hash_from_db(branch):
    """获取指定分支的最新提交hash
    
    Args:
        branch: 分支名称
        
    Returns:
        str: 最新提交的hash值，如果分支不存在则返回None
    """
    session = Session()
    try:
        # 查询指定分支的最新提交
        result = session.query(GitCommit.commit_hash)\
            .filter(GitCommit.branch == branch)\
            .order_by(GitCommit.commit_date.desc())\
            .first()
            
        return result[0] if result else None
    except Exception as e:
        print(f"获取最新提交hash失败: {str(e)}")
        raise
    finally:
        session.close()

def commit_exists_in_db(commit_hash):
    """检查提交是否已存在于数据库中
    
    Args:
        commit_hash: 提交的hash值
        
    Returns:
        bool: 如果提交存在返回True，否则返回False
    """
    session = Session()
    try:
        # 查询是否存在指定hash的提交
        result = session.query(GitCommit)\
            .filter(GitCommit.commit_hash == commit_hash)\
            .first()
            
        return result is not None
    except Exception as e:
        print(f"检查提交是否存在失败: {str(e)}")
        raise
    finally:
        session.close()

def get_diff_data(commit_hash1, commit_hash2):
    """获取两个提交之间的差异数据
    
    Args:
        commit_hash1: 第一个提交的hash值
        commit_hash2: 第二个提交的hash值
        
    Returns:
        list: 包含所有差异文件的列表，如果没有差异则返回空列表
    """
    session = Session()
    try:
        # 创建GitCommit表的别名
        commit1 = aliased(GitCommit)
        commit2 = aliased(GitCommit)
        
        # 通过join GitCommit表将commit_hash转换为id
        result = session.query(GitDiffFile)\
            .join(commit1, GitDiffFile.commit_1_id == commit1.id)\
            .filter(commit1.commit_hash == commit_hash1)\
            .join(commit2, GitDiffFile.commit_2_id == commit2.id)\
            .filter(commit2.commit_hash == commit_hash2)\
            .all()
            
        return result
    except Exception as e:
        print(f"获取差异数据失败: {str(e)}")
        raise
    finally:
        session.close()

def save_analysis_result(analyzer_name: str, diff_id: int, commit_1_id: int, commit_2_id: int, count1: int, result1: dict, count2: int, result2: dict) -> bool:
    """Securely save analysis results with validation
    
    Args:
        analyzer_name: Name of the analyzer (must be alphanumeric with underscores)
        diff_id: ID of the diff file
        commit_1_id: ID of the first commit
        commit_2_id: ID of the second commit
        count1: Analysis count for first commit
        result1: Analysis result dict for first commit
        count2: Analysis count for second commit
        result2: Analysis result dict for second commit
        
    Returns:
        bool: True if successful, False if failed
    """
    # Validate analyzer name to prevent SQL injection
    if not isinstance(analyzer_name, str) or not analyzer_name.replace('_', '').isalnum():
        raise ValueError(f"Invalid analyzer name: {analyzer_name}")
        
    # Validate IDs are positive integers
    if not all(isinstance(id, int) and id > 0 for id in [diff_id, commit_1_id, commit_2_id]):
        raise ValueError("IDs must be positive integers")
        
    session = Session()
    try:
        # 动态创建模型类
        model = create_analyzer_result_model(analyzer_name)
        
        # 检查表是否存在
        inspector = inspect(engine)
        if model.__tablename__ not in inspector.get_table_names():
            # 如果表不存在则创建
            model.__table__.create(engine)
        
        # 插入第一条结果
        result1_obj = model(
            diff_file_id=diff_id,
            commit_id=commit_1_id,
            count=count1,
            content=result1
        )
        session.add(result1_obj)
        
        # 插入第二条结果
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
        print(f"保存分析结果失败: {str(e)}")
        return False
    finally:
        session.close()
    
def analysis_exists(analyzer_name: str, diff_id: int) -> bool:
    """检查指定分析器是否已经分析过某个diff文件
    
    Args:
        analyzer_name: 分析器名称
        diff_id: diff文件ID
        
    Returns:
        bool: 如果已经分析过返回True，否则返回False
    """
    session = Session()
    try:
        # 验证分析器名称合法性
        if not isinstance(analyzer_name, str) or not analyzer_name.replace('_', '').isalnum():
            raise ValueError(f"Invalid analyzer name: {analyzer_name}")
            
        # 验证diff_id是否为正整数
        if not isinstance(diff_id, int) or diff_id <= 0:
            raise ValueError("diff_id must be a positive integer")
            
        # 动态创建模型类
        model = create_analyzer_result_model(analyzer_name)
        
        # 检查表是否存在
        inspector = inspect(engine)
        if model.__tablename__ not in inspector.get_table_names():
            return False
            
        # 使用SQLAlchemy的exists查询
        exists = session.query(
            session.query(model)
            .filter_by(diff_file_id=diff_id)
            .exists()
        ).scalar()
        
        return exists
    except Exception as e:
        print(f"检查分析结果是否存在失败: {str(e)}")
        raise
    finally:
        session.close()
