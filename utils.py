import yaml

def load_config():
    with open('config.yaml', 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    return config

def is_binary(blob):
    if isinstance(blob, bytes):
        return b'\0' in blob[:1024]
    return False

def calculate_file_metrics(file_content):
    line_count = len(file_content.splitlines())
    char_length = len(file_content)
    return char_length, line_count

def parse_short_hash(repo, short_hash):
    commit = repo.revparse_single(short_hash)
    return str(commit.id)
