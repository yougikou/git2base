import argparse
import pygit2
import sys
from pygit2.enums import SortMode
from pygit2.repository import Repository
from sqlalchemy.exc import IntegrityError
from tqdm import tqdm
from typing import cast
import os, json
from datetime import datetime, timezone
from typing import Protocol, Callable

from git2base.analyzers import load_and_register_analyzers
from git2base.database import (
    init_output,
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
run_dir_data: str | None = None


class RunMetaPlugin(Protocol):
    def prepare_run(
        self,
        *,
        artifacts_root: str,
        project: str,
        mode: str,
        branch: str,
        base: str,
        target: str,
        repo_path: str,
    ) -> str: ...


def _ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)


def _atomic_write_json(path: str, obj: dict):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _load_projects_json(project_dir: str) -> dict:
    pj = os.path.join(project_dir, "project.json")
    if os.path.exists(pj):
        with open(pj, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def default_prepare_run(
    *,
    artifacts_root: str,
    project: str,
    mode: str,
    branch: str,
    base: str,
    target: str,
    repo_path: str,
) -> str:
    # run_id: Mode_YYYYMMDD-HHMMSS-<shorthash>
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short = (target or base or "run")[:7]
    run_id = f"{mode}_{ts}-{short}"
    project_dir = os.path.join(artifacts_root, project)
    runs_dir = os.path.join(project_dir, "runs")
    run_dir = os.path.join(runs_dir, run_id)
    data_dir = os.path.join(run_dir, "data")
    # metrics_dir = os.path.join(run_dir, "metrics")
    # charts_dir = os.path.join(metrics_dir, "charts")
    for d in (project_dir, runs_dir, run_dir, data_dir):
        _ensure_dir(d)

    # project.json upsert (minimal fields)
    project_json = _load_projects_json(project_dir)
    project_json.setdefault("schema_version", "1.0")
    project_json.setdefault("id", project)
    project_json.setdefault("title", project)
    project_json["latest_run"] = run_id
    project_json["updated_at"] = (
        datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
    )
    runs_list = project_json.setdefault("runs", [])
    runs_list.append(
        {
            "run_id": run_id,
            "run_type": ("snapshot" if mode == "snap" or mode == "hist" else "diff"),
            "scope_key": (
                base if (mode == "snap" or mode == "hist") else f"{base}..{target}"
            ),
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")
            + "Z",
        }
    )
    _atomic_write_json(os.path.join(project_dir, "project.json"), project_json)

    # run.json skeleton (metrics_files can be filled by dashboard/aggregator later)
    run_json = {
        "schema_version": "1.0",
        "project_id": project,
        "run_id": run_id,
        "run_type": ("snapshot" if mode == "snap" or mode == "hist" else "diff"),
        "scope_type": ("snapshot" if mode == "snap" or mode == "hist" else "diff"),
        "scope_key": (
            base if (mode == "snap" or mode == "hist") else f"{base}..{target}"
        ),
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
    }
    _atomic_write_json(os.path.join(run_dir, "run.json"), run_json)
    return run_dir


def load_runmeta_plugin() -> Callable[..., str]:
    # ENV override: module:function
    spec = os.environ.get("GIT2BASE_RUNMETA_PLUGIN")
    if spec:
        mod, func = spec.split(":", 1)
        m = __import__(mod, fromlist=[func])
        return getattr(m, func)
    return default_prepare_run


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

    # Resolve CSV base path to current run's data directory when in CSV mode
    if not run_dir_data:
        raise RuntimeError(
            "Run directory data path is not initialized. Please call init_output() first."
        )

    if output_config["type"] == "csv":
        logger.debug("Write commit data")
        write_csv(
            [commit_data.to_dict()],
            os.path.join(run_dir_data, "commits.csv"),
            False,
        )
        logger.debug("Write commit file data")
        write_csv(
            [f.to_dict() for f in commit_files_data],
            os.path.join(run_dir_data, "commit_files.csv"),
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
                    os.path.join(run_dir_data, "analysis_results.csv"),
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
    try:
        base_ref = repo.lookup_reference(f"refs/heads/{base_branch}")
        target_ref = repo.lookup_reference(f"refs/heads/{target_branch}")
    except KeyError as e:
        raise ValueError(f"分支不存在: {str(e)}")

    base_commit = cast(pygit2.Commit, repo[base_ref.target])
    target_commit = cast(pygit2.Commit, repo[target_ref.target])

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

    # Resolve CSV base path to current run's data directory when in CSV mode
    if not run_dir_data:
        raise RuntimeError(
            "Run directory data path is not initialized. Please call init_output() first."
        )

    if output_config["type"] == "csv":
        logger.debug("Write commit data")
        write_csv(
            [f.to_dict() for f in commits_data],
            os.path.join(run_dir_data, "commits.csv"),
            False,
        )
        logger.debug("Write diff results data")
        write_csv(
            [f.to_dict() for f in diff_results_data],
            os.path.join(run_dir_data, "diff_results.csv"),
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
                    os.path.join(run_dir_data, "analysis_results.csv"),
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


def _finalize_run_metadata(run_dir: str):
    """Finalize metadata after a successful run.

    - Adds status and end timestamp to run.json
    - Lists produced CSV files under data/
    - Updates the matching run record in project.json with completion info
    """
    try:
        data_dir = os.path.join(run_dir, "data")
        data_files = []
        if os.path.isdir(data_dir):
            for name in sorted(os.listdir(data_dir)):
                if name.lower().endswith(".csv"):
                    data_files.append(os.path.join("data", name))

        # Update run.json
        run_json_path = os.path.join(run_dir, "run.json")
        if os.path.exists(run_json_path):
            with open(run_json_path, "r", encoding="utf-8") as f:
                run_json = json.load(f)
        else:
            run_json = {}

        run_json["status"] = "success"
        run_json["ended_at"] = (
            datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
        )
        run_json["data_files"] = data_files
        _atomic_write_json(run_json_path, run_json)

        # Update project.json entry for this run
        project_dir = os.path.dirname(os.path.dirname(run_dir))
        project_json_path = os.path.join(project_dir, "project.json")
        if os.path.exists(project_json_path):
            with open(project_json_path, "r", encoding="utf-8") as f:
                project_json = json.load(f)
        else:
            project_json = {}

        runs = project_json.get("runs", [])
        # Find the run by id
        run_id = os.path.basename(run_dir)
        for r in runs:
            if r.get("run_id") == run_id:
                r["status"] = "success"
                r["completed_at"] = (
                    datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
                )
                break
        project_json["runs"] = runs
        project_json["latest_run"] = run_id
        project_json["updated_at"] = (
            datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
        )
        _atomic_write_json(project_json_path, project_json)
    except Exception as e:
        logger.error(f"Failed to finalize run metadata: {e}")


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

    if not args.project:
        args.project = os.path.basename(os.path.normpath(repo.workdir))
        logger.info(
            f"No project is specified, use the root folder name as project name: {args.project}"
        )

    # 如果指定了分支但没有指定提交哈希或指定比较提交哈希，则获取该分支的最新提交
    if args.branch and not args.snapshot and not args.history and not args.diff:
        latest_commit_hash = str(repo.branches[args.branch].target)
        logger.info(
            f"Without specifying a mode or commit, get the latest commit of {args.branch}: {latest_commit_hash}, executed in snapshot mode"
        )
        return "snap", args.project, args.branch, latest_commit_hash, ""

    if args.branch and args.snapshot:
        snapshot_commit_hash = parse_short_hash(repo, args.snapshot)
        return "snap", args.project, args.branch, snapshot_commit_hash, ""

    if args.branch and args.history:
        history_commit_hash = parse_short_hash(repo, args.history)
        return "hist", args.project, args.branch, history_commit_hash, ""

    if args.branch and args.diff:
        base_commit_hash = parse_short_hash(repo, args.diff[0])
        target_commit_hash = parse_short_hash(repo, args.diff[1])
        return "diff", args.project, args.branch, base_commit_hash, target_commit_hash

    if args.diff_branch:
        return "diffb", args.project, "", args.diff_branch[0], args.diff_branch[1]

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
        "--project",
        type=str,
        help="Specify the project name of the analysis task",
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
    mode, project, branch, base, target = resolve_branch_and_commits(args, repo)

    csv_cfg = output_config.get("csv") or {}
    artifacts_root = csv_cfg.get("path") if isinstance(csv_cfg, dict) else None
    if not artifacts_root:
        artifacts_root = os.path.join(repo.workdir, "artifacts")

    prep = load_runmeta_plugin()
    repo_path = args.repo
    run_dir = prep(
        artifacts_root=artifacts_root,
        project=project,
        mode=mode,
        branch=branch or "",
        base=base or "",
        target=target or "",
        repo_path=repo_path,
    )

    global run_dir_data
    run_dir_data = os.path.join(run_dir, "data")
    init_output(mode, run_dir_data)

    load_and_register_analyzers()

    if mode == "snap":
        commit_exec(repo, branch, base)
    elif mode == "hist":
        commit_exec(repo, branch, base)
    elif mode == "diff":
        diff_commit_exec(repo, branch, base, target)
    elif mode == "diffb":
        diff_branch_exec(repo, base, target)

    # Finalize metadata once processing succeeds
    if run_dir:
        _finalize_run_metadata(run_dir)
