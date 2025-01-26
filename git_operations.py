import os
import importlib
import threading
import pygit2
import yaml
from db_operations import get_commit_id, insert_commit, commit_exists_in_db, insert_commit_and_files, insert_diff_file, get_diff_data,save_analysis_result, analysis_exists, remove_diff_file_snapshot
from tqdm import tqdm
from utils import is_binary, calculate_file_metrics

# Cached configuration with thread safety and validation
_config_cache = None
_config_last_modified = 0
_config_lock = threading.Lock()

def _load_config():
    """Load and cache the configuration file with thread safety and validation
    
    Returns:
        dict: Parsed configuration
        
    Raises:
        RuntimeError: If config file is missing or invalid
        ValueError: If config is malformed
    """
    global _config_cache, _config_last_modified
    
    try:
        mod_time = os.path.getmtime('config.yaml')
        with _config_lock:
            if _config_cache is None or mod_time > _config_last_modified:
                try:
                    with open('config.yaml', 'r') as file:
                        config = yaml.safe_load(file)
                        if not isinstance(config, dict):
                            raise ValueError("Config must be a dictionary")
                            
                        # Validate required sections
                        required_sections = ['database', 'analyzers', 'stacks']
                        for section in required_sections:
                            if section not in config:
                                raise ValueError(f"Missing required config section: {section}")
                                
                        _config_cache = config
                        _config_last_modified = mod_time
                except yaml.YAMLError as e:
                    raise ValueError(f"Invalid YAML in config: {str(e)}")
                except OSError as e:
                    raise RuntimeError(f"Failed to read config file: {str(e)}")
                    
            return _config_cache
            
    except Exception as e:
        raise RuntimeError(f"Configuration error: {str(e)}")

def load_stacks_config():
    """Load stacks configuration from cached config"""
    config = _load_config()
    return config.get('stacks', [])

def load_analyzer_config():
    """Load analyzer configuration from cached config"""
    config = _load_config()
    return config.get('analyzers', [])

# Mapping of Git delta status to change type
DELTA_STATUS_MAP = {
    pygit2.GIT_DELTA_ADDED: 'A',
    pygit2.GIT_DELTA_MODIFIED: 'M',
    pygit2.GIT_DELTA_DELETED: 'D',
    pygit2.GIT_DELTA_RENAMED: 'R',
    pygit2.GIT_DELTA_COPIED: 'C',
    pygit2.GIT_DELTA_UNMODIFIED: '=',
    pygit2.GIT_DELTA_UNTRACKED: '?',
    pygit2.GIT_DELTA_TYPECHANGE: 'T',
    pygit2.GIT_DELTA_UNREADABLE: '!',
    pygit2.GIT_DELTA_CONFLICTED: 'U'
}

def get_change_type(delta) -> str:
    """Get standardized change type from Git delta status
    
    Args:
        delta: Git delta object
        
    Returns:
        str: Single character representing change type
    """
    return DELTA_STATUS_MAP.get(delta.status, 'X')

def get_file_type(file_path):
    if file_path.startswith("."):
        return "<dev-config>"
    file_ext = file_path.split(".")[-1] if "." in file_path else ""
    return file_ext if file_ext else "<no-extension>"

def get_branch_name_for_commit(repo, commit_hash):
    try:
        branches = []
        for branch in repo.branches.local:
            branch_ref = repo.lookup_reference(f'refs/heads/{branch}')
            if branch_ref is not None:
                branch_target = branch_ref.target
                if branch_target == commit_hash:
                    branches.append(branch)
        if branches:
            return branches[0]  # 返回找到的第一个分支
        else:
            return 'unknown'  # 若未找到任何分支，返回 'unknown'
    except KeyError:
        return 'unknown'

