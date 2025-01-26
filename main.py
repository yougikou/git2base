import argparse
from git_operations import get_git_commits, get_git_diff, analyze_existing_diffs
from db_operations import reset_database, get_latest_commit_hash_from_db, insert_diff_files
from pygit2 import Repository
from utils import parse_short_hash

def main():
    parser = argparse.ArgumentParser(description='Git 数据库导入工具')
    parser.add_argument('--reset-db', action='store_true', help='重置数据库')
    parser.add_argument('--repo', type=str, help='指定Git仓库路径')
    parser.add_argument('--branch', type=str, help='指定分支，如果未提供则使用当前checkout的分支')
    parser.add_argument('--commit_hash', type=str, help='指定commit hash，支持短hash')
    parser.add_argument('--diff', nargs=2, metavar=('commit_hash1', 'commit_hash2'), help='比较两个commit的差异，支持短hash')
    parser.add_argument('--analyze', nargs='*', metavar=('commit_hash1', 'commit_hash2'), help='分析已有的diff结果，支持短hash。或者在diff时指定analyze参数，直接分析diff结果')

    args = parser.parse_args()

    # 初始化数据库连接
    from db_operations import initialize_db
    initialize_db()
    
    # 如果是重置数据库，不需要repo路径
    if args.reset_db:
        reset_database()
        print("数据库已重置")
        return

    # 非reset情况下需要repo路径
    if not args.repo:
        print("错误：未指定Git仓库路径。请使用 --repo 指定路径。")
        return

    # 指定的repo路径
    repo = Repository(args.repo)
    
    # 如果没有指定分支，使用当前checkout的分支
    if not args.branch and not args.diff and not args.analyze:
        args.branch = repo.head.shorthand
        print(f"未指定分支，使用当前checkout的分支: {args.branch}")

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
        runAnalysis = False
        
        if args.analyze is not None:
            if len(args.analyze) > 0:
                parser.error("--diff后的--analyze 如果指定参数则会被忽略")
            runAnalysis = True

        get_git_diff(repo, commit_hash1, commit_hash2, save_snapshot=True, run_analysis=runAnalysis)
        return

    # 单独对已有的diff结果进行分析，指定对象diff的hash
    if args.analyze:
        if len(args.analyze) != 2:
            parser.error("--analyze 参数只能接受 2 个值")

        commit_hash1 = parse_short_hash(repo, args.analyze[0])
        commit_hash2 = parse_short_hash(repo, args.analyze[1])
        analyze_existing_diffs(commit_hash1, commit_hash2)

if __name__ == '__main__':
    main()
