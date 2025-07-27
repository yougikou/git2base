# Git2Base

[中文版本](../readme.md)

Git2Base is a Python tool that extracts and analyzes Git repository data into a PostgreSQL database. It provides the following features:

- Import Git commit history and file changes into a structured database schema or CSV for data analysis and mining
- Difference analysis between commits
- Extensible repository data processing framework

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure CSV output or database connection in config.yaml:
```yaml
output:
  type: "csv"  # Supports postgresql, sqlite, or csv
  csv:
    path: "<full path>"
  postgresql:
    host: "localhost"
    port: 5432
    database: "gitbase"
    user: "gituser"
    password: "giko"
  sqlite:
    database: "<full path>/gitbase.db"  # SQLite database file path
```

## Data Structure

The following is the data structure used by Git2Base:
- Diff: When analyzing differences between two commits/branches, DiffResult is mainly used
  - 2 Commits
  - Multiple DiffResults
  - Each DiffResult has new and old AnalysisResult sets

- Snapshot: When analyzing a snapshot of a commit, CommitFile is mainly used
  - 1 Commit
  - Multiple CommitFiles
  - Each CommitFile has one AnalysisResult set

- History: (TODO) Used to collect all commits and file differences (Hunks) for each commit (and parent commit)
  - Multiple Commits
  - Multiple DiffResults (containing string/line count changes in Hunks, no static analysis for files)

<img src="assets/gitbase-er.svg" alt="Architecture Diagram" width="600">

### Table Descriptions

- `git_commit`: Stores basic Git commit information, including commit hash, author, committer, time, etc.
- `git_commit_file`: Stores file information contained in each commit, including file path, technology stack classification, etc.
- `git_diff_result`: Stores information about file differences between two commits, including change type, file hash, etc.
- `git_analysis_result`: Stores analysis results of files by analyzers, including match count and detailed content.
- `git_file_snapshot`: Stores snapshots of file content for analysis and comparison.

## Usage Instructions

### Import Git Data

- Reset database:
```bash
python main.py --reset-db
```

- Extract complete file structure snapshot from a specified commit for analysis (if --branch is omitted, the currently checked out branch is used; if commit hash is omitted, the latest commit of the current branch is used):
```bash
# Use the currently checked out branch and latest commit
python main.py --repo /path/to/repo

# Specify branch and latest commit
python main.py --repo /path/to/repo --branch main

# Specify branch and specific commit
python main.py --repo /path/to/repo --branch main --commit_hash a1b2c3d
```

- Extract difference files between two commits for analysis (if branch is not specified, the currently checked out branch is used):
```bash
# Compare differences between two commits (using current branch)
python main.py --repo /path/to/repo --diff a1b2c3d e5f6g7h

# Compare differences between two commits (specify branch)
python main.py --repo /path/to/repo --branch main --diff a1b2c3d e5f6g7h
```

- Extract difference files between two branches for analysis (automatically uses the latest commit of each branch):
```bash
# Compare latest commits of two branches
python main.py --repo /path/to/repo --diff-branch main feature-branch
```

### Configure Output Mode

Git2Base supports multiple output modes, including CSV, PostgreSQL, and SQLite. You can switch output modes by modifying the `output.type` parameter in the `config/config.yaml` file.

#### CSV Mode
```bash
# Set output.type to "csv" in config.yaml
# Then run the command
python main.py --repo /path/to/repo --branch main
```

#### PostgreSQL Mode
```bash
# Set output.type to "postgresql" in config.yaml
# Configure the corresponding database connection parameters
# Then run the command
python main.py --repo /path/to/repo --branch main
```

#### SQLite Mode
```bash
# Set output.type to "sqlite" in config.yaml
# Configure the corresponding database file path
# Then run the command
python main.py --repo /path/to/repo --branch main
```

## Analyzers

Git2Base provides an extensible analyzer framework that supports dynamic loading and registration of analyzers.

### Existing Analyzers

- RegexMatchCountAnalyzer: Counts the number of regex matches in files
- XMLElementCountAnalyzer: Counts elements in XML files

### Implementing New Analyzers

1. Create a new analyzer class that inherits from `BaseAnalyzer`
2. Implement the following required methods:
   - `get_description()`: Returns analyzer description
   - `get_test_cases()`: Returns a list of test cases
   - `analyze()`: Implements analysis logic
3. Add auto-registration functionality:
   ```python
   @classmethod
   def register(cls):
       register_analyzer("your_analyzer_name", cls)
       
   # Add auto-registration at the end of the file
   YourAnalyzer.register()
   ```

### Test Instructions

#### Running Tests
```bash
python -m unittest tests/test_analyzers.py -v
```

#### Test Case Structure
Each test case should contain the following fields:
- content: Test content (string)
- expected_count: Expected number of matches (integer)
- expected_result: Expected result (dictionary, will be converted to JSON string for comparison)
- name: Test case name (optional)

#### Test Result Comparison
The test framework uses JSON string comparison to verify analysis results:
1. Convert actual and expected results to JSON strings
2. Sort and normalize JSON strings
3. Compare normalized JSON strings

#### Test Code Example
```python
{
    "name": "Simple class definition match",
    "content": "public class MyClass {}",
    "expected_count": 1,
    "expected_result": {
        "class": ["MyClass"]
    }
}
```

### Analyzer Registration Mechanism

The analyzer framework supports dynamic loading and registration:
- Use `register_analyzer()` to register analyzers
- Use `get_analyzer()` to get analyzer instances
- Support loading analyzer parameters from configuration files

## Example Queries for Result Statistics

Example SQL queries are located in the sample-queries/ directory:

- file-count.sql: Count files by type
- stack-files-count.sql: Count files in stacks
- XMLElem.sql: Query XML elements

## Integration with Git Tools

Using command-line configuration shortcuts in Git tools can achieve the purpose of graphical interface usage. Therefore, this tool does not intend to provide graphical interface support for the data collection part.

## Contribution Guidelines

1. Fork this repository
2. Create a feature branch
3. Submit a Pull Request

Please ensure all code follows the PEP 8 style guide.