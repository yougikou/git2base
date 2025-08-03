import argparse
import pygit2
import sys
from pygit2.enums import SortMode
from pygit2.repository import Repository
from sqlalchemy.exc import IntegrityError
from tqdm import tqdm
from typing import cast


from git2base.analyzers import load_and_register_analyzers
from git2base.database import (
    init_output,
    create_tables,
    reset_tables,
    insert_analysis_results,
    insert_commits,
    insert_commit_files,
    insert_diff_results,
    insert_file_snapshot,
)
from git2base.git import (
    SnapshotAnalysisWrapper,
    DiffAnalysisWrapper,
    parse_short_hash,
    write_csv,
)
from git2base.config import LOGGER_GIT2BASE, get_logger, load_output_config


output_config = load_output_config()
logger = get_logger(LOGGER_GIT2BASE)


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

    if output_config["type"] == "csv":
        logger.debug("Write commit data")
        write_csv(
            [commit_data.to_dict()],
            f"{output_config['csv']['path']}/commits.csv",
            False,
        )
        logger.debug("Write commit file data")
        write_csv(
            [f.to_dict() for f in commit_files_data],
            f"{output_config['csv']['path']}/commit_files.csv",
            False,
        )
    else:
        try:
            if not commit_data.is_exists():
                insert_commits([commit_data])
            commit_files_data = insert_commit_files(commit_files_data)
        except IntegrityError as e:
            logger.error(
                f"CommitFile UNIQUE constraint failed. Result already exist: {e}"
            )
            logger.error("Process exit.")
            sys.exit(1)

    with tqdm(
        total=len(commit_files_data),
        desc="Processing files",
        unit="patch",
        bar_format="{desc}: {n_fmt}/{total_fmt} files",
    ) as pbar:
        processed_count = 0
        append_mode = False
        for file in commit_files_data:
            # TODO decide if keep snapshot as analysis evidence -- maybe for debug purpose
            file_snapshot, analysis_results_data = snapshot_wrapped.exec_analysis(file)

            if output_config["type"] == "csv":
                rows = [f.to_dict() for f in analysis_results_data]
                logger.debug(f"Write analysis results of file {file.path}")
                write_csv(
                    rows,
                    f"{output_config['csv']['path']}/analysis_results.csv",
                    append_mode,
                )
                if rows:
                    append_mode = True
            else:
                try:
                    insert_analysis_results(analysis_results_data)

                    if save_snapshot:
                        insert_file_snapshot([file_snapshot])
                except Exception as e:
                    logger.error("Process exit.")
                    sys.exit(1)

            # 更新进度条
            processed_count += 1
            pbar.n = processed_count
            pbar.refresh()

    logger.info("All files analyzed and processed")


def diff_branch_exec(
    repo: Repository,
    base_branch: str,
    target_branch: str,
    save_snapshot=False,
):
    base_ref = repo.lookup_reference(f"refs/heads/{base_branch}")
    target_ref = repo.lookup_reference(f"refs/heads/{target_branch}")
    if not base_ref:
        raise ValueError(f"分支不存在: {base_branch}")

    if not target_ref:
        raise ValueError(f"分支不存在: {target_branch}")

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
    commits_data = diff_wrapped.get_db_commits()
    diff_results_data = diff_wrapped.get_db_diff_results()
    if output_config["type"] == "csv":
        logger.debug("Write commit data")
        write_csv(
            [f.to_dict() for f in commits_data],
            f"{output_config['csv']['path']}/commits.csv",
            False,
        )
        logger.debug("Write diff results data")
        write_csv(
            [f.to_dict() for f in diff_results_data],
            f"{output_config['csv']['path']}/diff_results.csv",
            False,
        )
    else:
        try:
            for commit_data in commits_data:
                if not commit_data.is_exists():
                    insert_commits([commit_data])

            diff_results_data = insert_diff_results(diff_results_data)
        except IntegrityError as e:
            logger.error(
                f"DiffResult UNIQUE constraint failed. Result already exist: {e}"
            )
            logger.error("Process exit.")
            sys.exit(1)

    with tqdm(
        total=len(diff_results_data),
        desc="Processing files",
        unit="patch",
        bar_format="{desc}: {n_fmt}/{total_fmt} files",
    ) as pbar:
        processed_count = 0
        append_mode = False
        for diff_result_data in diff_results_data:
            # TODO decide if keep snapshot as analysis evidence -- maybe for debug purpose
            file_snapshots, analysis_results_data = diff_wrapped.exec_analysis(
                diff_result_data
            )

            if output_config["type"] == "csv":
                rows = [f.to_dict() for f in analysis_results_data]
                logger.debug(
                    f"Write analysis results of file {diff_result_data.target_path}"
                )
                write_csv(
                    rows,
                    f"{output_config['csv']['path']}/analysis_results.csv",
                    append_mode,
                )
                if rows:
                    append_mode = True
            else:
                try:
                    insert_analysis_results(analysis_results_data)

                    if save_snapshot:
                        insert_file_snapshot(file_snapshots)
                except Exception as e:
                    logger.error("Process exit.")
                    sys.exit(1)

            # 更新进度条
            processed_count += 1
            pbar.n = processed_count
            pbar.refresh()

    logger.info("All files analyzed and processed")


