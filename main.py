import argparse
from git_operations import get_git_commits, get_git_diff
from db_operations import reset_database, get_latest_commit_hash_from_db, insert_diff_files
from pygit2 import Repository
from utils import parse_short_hash

def main():
    parser = argparse.ArgumentParser(description='Git 数据库导入工具')
    parser.add_argument('--reset', action='store_true', help='重置数据库')
    parser.add_argument('--repo', type=str, help='指定Git仓库路径')
    parser.add_argument('--branch', type=str, help='指定分支')
    parser.add_argument('--commit_hash', type=str, help='指定commit hash，支持短hash')
    parser.add_argument('--diff', nargs=2, metavar=('commit_hash1', 'commit_hash2'), help='比较两个commit的差异，支持短hash')

    args = parser.parse_args()

    # 如果是重置数据库，不需要repo路径
    if args.reset:
        reset_database()
        print("数据库已重置")
        return

    # 非reset情况下需要repo路径
    if not args.repo:
        print("错误：未指定Git仓库路径。请使用 --repo 指定路径。")
        return

    # 指定的repo路径
    repo = Repository(args.repo)

    if args.branch and not args.commit_hash:
        # 从数据库获取指定分支下的最新 commit_hash
        latest_commit_hash = get_latest_commit_hash_from_db(args.branch)
        if latest_commit_hash:
            print(f"数据库的最新提交: {latest_commit_hash}，获取之后的所有提交: {args.branch}")
        else:
            print(f"数据库中无记录，获取所有提交: {args.branch}")
        # 导入 git 提交历史
        get_git_commits(repo, args.branch, latest_commit_hash)
        return

    if args.branch and args.commit_hash:
        full_commit_hash = parse_short_hash(repo, args.commit_hash)
        # 导入 git 提交历史
        get_git_commits(repo, args.branch, full_commit_hash)
        return

    # 获取 diff
    if args.diff:
        commit_hash1 = parse_short_hash(repo, args.diff[0])
        commit_hash2 = parse_short_hash(repo, args.diff[1])
        get_git_diff(repo, commit_hash1, commit_hash2)

if __name__ == '__main__':
    main()
