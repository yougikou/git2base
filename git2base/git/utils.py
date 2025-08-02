import csv
import io
import os
import pygit2
from pygit2.repository import Repository
from typing import cast

from git2base.config import LOGGER_GIT2BASE, get_logger, load_stacks_config

logger = get_logger(LOGGER_GIT2BASE)

def is_binary(blob):
    if isinstance(blob, bytes):
        return b"\0" in blob[:1024]
    return False


def calculate_file_metrics(file_content):
    line_count = len(file_content.splitlines())
    char_length = len(file_content)
    return char_length, line_count


def parse_short_hash(repo, short_hash):
    commit = repo.revparse_single(short_hash)
    return str(commit.id)


def get_file_type(file_path):
    if file_path.startswith("."):
        return "<dev-config>"
    file_ext = file_path.split(".")[-1] if "." in file_path else ""
    return file_ext if file_ext else "<no-extension>"


def identify_tech_stack(file_path, stacks=load_stacks_config()):
    extension = get_file_type(file_path)
    for stack in stacks:
        """Check
        if extension matches stack extensions
        if file path starts with any of the stack paths
        if stack has no paths, it matches all files with the specified extensions"""
        if (
            (not stack["paths"] and extension in stack["extensions"])
            or (
                not stack["extensions"]
                and any(file_path.startswith(path) for path in stack["paths"])
            )
            or (
                any(file_path.startswith(path) for path in stack["paths"])
                and extension in stack["extensions"]
            )
        ):
            return stack["name"]
    return None


def get_git_file_snapshot(hash: str, repo: Repository) -> str:
    if hash == "0" * 40:
        return "<invalid>"

    oid = pygit2.Oid(hex=hash)
    try:
        blob = cast(pygit2.Blob, repo[oid]) if oid else None
        if blob:
            snapshot = (
                blob.data.decode("utf-8", "ignore").replace("\x00", "")
                if not is_binary(blob.data)
                else "<binary>"
            )
        else:
            snapshot = "<invalid>"
        return snapshot
    except UnicodeDecodeError:
        return "<utf-8-decode-error>"


def write_csv(rows: list[dict[str, str]], filename: str, append_mode=False):
    if not rows:
        logger.debug(f"No data to write to {filename}")
        return

    file_exists = os.path.exists(filename)

    if append_mode and file_exists:
        with open(filename, mode="r", encoding="utf-8") as f:
            existing_lines = f.readlines()
            if len(existing_lines) > 1:
                existing_header = next(csv.reader(io.StringIO(existing_lines[0]), quoting=csv.QUOTE_ALL))
                new_header = list(rows[0].keys())
                if existing_header != new_header:
                    raise ValueError(
                        "CSV header does not match existing file structure."
                    )
            write_header = len(existing_lines) <= 1

        with open(filename, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys(), quoting=csv.QUOTE_ALL)
            if write_header:
                writer.writeheader()
            writer.writerows(rows)
    else:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys(), quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)

    logger.debug(f"CSV {'appended to' if append_mode else 'written to'} {filename}")
