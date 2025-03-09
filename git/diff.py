from git.config import load_stacks_config
from git.commit import get_file_type, get_branch_name_for_commit
from git.analyzer import _analyze_diff
from git.utils import get_change_type, identify_tech_stack
from db.operations import get_commit_id, insert_commit, commit_exists_in_db, insert_diff_file
from tqdm import tqdm
from utils import is_binary

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
    diff = commit1.tree.diff_to_tree(commit2.tree)

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
                _analyze_diff(diff_id, commit_1_id, commit_2_id, 
                            snapshot1, snapshot2, tech_stack)

            processed_count += 1
            pbar.n = processed_count
            pbar.refresh()

