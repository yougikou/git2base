import importlib
import os
import pygit2
from datetime import datetime
from pygit2.enums import DeltaStatus, DiffOption
from pygit2.repository import Repository

from config.config import load_analyzer_config
from database.model import AnalysisResult, Commit, CommitFile, DiffResult, FileSnapshot
from git.utils import get_git_file_snapshot, identify_tech_stack


DELTA_STATUS_MAP = {
    DeltaStatus.ADDED: "A",
    DeltaStatus.MODIFIED: "M",
    DeltaStatus.DELETED: "D",
    DeltaStatus.RENAMED: "R",
    DeltaStatus.COPIED: "C",
    DeltaStatus.UNMODIFIED: "=",
    DeltaStatus.UNTRACKED: "?",
    DeltaStatus.TYPECHANGE: "T",
    DeltaStatus.UNREADABLE: "!",
    DeltaStatus.CONFLICTED: "U",
    DeltaStatus.IGNORED: "I",
}


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
        class_name = analyzer_config["class"]
        module_name = f"analyzers.{class_name}"
        try:
            module = importlib.import_module(module_name)
            analyzer_class = getattr(module, class_name)
            loaded_analyzers[class_name] = analyzer_class
        except (ImportError, AttributeError) as e:
            raise ImportError(f"Failed to load {class_name} from {module_name}: {e}")
    return loaded_analyzers


analyzers = load_analyzer_config()
loadedAnalyzers = _load_analyzers(analyzers) if analyzers else {}

def apply_analysis(
    repo: Repository,
    commit_hash: str | None,
    file_path: str | None,
    file_hash: str | None,
    tech_stack: str | None,
) -> tuple[FileSnapshot, list[AnalysisResult]]:
    snapshot = get_git_file_snapshot(file_hash, repo) if file_hash else "<invalid>"
    file_snapshot = FileSnapshot(
        commit_file_hash=file_hash,
        content_snapshot=snapshot,
    )

    if tech_stack is None:
        print(f"No tech stack identified for file: {file_path}")
        return file_snapshot, []

    results = []
    for analyzer_config in analyzers:
        if (
            tech_stack not in analyzer_config["tech_stacks"]
            and "All" not in analyzer_config["tech_stacks"]
        ):
            continue

        analyzer_class = loadedAnalyzers[analyzer_config["class"]]
        params = analyzer_config.get("params", None)
        analyzer = analyzer_class(params or {})

        if snapshot and snapshot not in [
            "<invalid>",
            "<binary>",
            "<utf-8-decode-error>",
        ]:
            count, content = analyzer.analyze(snapshot)
        else:
            count, content = 0, None

        results.append(
            AnalysisResult(
                commit_hash=commit_hash,
                path=file_path,
                analyzer_type=analyzer_config["name"],
                count=count,
                content=content,
            )
        )

    return file_snapshot, results


def get_file_level_line_and_char_changes(
    repo: Repository, base_commit: pygit2.Commit, target_commit: pygit2.Commit
):
    """Used for work effort"""
    diff = target_commit.tree.diff_to_tree(
        base_commit.tree,
        flags=DiffOption.IGNORE_WHITESPACE
        | DiffOption.IGNORE_WHITESPACE_CHANGE
        | DiffOption.IGNORE_WHITESPACE_EOL
        | DiffOption.IGNORE_BLANK_LINES,
    )

    file_changes = []

    for patch in diff:
        file_path = patch.delta.new_file.path or patch.delta.old_file.path
        added_lines = 0
        deleted_lines = 0
        added_chars = 0
        deleted_chars = 0

        for hunk in patch.hunks:
            for line in hunk.lines:
                line_text = line.content.strip()
                if not line_text:  # 忽略空白行
                    continue
                if line.origin == "+":
                    added_lines += 1
                    added_chars += len(line_text)
                elif line.origin == "-":
                    deleted_lines += 1
                    deleted_chars += len(line_text)

        file_changes.append(
            {
                "file_path": file_path,
                "added_lines": added_lines,
                "deleted_lines": deleted_lines,
                "added_chars": added_chars,
                "deleted_chars": deleted_chars,
            }
        )

    return file_changes


