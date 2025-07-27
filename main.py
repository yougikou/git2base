import argparse
import pygit2
import sys
from pygit2.enums import SortMode
from pygit2.repository import Repository
from sqlalchemy.exc import IntegrityError
from tqdm import tqdm
from typing import cast

from database.connection import init_db
from database.model import create_tables, reset_tables
from database.operation import (
    insert_analysis_results,
    insert_commits,
    insert_commit_files,
    insert_diff_results,
    insert_file_snapshot,
)
from git.utils import parse_short_hash
from git.wrapper import SnapshotAnalysisWrapper, DiffAnalysisWrapper


def commit_exec(
    repo: Repository,
    branch: str,
    commit_hash: str,
    save_snapshot=False,
):
    """Process git commits from a branch with robust error handling
    Args:
        repo: Initialized pygit2 repository
        branch: Branch name to process
        commit_hash: commit hash to walk files tree and snapshots

    Raises:
        ValueError: For invalid branch or commit hash
        RuntimeError: For repository access errors
    """
    if not repo or not isinstance(repo, Repository):
        raise ValueError("Invalid repository instance")

    branch_ref = repo.lookup_reference(f"refs/heads/{branch}")
    if not branch_ref:
        raise ValueError(f"Branch {branch} not found")

    # 验证 commit 是否存在的同时获取改commit
    commit = cast(pygit2.Commit, repo.get(commit_hash))
    if not commit:
        raise ValueError(f"Commit {commit_hash} not found")

    # 验证 commit 是否属于该 branch
    walker = repo.walk(branch_ref.target, SortMode.TOPOLOGICAL)
    if commit_hash not in [str(c.id) for c in walker]:
        raise ValueError(f"Commit {commit_hash} does not belong to branch {branch}")

    snapshot_wrapped = SnapshotAnalysisWrapper(repo, branch, commit)
    commit_data = snapshot_wrapped.get_db_commit()
    commit_files_data = snapshot_wrapped.get_db_commit_files()

    try:
        if not commit_data.is_exists():
            insert_commits([commit_data])

        commit_files_data = insert_commit_files(commit_files_data)
    except IntegrityError as e:
        print(f"CommitFile UNIQUE constraint failed. Result already exist: {e}")
        print(f"Process exit.")
        sys.exit(1)

    with tqdm(
        total=len(commit_files_data),
        desc="Processing files",
        unit="patch",
        bar_format="{desc}: {n_fmt}/{total_fmt} files",
    ) as pbar:
        processed_count = 0
        for file in commit_files_data:
            # TODO decide if keep snapshot as analysis evidence -- maybe for debug purpose
            file_snapshot, analysis_results_data = snapshot_wrapped.exec_analysis(file)
            insert_analysis_results(analysis_results_data)

            if save_snapshot:
                insert_file_snapshot([file_snapshot])

            # 更新进度条
            processed_count += 1
            pbar.n = processed_count
            pbar.refresh()

    print("所有文件分析处理完成")


def diff_branch_exec(
    repo: Repository,
    base_branch: str,
    target_branch: str,
    save_snapshot=False,
):
    base_ref = repo.lookup_reference(f"refs/heads/{base_branch}")
    target_ref = repo.lookup_reference(f"refs/heads/{target_branch}")
    if not base_ref:
        raise ValueError("分支不存在: {base_branch}")

    if not target_ref:
        raise ValueError("分支不存在: {target_branch}")

    base_commit = cast(pygit2.Commit, repo.get(base_ref.target))
    target_commit = cast(pygit2.Commit, repo.get(target_ref.target))

    diff_branch_commit_exec(
        repo,
        base_branch,
        target_branch,
        str(base_commit.id),
        str(target_commit.id),
        save_snapshot,
    )


def diff_commit_exec(
    repo: Repository,
    branch: str,
    base_commit_hash: str,
    target_commit_hash: str,
    save_snapshot=False,
):
    diff_branch_commit_exec(
        repo, branch, branch, base_commit_hash, target_commit_hash, save_snapshot
    )