def get_git_commits(repo: pygit2.Repository, branch: str, start_commit_hash: str = None) -> int:
    """Process git commits from a branch with robust error handling
    
    Args:
        repo: Initialized pygit2 repository
        branch: Branch name to process
        start_commit_hash: Optional commit hash to start from
        
    Returns:
        int: Number of commits successfully processed
        
    Raises:
        ValueError: For invalid branch or commit hash
        RuntimeError: For repository access errors
    """
    if not repo or not isinstance(repo, pygit2.Repository):
        raise ValueError("Invalid repository instance")
        
    if not branch or not isinstance(branch, str):
        raise ValueError("Invalid branch name")
        
    # Get branch reference with error handling
    branch_ref = repo.lookup_reference(f'refs/heads/{branch}')
    if not branch_ref:
        raise ValueError(f"Branch {branch} not found")
        
    # Create walker with error handling
    walker = repo.walk(branch_ref.target, pygit2.GIT_SORT_TIME)
    if start_commit_hash:
        try:
            start_commit = repo.revparse_single(start_commit_hash)
            walker.hide(start_commit.id)
        except KeyError:
            raise ValueError(f"Start commit {start_commit_hash} not found")
            
    # Calculate total commits safely
    total_commits = sum(1 for _ in walker)
    if total_commits == 0:
        return 0
        
    # Recreate walker for actual processing
    walker = repo.walk(branch_ref.target, pygit2.GIT_SORT_TIME | pygit2.GIT_SORT_REVERSE)
    
    # Initialize progress bar
    pbar = tqdm(
        total=total_commits,
        desc="Processing commits",
        unit="commit",
        bar_format="{desc}: {n_fmt}/{total_fmt} commits"
    )
    
    start_found = False if start_commit_hash else True
    
    for commit in walker:
        if not start_found:
            if str(commit.id) == start_commit_hash:
                start_found = True
            continue

        commit_data = {
            'commit_hash': str(commit.id),
            'branch': branch,
            'commit_date': commit.commit_time,
            'commit_message': commit.message,
            'author_name': commit.author.name,
            'author_email': commit.author.email,
        }

        # 获取提交的 diff
        if commit.parents:
            diff = commit.tree.diff_to_tree(commit.parents[0].tree)
        else:
            diff = commit.tree.diff_to_tree()

        files = []
        for delta in diff.deltas:
            file_path = delta.new_file.path if delta.status != pygit2.GIT_DELTA_DELETED else delta.old_file.path
            file_type = get_file_type(file_path)  # 使用新函数获取文件类型

            try:
                blob = repo[delta.new_file.id] if delta.status != pygit2.GIT_DELTA_DELETED else None
            except KeyError:
                # 如果无法找到对应的 blob，将内容标记为 <invalid>
                print(f"Warning: {file_path} Blob {delta.new_file.id} not found in repository, marking blob_hash as <invalid>.")
                blob = None
                blob_hash = '<invalid>'
                char_length = 0
                line_count = 0
            else:
                if blob and is_binary(blob.data):
                    blob_hash = str(blob.id) if blob else None
                    char_length = 0
                    line_count = 0
                elif blob:
                    blob_hash = str(blob.id) if blob else None
                    content = blob.data.decode('utf-8', 'ignore')
                    char_length, line_count = calculate_file_metrics(content)
                else:
                    blob_hash = '<deleted>'
                    char_length = 0
                    line_count = 0

            print(f"Debug: {file_path} - {delta.status}  - {commit.id} - {pygit2.GIT_DELTA_ADDED} ")

            file_data = {
                'file_path': file_path,
                'file_type': file_type,  # 使用新的文件类型
                'change_type': get_change_type(delta),  # 获取标准变更类型
                'char_length': char_length,
                'line_count': line_count,
                'blob_hash': blob_hash
            }
            files.append(file_data)

        # 更新 tqdm 的显示
        pbar.update(1)

        insert_commit_and_files(commit_data, files)

    # 完成后关闭进度条并打印结束信息
    pbar.close()
    print("所有提交处理完成")

