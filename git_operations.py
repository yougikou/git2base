import os
import importlib
import threading
import traceback
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
                    with open('config.yaml', 'r', encoding='utf-8') as file:
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

def get_git_commits_ui(repo, branch: str = None, density: str = "全部", show_only_current: bool = False):
    try:
        # 使用字典存储提交，key为commit_hash，value为提交数据
        commits_data = {}
        
        # 获取所有分支
        all_branches = list(repo.branches.local)
        
        # 遍历所有分支
        for b in all_branches:
            branch_commits = get_git_commits_data(repo, b)
            for commit in branch_commits:
                commit_hash = commit['commit_hash']
                
                if commit_hash in commits_data:
                    # 如果提交已存在，合并分支信息
                    existing_branches = commits_data[commit_hash]['branch'].split(', ')
                    if b not in existing_branches:
                        commits_data[commit_hash]['branch'] += f", {b}"
                else:
                    # 新提交，初始化分支信息
                    commit['branch'] = b
                    commits_data[commit_hash] = commit
        
        # 转换为列表并按时间排序
        commits = sorted(commits_data.values(), key=lambda x: x['commit_date'], reverse=True)
        
        # 如果指定了分支且需要仅显示当前分支
        if branch and show_only_current:
            commits = [c for c in commits if branch in c['branch'].split(', ')]
        
        # 根据密度筛选提交
        if density != "全部":
            filtered_commits = []
            # 为每个分支维护最后显示时间
            branch_last_dates = {}
            
            # 按时间顺序遍历提交
            for commit in sorted(commits, key=lambda x: x['commit_date']):
                commit_date = commit['commit_date']
                branches = commit['branch'].split(', ')
                
                # 检查每个分支是否需要显示
                show_commit = False
                for branch in branches:
                    last_date = branch_last_dates.get(branch)
                    
                    # 如果分支没有最后显示时间，或者时间差超过间隔
                    if last_date is None:
                        show_commit = True
                        branch_last_dates[branch] = commit_date
                    else:
                        time_diff = commit_date - last_date
                        if density == "1周" and time_diff >= 604800:
                            show_commit = True
                        elif density == "2周" and time_diff >= 1209600:
                            show_commit = True
                        elif density == "1个月" and time_diff >= 2592000:
                            show_commit = True
                        elif density == "3个月" and time_diff >= 7776000:
                            show_commit = True
                        elif density == "6个月" and time_diff >= 15552000:
                            show_commit = True
                        elif density == "1年" and time_diff >= 31536000:
                            show_commit = True
                            
                        if show_commit:
                            branch_last_dates[branch] = commit_date
                
                if show_commit:
                    filtered_commits.append(commit)
                    
            # 按时间倒序返回
            return sorted(filtered_commits, key=lambda x: x['commit_date'], reverse=True)
            
        return commits
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()

