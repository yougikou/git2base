import traceback
import pygit2
from git.utils import get_change_type, get_file_type
from tqdm import tqdm
from db.operations import insert_commit_and_files
from utils import is_binary, calculate_file_metrics

# Density options constants
DENSITY_ALL = "density_options.all"
DENSITY_1WEEK = "density_options.1week"
DENSITY_2WEEKS = "density_options.2weeks"
DENSITY_1MONTH = "density_options.1month"
DENSITY_3MONTHS = "density_options.3months"
DENSITY_6MONTHS = "density_options.6months"
DENSITY_1YEAR = "density_options.1year"


def get_branch_name_for_commit(repo, commit_hash):
    try:
        branches = []
        for branch in repo.branches.local:
            branch_ref = repo.lookup_reference(f'refs/heads/{branch}')
            if branch_ref is not None:
                branch_target = branch_ref.target
                if branch_target == commit_hash:
                    branches.append(branch)
        return branches[0] if branches else 'unknown'
    except KeyError:
        return 'unknown'

def get_git_commits_ui(repo, branch: str = None, density: str = DENSITY_ALL, show_only_current: bool = False):
    try:
        commits_data = {}
        all_branches = list(repo.branches.local)
        
        for b in all_branches:
            branch_commits = get_git_commits_data(repo, b)
            for commit in branch_commits:
                commit_hash = commit['commit_hash']
                if commit_hash in commits_data:
                    existing_branches = commits_data[commit_hash]['branch'].split(', ')
                    if b not in existing_branches:
                        commits_data[commit_hash]['branch'] += f", {b}"
                else:
                    commit['branch'] = b
                    commits_data[commit_hash] = commit
        
        commits = sorted(commits_data.values(), key=lambda x: x['commit_date'], reverse=True)
        
        if branch and show_only_current:
            commits = [c for c in commits if branch in c['branch'].split(', ')]
        
        if density != DENSITY_ALL:
            filtered_commits = []
            branch_last_dates = {}
            
            for commit in sorted(commits, key=lambda x: x['commit_date']):
                commit_date = commit['commit_date']
                branches = commit['branch'].split(', ')
                
                show_commit = False
                for branch in branches:
                    last_date = branch_last_dates.get(branch)
                    
                    if last_date is None:
                        show_commit = True
                        branch_last_dates[branch] = commit_date
                    else:
                        time_diff = commit_date - last_date
                        if density == DENSITY_1WEEK and time_diff >= 604800:
                            show_commit = True
                        elif density == DENSITY_2WEEKS and time_diff >= 1209600:
                            show_commit = True
                        elif density == DENSITY_1MONTH and time_diff >= 2592000:
                            show_commit = True
                        elif density == DENSITY_3MONTHS and time_diff >= 7776000:
                            show_commit = True
                        elif density == DENSITY_6MONTHS and time_diff >= 15552000:
                            show_commit = True
                        elif density == DENSITY_1YEAR and time_diff >= 31536000:
                            show_commit = True
                            
                        if show_commit:
                            branch_last_dates[branch] = commit_date
                
                if show_commit:
                    filtered_commits.append(commit)
                    
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
    if not repo or not isinstance(repo, pygit2.Repository):
        raise ValueError("Invalid repository instance")
        
    if not branch or not isinstance(branch, str):
        raise ValueError("Invalid branch name")
        
    branch_ref = repo.lookup_reference(f'refs/heads/{branch}')
    if not branch_ref:
        raise ValueError(f"Branch {branch} not found")
        
    walker = repo.walk(branch_ref.target, pygit2.GIT_SORT_TIME)
    if start_commit_hash:
        try:
            start_commit = repo.revparse_single(start_commit_hash)
            walker.hide(start_commit.id)
        except KeyError:
            raise ValueError(f"Start commit {start_commit_hash} not found")
            
    total_commits = sum(1 for _ in walker)
    if total_commits == 0:
        return 0
        
    walker = repo.walk(branch_ref.target, pygit2.GIT_SORT_TIME | pygit2.GIT_SORT_REVERSE)
    
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

        if commit.parents:
            diff = commit.parents[0].tree.diff_to_tree(commit.tree)
        else:
            empty_tree = repo.TreeBuilder().write()
            diff = repo[empty_tree].diff_to_tree(commit.tree)

        files = []
        for delta in diff.deltas:
            file_path = delta.new_file.path if delta.status != pygit2.GIT_DELTA_DELETED else delta.old_file.path
            file_type = get_file_type(file_path) 

            try:
                blob = repo[delta.new_file.id] if delta.status != pygit2.GIT_DELTA_DELETED else None
            except KeyError:
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
                'file_type': file_type,
                'change_type': get_change_type(delta),
                'char_length': char_length,
                'line_count': line_count,
                'blob_hash': blob_hash
            }
            files.append(file_data)

        pbar.update(1)
        insert_commit_and_files(commit_data, files)

    pbar.close()
    print("所有提交处理完成")
