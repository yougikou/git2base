import psycopg2
from psycopg2 import pool
import yaml
from contextlib import contextmanager
import json

# Load database configuration
def load_db_config():
    with open('config.yaml', 'r') as file:
        config = yaml.safe_load(file)
    return config['database']

def load_analyzer_config():
    with open('config.yaml', 'r') as file:
        config = yaml.safe_load(file)
    return config['analyzers']

# Create database connection pool with cleanup
connection_pool = None

def initialize_connection_pool():
    """Initialize the database connection pool with error handling and cleanup"""
    global connection_pool
    if connection_pool:
        return  # Already initialized
    
    config = load_db_config()
    try:
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=20,
            **config
        )
        if connection_pool:
            print("Connection pool created successfully")
            # Register cleanup on program exit
            import atexit
            atexit.register(close_connection_pool)
    except Exception as e:
        print(f"Failed to create connection pool: {e}")
        raise

def close_connection_pool():
    """Close all connections in the pool"""
    global connection_pool
    if connection_pool:
        try:
            connection_pool.closeall()
            print("Connection pool closed successfully")
        except Exception as e:
            print(f"Error closing connection pool: {e}")
        finally:
            connection_pool = None

# Get and return connection using context manager
@contextmanager
def get_db_connection():
    if not connection_pool:
        raise Exception("Connection pool is not initialized")
    connection = connection_pool.getconn()
    try:
        yield connection
    except Exception as e:
        connection.rollback()
        raise e
    else:
        connection.commit()
    finally:
        connection_pool.putconn(connection)

# Example usage of the improved database connection
initialize_connection_pool()

# Database operations SQL
def reset_database():
    # 首先删除所有以_results结尾的分析结果表
    drop_analyzer_tables_query = """
    DO $$ 
    DECLARE
        _table text;
    BEGIN
        FOR _table IN 
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name LIKE '%_results'
            AND table_schema = current_schema()
        LOOP
            EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(_table) || ' CASCADE';
        END LOOP;
    END $$;
    """

    # 然后创建基础表
    create_tables_query = """
    DROP TABLE IF EXISTS git_diff_files CASCADE;
    DROP TABLE IF EXISTS git_files CASCADE;
    DROP TABLE IF EXISTS git_commits CASCADE;

    CREATE TABLE IF NOT EXISTS git_commits (
        id SERIAL PRIMARY KEY,
        commit_hash VARCHAR(255) UNIQUE NOT NULL,
        branch VARCHAR(255),
        commit_date TIMESTAMP,
        commit_message TEXT,
        author_name VARCHAR(255),
        author_email VARCHAR(255)
    );
    
    CREATE TABLE IF NOT EXISTS git_files (
        id SERIAL PRIMARY KEY,
        commit_hash_id INTEGER REFERENCES git_commits(id),
        file_path TEXT,
        file_type VARCHAR(255),
        change_type CHAR(1),
        char_length INT,
        line_count INT,
        blob_hash VARCHAR(255)
    );
    
    CREATE TABLE IF NOT EXISTS git_diff_files (
        id SERIAL PRIMARY KEY,
        commit_hash1_id INTEGER REFERENCES git_commits(id),
        commit_hash2_id INTEGER REFERENCES git_commits(id),
        file_path TEXT,
        file_type VARCHAR(255),
        change_type CHAR(1),
        line_count1 INT,
        char_length1 INT,
        blob_hash1 VARCHAR(255),
        content_snapshot1 TEXT,
        line_count2 INT,
        char_length2 INT,
        blob_hash2 VARCHAR(255),
        content_snapshot2 TEXT,
        tech_stack VARCHAR(255)
    );    
    """

    # 最后创建分析结果表
    analyzers = load_analyzer_config()
    for analyzer in analyzers:
        create_tables_query = f"""
        {create_tables_query}
        CREATE TABLE IF NOT EXISTS {analyzer['name']}_results (
            id SERIAL PRIMARY KEY,
            diff_file_id INTEGER REFERENCES git_diff_files(id),
            commit_hash_id INTEGER REFERENCES git_commits(id),
            count INT,
            content TEXT
        );
        """
    
    # 将所有SQL语句合并
    create_tables_query = drop_analyzer_tables_query + create_tables_query

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(create_tables_query)
            conn.commit()