def diff_branch_commit_exec(
    repo: Repository,
    base_branch: str,
    target_branch: str,
    base_commit_hash: str,
    target_commit_hash: str,
    save_snapshot=False,
):
    base_commit = cast(pygit2.Commit, repo.get(base_commit_hash))
    target_commit = cast(pygit2.Commit, repo.get(target_commit_hash))

    diff_wrapped = DiffAnalysisWrapper(
        repo, base_branch, target_branch, base_commit, target_commit
    )
    diff_results_data = diff_wrapped.get_db_diff_results()
    try:
        for commit_data in diff_wrapped.get_db_commits():
            if not commit_data.is_exists():
                insert_commits([commit_data])

        diff_results_data = insert_diff_results(diff_results_data)
    except IntegrityError as e:
        print(f"DiffResult UNIQUE constraint failed. Result already exist: {e}")
        print(f"Process exit.")
        sys.exit(1)

    with tqdm(
        total=len(diff_results_data),
        desc="Processing files",
        unit="patch",
        bar_format="{desc}: {n_fmt}/{total_fmt} files",
    ) as pbar:
        processed_count = 0
        for diff_result_data in diff_results_data:
            # TODO decide if keep snapshot as analysis evidence -- maybe for debug purpose
            file_snapshots, analysis_results_data = diff_wrapped.exec_analysis(
                diff_result_data
            )
            insert_analysis_results(analysis_results_data)

            if save_snapshot:
                insert_file_snapshot(file_snapshots)

            # 更新进度条
            processed_count += 1
            pbar.n = processed_count
            pbar.refresh()

    print("所有文件分析处理完成")


def validate_args(args):
    exclusive_groups = [
        ("commit_hash", "diff"),
        ("commit_hash", "diff_branch"),
        ("diff", "diff_branch"),
        ("branch", "diff_branch"),
    ]
    for a, b in exclusive_groups:
        if getattr(args, a) and getattr(args, b):
            print(f"错误：不能同时指定 --{a} 和 --{b}。请分别使用。")
            sys.exit(1)


def resolve_branch_and_commits(args, repo):
    # 不指定分支且不是比较分支模式时，使用当前分支
    if not args.branch and not args.diff_branch:
        args.branch = repo.head.shorthand
        print(f"未指定分支，使用当前checkout的分支: {args.branch}")

    # 如果指定了分支但没有指定提交哈希或指定比较提交哈希，则获取该分支的最新提交
    if args.branch and not args.commit_hash and not args.diff:
        latest_commit_hash = str(repo.branches[args.branch].target)
        print(f"没有指定提交，获取{args.branch}的最新提交: {latest_commit_hash}")
        return "commit", args.branch, latest_commit_hash, ""

    if args.branch and args.commit_hash:
        full_commit_hash = parse_short_hash(repo, args.commit_hash)
        return "commit", args.branch, full_commit_hash, ""

    if args.branch and args.diff:
        base_commit_hash = parse_short_hash(repo, args.diff[0])
        target_commit_hash = parse_short_hash(repo, args.diff[1])
        return "diff", args.branch, base_commit_hash, target_commit_hash

    if args.diff_branch:
        return "diff_branch", "", args.diff_branch[0], args.diff_branch[1]

    print("错误：未提供有效的命令参数")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Git 数据库导入工具")
    parser.add_argument("--reset-db", action="store_true", help="重置数据库")
    parser.add_argument("--repo", type=str, help="指定Git仓库路径")
    parser.add_argument(
        "--branch", type=str, help="指定分支，如果未提供则使用当前checkout的分支"
    )
    parser.add_argument(
        "--commit_hash", type=str, help="分析指定commit hash的文件，支持短哈希"
    )
    parser.add_argument(
        "--diff",
        nargs=2,
        metavar=("base_commit", "target_commit"),
        help="分析两个commit的差异文件，支持短哈希",
    )
    parser.add_argument(
        "--diff-branch",
        nargs=2,
        metavar=("base_branch", "target_branch"),
        help="分析两个分支的差异文件，自动使用各自的最新提交",
    )

    if len(sys.argv) == 1:
        parser.print_help()
        return
    args = parser.parse_args()

    if args.reset_db:
        engine = init_db()
        reset_tables(engine)
        print("数据库已重置")
        return

    if not args.repo:
        print("错误：未指定Git仓库路径。请使用 --repo 指定路径。")
        return

    validate_args(args)
    engine = init_db()
    create_tables(engine)
    repo = Repository(args.repo)

    mode, branch, base, target = resolve_branch_and_commits(args, repo)

    if mode == "commit":
        commit_exec(repo, branch, base)
    elif mode == "diff":
        diff_commit_exec(repo, branch, base, target)
    elif mode == "diff_branch":
        diff_branch_exec(repo, base, target)


if __name__ == "__main__":
    main()
