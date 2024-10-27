import pygit2
from db_operations import get_commit_id, insert_commit, commit_exists_in_db, insert_commit_and_files, insert_diff_files
from tqdm import tqdm
from utils import is_binary, calculate_file_metrics

def get_change_type(delta):
    if delta.status == pygit2.GIT_DELTA_ADDED:
        return 'A'  # Added
    elif delta.status == pygit2.GIT_DELTA_MODIFIED:
        return 'M'  # Modified
    elif delta.status == pygit2.GIT_DELTA_DELETED:
        return 'D'  # Deleted
    elif delta.status == pygit2.GIT_DELTA_RENAMED:
        return 'R'  # Renamed
    elif delta.status == pygit2.GIT_DELTA_COPIED:
        return 'C'  # Copied
    elif delta.status == pygit2.GIT_DELTA_UNMODIFIED:
        return '='  # Unmodified (未修改)
    elif delta.status == pygit2.GIT_DELTA_UNTRACKED:
        return '?'  # Untracked (未跟踪)
    elif delta.status == pygit2.GIT_DELTA_TYPECHANGE:
        return 'T'  # Type change (类型变化)
    elif delta.status == pygit2.GIT_DELTA_UNREADABLE:
        return '!'  # Unreadable (不可读)
    elif delta.status == pygit2.GIT_DELTA_CONFLICTED:
        return 'U'  # Unmerged (冲突)
    else:
        return 'X'  # Unknown 状态 (未知情况)

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

def get_git_commits(repo, branch, start_commit_hash=None):
    # 打印遍历开始的提示
    print(f"开始从分支 {branch} 的提交 {start_commit_hash} 后开始处理（从旧到新）")

    # 创建 walker，从指定的分支开始遍历
    walker = repo.walk(repo.lookup_reference(f'refs/heads/{branch}').target, pygit2.GIT_SORT_TIME)
    if start_commit_hash:
        walker.hide(repo.revparse_single(start_commit_hash).id)

    # 计算总提交数
    total_commits = sum(1 for _ in walker)
    print(f"总共有 {total_commits} 个提交需要处理")

    # 重新创建 walker 以便遍历提交
    walker = repo.walk(repo.lookup_reference(f'refs/heads/{branch}').target, pygit2.GIT_SORT_TIME | pygit2.GIT_SORT_REVERSE)

    # 初始化 tqdm 进度条，禁用百分比显示，只显示处理数/总数
    pbar = tqdm(total=total_commits, desc="Processing commits", unit="commit", bar_format="{desc}: {n_fmt}/{total_fmt} commits")

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

def get_git_diff(repo, commit_hash1, commit_hash2):
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
            file_type = file_type = get_file_type(file_path)

            # 获取变更类型
            change_type = get_change_type(patch.delta)

            # print(f"Debug: file {file_path}, Change Type: {change_type}.")

            try:
                if change_type == 'A':  # Added
                    # 新增文件：只存在 new_file
                    blob2 = repo[patch.delta.new_file.id]
                    snapshot1 = '<added>'
                    snapshot2 = blob2.data.decode('utf-8', 'ignore').replace('\x00', '') if not is_binary(blob2.data) else '<binary>'
                    char_length1 = 0
                    char_length2 = len(snapshot2) if snapshot2 != '<binary>' else 0

                elif change_type == 'D':  # Deleted
                    # 删除文件：只存在 old_file
                    blob1 = repo[patch.delta.old_file.id]
                    snapshot1 = blob1.data.decode('utf-8', 'ignore').replace('\x00', '') if not is_binary(blob1.data) else '<binary>'
                    snapshot2 = '<deleted>'
                    char_length1 = len(snapshot1) if snapshot1 != '<binary>' else 0
                    char_length2 = 0

                elif change_type == 'M':  # Modified
                    # 修改文件：同时存在 old_file 和 new_file
                    blob1 = repo[patch.delta.old_file.id]
                    blob2 = repo[patch.delta.new_file.id]
                    snapshot1 = blob1.data.decode('utf-8', 'ignore').replace('\x00', '') if not is_binary(blob1.data) else '<binary>'
                    snapshot2 = blob2.data.decode('utf-8', 'ignore').replace('\x00', '') if not is_binary(blob2.data) else '<binary>'
                    char_length1 = len(snapshot1) if snapshot1 != '<binary>' else 0
                    char_length2 = len(snapshot2) if snapshot2 != '<binary>' else 0

                else:
                    # 其他类型处理，例如 Renamed 或 Copied
                    snapshot1 = None
                    snapshot2 = None
                    char_length1 = 0
                    char_length2 = 0

            except KeyError as e:
                # 捕获文件不存在的 KeyError，根据具体情况处理
                if change_type == 'A':
                    # 对于新增的文件，出现 KeyError 通常意味着新文件引用不正确，跳过处理
                    print(f"Warning: Unable to find added file for {file_path}, skipping.")
                    continue
                elif change_type == 'D':
                    # 对于删除的文件，出现 KeyError 通常意味着旧文件引用不正确，跳过处理
                    print(f"Warning: Unable to find deleted file for {file_path}, skipping.")
                    continue
                else:
                    raise e
            
            diff_tuple = (
                commit_hash1_id,
                commit_hash2_id,
                file_path,
                file_type,
                change_type,
                len(snapshot1.splitlines()) if snapshot1 else 0,
                char_length1,
                str(patch.delta.old_file.id) if patch.delta.old_file.id else None,
                snapshot1,
                len(snapshot2.splitlines()) if snapshot2 else 0,
                char_length2,
                str(patch.delta.new_file.id) if patch.delta.new_file.id else None,
                snapshot2,
            )
            
            diff_files_data.append(diff_tuple)
            processed_count += 1
            pbar.n = processed_count
            pbar.refresh()

            # Every 100 patches, insert data into the database
            if len(diff_files_data) >= 100:
                insert_diff_files(diff_files_data)
                diff_files_data = []
                pbar.update(100)

        # Insert any remaining diff data
        if diff_files_data:
            insert_diff_files(diff_files_data)
            pbar.update(len(diff_files_data))