def get_commit_id(commit_hash):
    query = """
    SELECT id FROM git_commits WHERE commit_hash = %s
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (commit_hash,))
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                raise ValueError(f"Commit hash {commit_hash} not found in git_commits table.")

def insert_commit(commit_data):
    query = """
    INSERT INTO git_commits (commit_hash, branch, commit_date, commit_message, author_name, author_email)
    VALUES (%s, %s, to_timestamp(%s), %s, %s, %s)
    """
    params = (
        commit_data['commit_hash'],
        commit_data['branch'],
        commit_data['commit_date'],
        commit_data['commit_message'],
        commit_data['author_name'],
        commit_data['author_email']
    )
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute(query, params)
                # 获取插入的提交 ID
                cursor.execute("SELECT currval('git_commits_id_seq')")
                commit_id = cursor.fetchone()[0]
                conn.commit()
                return commit_id
            except psycopg2.Error as e:
                conn.rollback()
                print(f"Error inserting commit: {e}")
                raise

def insert_diff_file(diff_file_data):
    query = """
    INSERT INTO git_diff_files (commit_hash1_id, commit_hash2_id, file_path, file_type, change_type, 
                                line_count1, char_length1, blob_hash1, content_snapshot1, 
                                line_count2, char_length2, blob_hash2, content_snapshot2, tech_stack)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (
                diff_file_data['commit_hash1_id'],
                diff_file_data['commit_hash2_id'],
                diff_file_data['file_path'],
                diff_file_data['file_type'],
                diff_file_data['change_type'],
                diff_file_data['line_count1'],
                diff_file_data['char_length1'],
                diff_file_data['blob_hash1'],
                diff_file_data['content_snapshot1'],
                diff_file_data['line_count2'],
                diff_file_data['char_length2'],
                diff_file_data['blob_hash2'],
                diff_file_data['content_snapshot2'],
                diff_file_data['tech_stack']
            ))
            # 获取插入的提交 ID
            cursor.execute("SELECT currval('git_diff_files_id_seq')")
            commit_id = cursor.fetchone()[0]
            conn.commit()
            return commit_id

def insert_diff_files(diff_files_data):
    query = """
    INSERT INTO git_diff_files (commit_hash1_id, commit_hash2_id, file_path, file_type, change_type, 
                                line_count1, char_length1, blob_hash1, content_snapshot1, 
                                line_count2, char_length2, blob_hash2, content_snapshot2, tech_stack)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(query, diff_files_data)
            # 获取插入的提交 ID
            cursor.execute("SELECT currval('git_diff_files_id_seq')")
            commit_id = cursor.fetchone()[0]
            conn.commit()
            return commit_id

def remove_diff_file_snapshot(diff_id):
    query = """
    UPDATE git_diff_files SET content_snapshot1 = NULL, content_snapshot2 = NULL
    WHERE id = %s;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (diff_id,))
            conn.commit()

def insert_commit_and_files(commit_data, file_data_list):
    commit_query = """
    INSERT INTO git_commits (commit_hash, branch, commit_date, commit_message, author_name, author_email)
    VALUES (%s, %s, to_timestamp(%s), %s, %s, %s) RETURNING id
    """
    file_query = """
    INSERT INTO git_files (commit_hash_id, file_path, file_type, change_type, char_length, line_count, blob_hash)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(commit_query, (
                commit_data['commit_hash'],
                commit_data['branch'],
                commit_data['commit_date'],
                commit_data['commit_message'],
                commit_data['author_name'],
                commit_data['author_email']
            ))
            # 获取插入的提交 ID
            cursor.execute("SELECT currval('git_commits_id_seq')")
            commit_id = cursor.fetchone()[0]

            for file_data in file_data_list:
                cursor.execute(file_query, (
                    commit_id,
                    file_data['file_path'],
                    file_data['file_type'],
                    file_data['change_type'],
                    file_data['char_length'],
                    file_data['line_count'],
                    file_data['blob_hash']
                ))
            conn.commit()

def get_latest_commit_hash_from_db(branch):
    query = """
    SELECT commit_hash FROM git_commits WHERE branch = %s ORDER BY commit_date DESC LIMIT 1
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (branch,))
            result = cursor.fetchone()
            return result[0] if result else None

def commit_exists_in_db(commit_hash):
    query = """
    SELECT 1 FROM git_commits WHERE commit_hash = %s LIMIT 1
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (commit_hash,))
            result = cursor.fetchone()
            return result is not None

def get_diff_data(commit_hash1, commit_hash2):
    query = """
    SELECT * FROM git_diff_files WHERE commit_hash1_id = %s AND commit_hash2_id = %s
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (commit_hash1, commit_hash2))
            return cursor.fetchall()

def save_analysis_result(analyzer_name: str, diff_id: int, commit_hash1_id: int, commit_hash2_id: int, count1: int, result1: dict, count2: int, result2: dict) -> bool:
    """Securely save analysis results with validation
    
    Args:
        analyzer_name: Name of the analyzer (must be alphanumeric with underscores)
        diff_id: ID of the diff file
        commit_hash1_id: ID of the first commit
        commit_hash2_id: ID of the second commit
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
    if not all(isinstance(id, int) and id > 0 for id in [diff_id, commit_hash1_id, commit_hash2_id]):
        raise ValueError("IDs must be positive integers")
        
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Use parameterized table name with psycopg2's quote_ident
                table_name = psycopg2.extensions.quote_ident(analyzer_name.lower() + '_results', conn)
                
                insert_sql = f"""
                    INSERT INTO {table_name} (diff_file_id, commit_hash_id, count, content)
                    VALUES (%s, %s, %s, %s)
                """
                
                # Execute with parameterized values
                cursor.execute(insert_sql, (diff_id, commit_hash1_id, count1, json.dumps(result1)))
                cursor.execute(insert_sql, (diff_id, commit_hash2_id, count2, json.dumps(result2)))
                conn.commit()
                return True
                
    except Exception as e:
        print(f"保存分析结果失败: {str(e)}")
        return False
    
def analysis_exists(analyzer_name: str, diff_id: int) -> bool:
    query = f"SELECT 1 FROM {analyzer_name}_results WHERE diff_file_id = %s LIMIT 1"
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (diff_id,))
            return cursor.fetchone() is not None
