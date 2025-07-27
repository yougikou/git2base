from database.connection import session_scope
from database.model import AnalysisResult, Commit, CommitFile, DiffResult, FileSnapshot


def insert_commits(commits_data: list[Commit]) -> list[Commit]:
    copies = []
    try:
        with session_scope() as session:
            session.add_all(commits_data)
            session.commit()
            for c in commits_data:
                copies.append(
                    Commit(
                        id=c.id,
                        repository=c.repository,
                        branch=c.branch,
                        hash=c.hash,
                        message=c.message,
                        author_name=c.author_name,
                        author_email=c.author_email,
                        author_date=c.author_date,
                        committer_name=c.committer_name,
                        committer_email=c.committer_email,
                        commit_date=c.commit_date,
                    )
                )
        return copies
    except Exception as e:
        print(f"插入提交及文件记录失败: {str(e)}")
        raise


def insert_diff_results(diff_results_data: list[DiffResult]) -> list[DiffResult]:
    copies = []
    try:
        with session_scope() as session:
            session.add_all(diff_results_data)
            session.flush()
            for d in diff_results_data:
                copies.append(
                    DiffResult(
                        id=d.id,
                        base_commit_hash=d.base_commit_hash,
                        target_commit_hash=d.target_commit_hash,
                        base_path=d.base_path,
                        target_path=d.target_path,
                        diff_change_type=d.diff_change_type,
                        base_tech_stack=d.base_tech_stack,
                        target_tech_stack=d.target_tech_stack,
                        base_file_hash=d.base_file_hash,
                        target_file_hash=d.target_file_hash,
                        hunk_char_count=d.hunk_char_count,
                        hunk_line_count=d.hunk_line_count,
                    )
                )
        return copies
    except Exception as e:
        print(f"Failed to insert diff result records: {str(e)}")
        raise


def insert_commit_files(commit_files_data: list[CommitFile]) -> list[CommitFile]:
    copies = []
    try:
        with session_scope() as session:
            session.add_all(commit_files_data)
            session.flush()
            for f in commit_files_data:
                copies.append(
                    CommitFile(
                        id=f.id,
                        commit_hash=f.commit_hash,
                        path=f.path,
                        tech_stack=f.tech_stack,
                        hash=f.hash,
                    )
                )
        return copies
    except Exception as e:
        print(f"插入提交及文件记录失败: {str(e)}")
        raise


def insert_analysis_results(
    analysis_results_data: list[AnalysisResult],
):
    try:
        with session_scope() as session:
            session.add_all(analysis_results_data)
    except Exception as e:
        print(f"插入分析结果失败: {str(e)}")
        raise


def insert_file_snapshot(file_snapshots_data: list[FileSnapshot]):
    try:
        with session_scope() as session:
            session.add_all(file_snapshots_data)
    except Exception as e:
        print(f"插入文件快照失败: {str(e)}")
        raise