def get_git_diff(repo, commit_hash1, commit_hash2, save_snapshot=True, run_analysis=False):
    stacks = load_stacks_config()
    analyzers = load_analyzer_config() if run_analysis else []
    loadedAnalyzers = {}
    for analyzer_config in analyzers:
        class_name = analyzer_config['class']
        module_name = f'analyzers.{class_name}'
        try:
            # 动态加载模块和类
            module = importlib.import_module(module_name)
            analyzer_class = getattr(module, class_name)
            loadedAnalyzers[class_name] = analyzer_class
        except (ImportError, AttributeError) as e:
            raise ImportError(f"Failed to load {class_name} from {module_name}: {e}")

    # Ensure commit_hash1 exists in the database, otherwise insert it
    commit1 = repo.get(commit_hash1)
    if not commit_exists_in_db(commit_hash1):
        branch_name1 = get_branch_name_for_commit(repo, commit_hash1)
        commit_data1 = {
            'commit_hash': commit_hash1,
            'branch': branch_name1,
            'commit_date': commit1.commit_time,
            'commit_message': commit1.message,
            'author_name': commit1.author.name,
            'author_email': commit1.author.email
        }
        commit_hash1_id = insert_commit(commit_data1)  # 获取插入的 commit_id
    else:
        commit_hash1_id = get_commit_id(commit_hash1)

    # Ensure commit_hash2 exists in the database, otherwise insert it
    commit2 = repo.get(commit_hash2)
    if not commit_exists_in_db(commit_hash2):
        branch_name2 = get_branch_name_for_commit(repo, commit_hash2)
        commit_data2 = {
            'commit_hash': commit_hash2,
            'branch': branch_name2,
            'commit_date': commit2.commit_time,
            'commit_message': commit2.message,
            'author_name': commit2.author.name,
            'author_email': commit2.author.email
        }
        commit_hash2_id = insert_commit(commit_data2)  # 获取插入的 commit_id
    else:
        commit_hash2_id = get_commit_id(commit_hash2)  # 已存在则直接获取 commit_id

    # Get the diff between the two commits
    diff = commit2.tree.diff_to_tree(commit1.tree)

    total_patches = len(diff)
    processed_count = 0
    diff_files_data = []

    with tqdm(total=total_patches, desc="Processing patches", unit="patch", bar_format="{desc}: {n_fmt}/{total_fmt} patches") as pbar:
        for patch in diff:
            file_path = patch.delta.new_file.path if patch.delta.new_file.path else patch.delta.old_file.path

            # 跳过以 . 开头的路径
            if file_path.startswith('.'):
                continue

            file_type = file_type = get_file_type(file_path)
            tech_stack = identify_tech_stack(file_path, stacks)

            # 获取变更类型
            change_type = get_change_type(patch.delta)

            try:
                if change_type == 'A':  # Added
                    # 新增文件：只存在 new_file
                    blob2 = repo[patch.delta.new_file.id]
                    snapshot1 = '<added>'
                    snapshot2 = blob2.data.decode('utf-8', 'ignore').replace('\x00', '') if not is_binary(blob2.data) else '<binary>'
                    char_length1 = 0
                    char_length2 = len(snapshot2) if snapshot2 != '<binary>' else 0
                    line_count1 = 0
                    line_count2 = len(snapshot2.splitlines()) if snapshot2 != '<binary>' else 0

                elif change_type == 'D':  # Deleted
                    # 删除文件：只存在 old_file
                    blob1 = repo[patch.delta.old_file.id]
                    snapshot1 = blob1.data.decode('utf-8', 'ignore').replace('\x00', '') if not is_binary(blob1.data) else '<binary>'
                    snapshot2 = '<deleted>'
                    char_length1 = len(snapshot1) if snapshot1 != '<binary>' else 0
                    char_length2 = 0
                    line_count1 = len(snapshot1.splitlines()) if snapshot1 != '<binary>' else 0
                    line_count2 = 0

                elif change_type == 'M':  # Modified
                    # 修改文件：同时存在 old_file 和 new_file
                    blob1 = repo[patch.delta.old_file.id]
                    blob2 = repo[patch.delta.new_file.id]
                    snapshot1 = blob1.data.decode('utf-8', 'ignore').replace('\x00', '') if not is_binary(blob1.data) else '<binary>'
                    snapshot2 = blob2.data.decode('utf-8', 'ignore').replace('\x00', '') if not is_binary(blob2.data) else '<binary>'
                    char_length1 = len(snapshot1) if snapshot1 != '<binary>' else 0
                    char_length2 = len(snapshot2) if snapshot2 != '<binary>' else 0
                    line_count1 = len(snapshot1.splitlines()) if snapshot1 != '<binary>' else 0
                    line_count2 = len(snapshot2.splitlines()) if snapshot2 != '<binary>' else 0

                else:
                    # 其他类型处理，例如 Renamed 或 Copied
                    snapshot1 = None
                    snapshot2 = None
                    char_length1 = 0
                    char_length2 = 0
                    line_count1 = 0
                    line_count2 = 0

            except KeyError as e:
                # 捕获文件不存在的 KeyError，根据具体情况处理
                if change_type == 'A':
                    print(f"Warning: Unable to find added file for {file_path}, skipping.")
                    continue
                elif change_type == 'D':
                    print(f"Warning: Unable to find deleted file for {file_path}, skipping.")
                    continue
                else:
                    raise e
            
            # 准备数据库记录，如果不保存快照则将内容设为None
            db_snapshot1 = snapshot1 if save_snapshot else None
            db_snapshot2 = snapshot2 if save_snapshot else None
            
            diff_file = {
                'commit_hash1_id': commit_hash1_id,
                'commit_hash2_id': commit_hash2_id,
                'file_path': file_path,
                'file_type': file_type,
                'change_type': change_type,
                'line_count1': line_count1,
                'char_length1': char_length1,
                'blob_hash1': str(patch.delta.old_file.id) if patch.delta.old_file.id else None,
                'content_snapshot1': db_snapshot1,
                'line_count2': line_count2,
                'char_length2': char_length2,
                'blob_hash2': str(patch.delta.new_file.id) if patch.delta.new_file.id else None,
                'content_snapshot2': db_snapshot2,
                'tech_stack': tech_stack
            }
            
            # 插入diff记录并获取id
            diff_id = insert_diff_file(diff_file)
            
            # 如果需要运行分析
            if run_analysis and tech_stack:
                for analyzer_config in analyzers:
                    # 检查分析器是否适用于当前技术栈
                    if tech_stack in analyzer_config['tech_stacks']:
                        analyzer_name = analyzer_config['name']
                        
                        # 检查是否已经分析过
                        if not analysis_exists(analyzer_name, diff_id):
                            # 实例化分析器类
                            analyzer_class = loadedAnalyzers[analyzer_config['class']]
                            params = analyzer_config.get('params', None)
                            if (params is not None):
                                analyzer = analyzer_class(params)
                            else:
                                analyzer = analyzer_class()
                                
                            # 分析两个快照
                            if snapshot1 and snapshot1 not in ['<added>', '<binary>']:
                                count1, result1 = analyzer.analyze(snapshot1)
                            else:
                                count1, result1 = 0, None
                                
                            if snapshot2 and snapshot2 not in ['<deleted>', '<binary>']:
                                count2, result2 = analyzer.analyze(snapshot2)
                            else:
                                count2, result2 = 0, None
                            
                            save_analysis_result(analyzer_name, diff_id, commit_hash1_id, commit_hash2_id, count1, result1, count2, result2)

                # remove_diff_file_snapshot(diff_id)

            processed_count += 1
            pbar.n = processed_count
            pbar.refresh()