def get_git_commits_data(repo, branch: str):
    if not repo or not isinstance(repo, pygit2.Repository):
        raise ValueError("Invalid repository instance")
    
    if not branch or not isinstance(branch, str):
        raise ValueError("Invalid branch name")

    branch_ref = repo.lookup_reference(f'refs/heads/{branch}')
    if not branch_ref:
        raise ValueError(f"Branch {branch} not found")
    
    commits_data = []
    walker = repo.walk(branch_ref.target, pygit2.GIT_SORT_TIME)
    for commit in walker:
        commit_data = {
            'commit_hash': str(commit.id),
            'branch': branch,
            'commit_date': commit.commit_time,
            'commit_message': commit.message,
            'author_name': commit.author.name,
            'author_email': commit.author.email
        }
        commits_data.append(commit_data)
    return commits_data


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
            # diff = commit.tree.diff_to_tree(commit.parents[0].tree)
            diff = commit.parents[0].tree.diff_to_tree(commit.tree)
        else:
            # diff = commit.tree.diff_to_tree()
            empty_tree = repo.TreeBuilder().write()
            diff = repo[empty_tree].diff_to_tree(commit.tree)

        files = []
        for delta in diff.deltas:
            file_path = delta.new_file.path if delta.status != pygit2.GIT_DELTA_DELETED else delta.old_file.path
            file_type = get_file_type(file_path) 

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
        commit_1_id = insert_commit(commit_data1)  # 获取插入的 commit_id
    else:
        commit_1_id = get_commit_id(commit_hash1)

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
        commit_2_id = insert_commit(commit_data2)  # 获取插入的 commit_id
    else:
        commit_2_id = get_commit_id(commit_hash2)  # 已存在则直接获取 commit_id

    # Get the diff between the two commits
    diff = commit2.tree.diff_to_tree(commit1.tree)

    total_patches = len(diff)
    processed_count = 0

    with tqdm(total=total_patches, desc="Processing patches", unit="patch", bar_format="{desc}: {n_fmt}/{total_fmt} patches") as pbar:
        for patch in diff:
            file_path = patch.delta.new_file.path if patch.delta.new_file.path else patch.delta.old_file.path

            # 跳过以 . 开头的路径
            if file_path.startswith('.'):
                continue

            file_type = get_file_type(file_path)

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
            
            tech_stack = identify_tech_stack(file_path, stacks)

            diff_file = {
                'commit_1_id': commit_1_id,
                'commit_2_id': commit_2_id,
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
            if run_analysis:
                analyzers = load_analyzer_config() if run_analysis else []
                loadedAnalyzers = _load_analyzers(analyzers) if analyzers else {}
                _analyze_diff(diff_id, commit_1_id, commit_2_id, 
                            snapshot1, snapshot2, tech_stack, 
                            analyzers, loadedAnalyzers)

            processed_count += 1
            pbar.n = processed_count
            pbar.refresh()

def analyze_existing_diffs(commit_hash1, commit_hash2):
    analyzers = load_analyzer_config()
    loadedAnalyzers = _load_analyzers(analyzers) if analyzers else {}

    # 获取数据库中的diff数据，然后进行分析
    diff_data = get_diff_data(commit_hash1, commit_hash2)

    total_files = len(diff_data)
    processed_count = 0

    with tqdm(total=total_files, desc="Processing analyzing", unit="file", bar_format="{desc}: {n_fmt}/{total_fmt} files") as pbar:
        for diff in diff_data:
            _analyze_diff(diff.id, diff.commit_1_id, diff.commit_2_id, 
                        diff.content_snapshot1, diff.content_snapshot2, diff.tech_stack,
                        analyzers, loadedAnalyzers)
            processed_count += 1
            pbar.n = processed_count
            pbar.refresh()

def _load_analyzers(analyzers):
    """加载分析器类
    
    Args:
        analyzers: 分析器配置列表
        
    Returns:
        dict: 已加载的分析器类字典
        
    Raises:
        ImportError: 如果无法加载分析器
    """
    loaded_analyzers = {}
    for analyzer_config in analyzers:
        class_name = analyzer_config['class']
        module_name = f'analyzers.{class_name}'
        try:
            module = importlib.import_module(module_name)
            analyzer_class = getattr(module, class_name)
            loaded_analyzers[class_name] = analyzer_class
        except (ImportError, AttributeError) as e:
            raise ImportError(f"Failed to load {class_name} from {module_name}: {e}")
    return loaded_analyzers

def _analyze_diff(diff_id, commit_1_id, commit_2_id, snapshot1, snapshot2, tech_stack, analyzers, loadedAnalyzers):
    """分析diff文件并保存结果
    
    Args:
        diff_id: diff记录ID
        commit_1_id: 提交1 ID
        commit_2_id: 提交2 ID
        snapshot1: 快照1内容
        snapshot2: 快照2内容
        tech_stack: 技术栈
        analyzers: 分析器配置列表
        loadedAnalyzers: 已加载的分析器类字典
    """
    if tech_stack:
        for analyzer_config in analyzers:
            if tech_stack in analyzer_config['tech_stacks']:
                analyzer_name = analyzer_config['name']
                
                # 检查是否已经分析过
                if not analysis_exists(analyzer_name, diff_id):
                    # 实例化分析器类
                    analyzer_class = loadedAnalyzers[analyzer_config['class']]
                    params = analyzer_config.get('params', None)
                    analyzer = analyzer_class(params or {})
                        
                    # 分析两个快照
                    if snapshot1 and snapshot1 not in ['<added>', '<binary>']:
                        count1, result1 = analyzer.analyze(snapshot1)
                    else:
                        count1, result1 = 0, None
                        
                    if snapshot2 and snapshot2 not in ['<deleted>', '<binary>']:
                        count2, result2 = analyzer.analyze(snapshot2)
                    else:
                        count2, result2 = 0, None
                    
                    save_analysis_result(analyzer_name, diff_id, commit_1_id, commit_2_id, count1, result1, count2, result2)

def identify_tech_stack(file_path, stacks):
    extension = os.path.splitext(file_path)[1]
    for stack in stacks:
        if any(file_path.startswith(path) for path in stack['paths']) and extension in stack['extensions']:
            return stack['name']
    return None