def validate_args(args):
    exclusive_groups = [
        ("snapshot", "diff"),
        ("snapshot", "diff_branch"),
        ("history", "diff"),
        ("history", "diff_branch"),
        ("history", "snapshot"),
        ("diff", "diff_branch"),
        ("branch", "diff_branch"),
    ]
    for a, b in exclusive_groups:
        if getattr(args, a) and getattr(args, b):
            logger.error(
                f"Error: Cannot specify both --{a} and --{b}. Please use each separately."
            )
            sys.exit(1)


def resolve_branch_and_commits(args, repo):
    # 不指定分支且不是比较分支模式时，使用当前分支
    if not args.branch and not args.diff_branch:
        args.branch = repo.head.shorthand
        logger.info(
            f"No branch is specified, use the branch of the current checkout: {args.branch}"
        )

    # 如果指定了分支但没有指定提交哈希或指定比较提交哈希，则获取该分支的最新提交
    if args.branch and not args.snapshot and not args.history and not args.diff:
        latest_commit_hash = str(repo.branches[args.branch].target)
        logger.info(
            f"Without specifying a mode or commit, get the latest commit of {args.branch}: {latest_commit_hash}, executed in snapshot mode"
        )
        return "snapshot", args.branch, latest_commit_hash, ""

    if args.branch and args.snapshot:
        snapshot_commit_hash = parse_short_hash(repo, args.snapshot)
        return "snapshot", args.branch, snapshot_commit_hash, ""

    if args.branch and args.history:
        history_commit_hash = parse_short_hash(repo, args.history)
        return "history", args.branch, history_commit_hash, ""

    if args.branch and args.diff:
        base_commit_hash = parse_short_hash(repo, args.diff[0])
        target_commit_hash = parse_short_hash(repo, args.diff[1])
        return "diff", args.branch, base_commit_hash, target_commit_hash

    if args.diff_branch:
        return "diff_branch", "", args.diff_branch[0], args.diff_branch[1]

    logger.error("Error: No valid command arguments were provided")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Git database import/analysis tool")
    parser.add_argument("--reset-db", action="store_true", help="Reset the database")
    parser.add_argument("--repo", type=str, help="Specify the Git repository path")
    parser.add_argument(
        "--branch",
        type=str,
        help="Specify the branch. If not provided, the current checkout branch will be used.",
    )
    parser.add_argument(
        "--snapshot",
        type=str,
        help="Analyze files with specified snapshot commit hash, supporting short hashes",
    )
    parser.add_argument(
        "--history",
        type=str,
        help="Analyze the commit data after the specified history commit hash, supporting short hashes",
    )
    parser.add_argument(
        "--diff",
        nargs=2,
        metavar=("base_commit", "target_commit"),
        help="Analyze the difference between two commit files, support short hash",
    )
    parser.add_argument(
        "--diff-branch",
        nargs=2,
        metavar=("base_branch", "target_branch"),
        help="Analyze the difference files between two branches and automatically use their respective latest commits",
    )

    if len(sys.argv) == 1:
        parser.print_help()
        return
    args = parser.parse_args()

    if args.reset_db:
        engine = init_output()
        if engine:
            reset_tables(engine)
            logger.info("Database reset")
        else:
            logger.info("Output mode is CSV, ignoring database operations")
        return

    if not args.repo:
        logger.error(
            "Error: Git repository path not specified. Please use --repo to specify the path"
        )
        return

    validate_args(args)
    repo = Repository(args.repo)
    mode, branch, base, target = resolve_branch_and_commits(args, repo)
    engine = init_output(mode)
    if engine:
        create_tables(engine)

    load_and_register_analyzers()

    if mode == "snapshot":
        commit_exec(repo, branch, base)
    elif mode == "history":
        commit_exec(repo, branch, base)
    elif mode == "diff":
        diff_commit_exec(repo, branch, base, target)
    elif mode == "diff_branch":
        diff_branch_exec(repo, base, target)
