import pygit2
import os

# Mapping of Git delta status to change type
DELTA_STATUS_MAP = {
    pygit2.GIT_DELTA_ADDED: 'A',
    pygit2.GIT_DELTA_MODIFIED: 'M',
    pygit2.GIT_DELTA_DELETED: 'D',
    pygit2.GIT_DELTA_RENAMED: 'R',
    pygit2.GIT_DELTA_COPIED: 'C',
    pygit2.GIT_DELTA_UNMODIFIED: '=',
    pygit2.GIT_DELTA_UNTRACKED: '?',
    pygit2.GIT_DELTA_TYPECHANGE: 'T',
    pygit2.GIT_DELTA_UNREADABLE: '!',
    pygit2.GIT_DELTA_CONFLICTED: 'U'
}

def get_change_type(delta) -> str:
    """Get standardized change type from Git delta status"""
    return DELTA_STATUS_MAP.get(delta.status, 'X')

def get_file_type(file_path):
    if file_path.startswith("."):
        return "<dev-config>"
    file_ext = file_path.split(".")[-1] if "." in file_path else ""
    return file_ext if file_ext else "<no-extension>"

def identify_tech_stack(file_path, stacks):
    extension = os.path.splitext(file_path)[1]
    for stack in stacks:
        if any(file_path.startswith(path) for path in stack['paths']) and extension in stack['extensions']:
            return stack['name']
    return None