def analyze_existing_diffs(commit_hash1, commit_hash2):
    stacks = load_stacks_config()
    analyzers = load_analyzer_config()

    # 获取数据库中的diff数据，然后进行分析
    diff_data = get_diff_data(commit_hash1, commit_hash2)
    for diff in diff_data:
        tech_stack = identify_tech_stack(diff['file_path'], stacks)
        if tech_stack:
            for analyzer_config in analyzers:
                if tech_stack in analyzer_config['tech_stacks']:
                    analyzer_name = analyzer_config['name']
                    
                    # 检查是否已经分析过
                    if not analysis_exists(analyzer_name, diff['id']):
                        # 实例化分析器类
                        analyzer_class = globals()[analyzer_config['class']]
                        analyzer = analyzer_class()
                        
                        # 分析两个快照
                        if diff['snapshot1'] and diff['snapshot1'] not in ['<added>', '<binary>']:
                            count1, result1 = analyzer.analyze(diff['snapshot1'])
                        else:
                            count1, result1 = 0, None
                            
                        if diff['snapshot2'] and diff['snapshot2'] not in ['<deleted>', '<binary>']:
                            count2, result2 = analyzer.analyze(diff['snapshot2'])
                        else:
                            count2, result2 = 0, None
                        
                        save_analysis_result(analyzer_name, diff['id'], diff['commit_hash1_id'], diff['commit_hash2_id'], count1, result1, count2, result2)

def identify_tech_stack(file_path, stacks):
    extension = os.path.splitext(file_path)[1]
    for stack in stacks:
        if any(file_path.startswith(path) for path in stack['paths']) or extension in stack['extensions']:
            return stack['name']
    return None