class SnapshotAnalysisWrapper:
    def __init__(self, repo: Repository, branch: str, commit: pygit2.Commit):
        self.repo = repo
        self.branch = branch
        self.commit = commit

    def get_db_commit(self) -> Commit:
        return Commit(
            repository=self.repo.path,
            hash=str(self.commit.id),
            branch=self.branch,
            message=self.commit.message,
            author_name=self.commit.author.name,
            author_email=self.commit.author.email,
            author_date=datetime.fromtimestamp(self.commit.author.time),
            committer_name=self.commit.committer.name,
            committer_email=self.commit.committer.email,
            commit_date=datetime.fromtimestamp(self.commit.commit_time),
        )

    def get_db_commit_files(self) -> list[CommitFile]:
        def walk_tree(tree, path):
            for entry in tree:
                full_path = os.path.join(path, entry.name)
                if entry.type_str == "tree":
                    yield from walk_tree(self.repo[entry.id], full_path)
                elif entry.type_str == "blob":
                    yield full_path, entry.id

        files = []
        repo_root = os.path.abspath(os.path.join(self.repo.path, ".."))
        for file_path, file_oid in walk_tree(self.commit.tree, repo_root):
            related_path = os.path.relpath(file_path, repo_root)
            tech_stack = identify_tech_stack(related_path)

            files.append(
                CommitFile(
                    commit_hash=str(self.commit.id),
                    path=related_path,
                    tech_stack=tech_stack,
                    hash=str(file_oid),
                )
            )

        return files

    def exec_analysis(
        self, file: CommitFile
    ) -> tuple[FileSnapshot, list[AnalysisResult]]:
        return apply_analysis(
            self.repo,
            str(file.commit_hash) if file.commit_hash is not None else None,
            str(file.path) if file.path is not None else None,
            str(file.hash) if file.hash is not None else None,
            str(file.tech_stack) if file.tech_stack is not None else None,
        )


class DiffAnalysisWrapper:
    def __init__(
        self,
        repo: Repository,
        base_branch: str,
        target_branch: str,
        base_commit: pygit2.Commit,
        target_commit: pygit2.Commit,
    ):
        self.repo = repo
        self.base_branch = base_branch
        self.target_branch = target_branch
        self.base_commit = base_commit
        self.target_commit = target_commit
        self.diff = self.target_commit.tree.diff_to_tree(self.base_commit.tree)

    def get_db_commits(self) -> list[Commit]:
        return [
            Commit(
                repository=self.repo.path,
                hash=str(self.base_commit.id),
                branch=self.base_branch,
                message=self.base_commit.message,
                author_name=self.base_commit.author.name,
                author_email=self.base_commit.author.email,
                author_date=datetime.fromtimestamp(self.base_commit.author.time),
                committer_name=self.base_commit.committer.name,
                committer_email=self.base_commit.committer.email,
                commit_date=datetime.fromtimestamp(self.base_commit.commit_time),
            ),
            Commit(
                repository=self.repo.path,
                hash=str(self.target_commit.id),
                branch=self.target_branch,
                message=self.target_commit.message,
                author_name=self.target_commit.author.name,
                author_email=self.target_commit.author.email,
                author_date=datetime.fromtimestamp(self.target_commit.author.time),
                committer_name=self.target_commit.committer.name,
                committer_email=self.target_commit.committer.email,
                commit_date=datetime.fromtimestamp(self.target_commit.commit_time),
            ),
        ]

    def get_db_diff_results(self) -> list[DiffResult]:
        files = []
        for patch in self.diff:
            diff_result = DiffResult(
                base_commit_hash=str(self.base_commit.id),
                target_commit_hash=str(self.target_commit.id),
                base_path=patch.delta.old_file.path,
                target_path=patch.delta.new_file.path,
                diff_change_type=DELTA_STATUS_MAP.get(patch.delta.status, "X"),
                base_tech_stack=identify_tech_stack(patch.delta.old_file.path),
                target_tech_stack=identify_tech_stack(patch.delta.new_file.path),
                base_file_hash=str(patch.delta.old_file.id),
                target_file_hash=str(patch.delta.new_file.id),
            )
            files.append(diff_result)
        return files

    def exec_analysis(
        self, d: DiffResult
    ) -> tuple[list[FileSnapshot], list[AnalysisResult]]:
        base_file_snapshot, base_analysis_results = apply_analysis(
            self.repo,
            str(d.base_commit_hash) if d.base_commit_hash is not None else None,
            str(d.base_path) if d.base_path is not None else None,
            str(d.base_file_hash) if d.base_file_hash is not None else None,
            str(d.base_tech_stack) if d.base_tech_stack is not None else None,
        )
        target_file_snapshot, target_analysis_results = apply_analysis(
            self.repo,
            str(d.target_commit_hash) if d.target_commit_hash is not None else None,
            str(d.target_path) if d.target_path is not None else None,
            str(d.target_file_hash) if d.target_file_hash is not None else None,
            str(d.target_tech_stack) if d.target_tech_stack is not None else None,
        )
        return [
            base_file_snapshot,
            target_file_snapshot,
        ], base_analysis_results + target_analysis_results
