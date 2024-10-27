import psycopg2
from psycopg2 import pool
import yaml
from contextlib import contextmanager

# Load database configuration
def load_db_config():
    with open('config.yaml', 'r') as file:
        config = yaml.safe_load(file)
    return config['database']

# Create database connection pool
connection_pool = None

def initialize_connection_pool():
    global connection_pool
    config = load_db_config()
    try:
        connection_pool = psycopg2.pool.SimpleConnectionPool(1, 20, **config)
        if connection_pool:
            print("Connection pool created successfully")
    except Exception as e:
        print(f"Failed to create connection pool: {e}")
        raise

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
    create_tables_query = """
    DROP TABLE git_diff_files;
    DROP TABLE git_files;
    DROP TABLE git_commits;

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
        content_snapshot2 TEXT
    );
    """
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

def insert_diff_files(diff_files_data):
    query = """
    INSERT INTO git_diff_files (commit_hash1_id, commit_hash2_id, file_path, file_type, change_type, 
                                line_count1, char_length1, blob_hash1, content_snapshot1, 
                                line_count2, char_length2, blob_hash2, content_snapshot2)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(query, diff_files_data)
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