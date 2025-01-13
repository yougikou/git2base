# Git2Base

Git2Base is a Python tool for extracting and analyzing Git repository data into a PostgreSQL database. It provides:

- Import of Git commit history and file changes into a structured database schema
- Diff analysis between commits  
- Extensible analysis framework for processing repository data

## Installation

1. Install requirements:
```bash
pip install -r requirements.txt
```

2. Configure database connection in config.yaml:
```yaml
database:
  host: localhost
  port: 5432
  dbname: git2base
  user: postgres
  password: password
```

3. Initialize database schema:
```bash
python main.py --reset
```

## Database Schema

```sql
git_commits:
  id, commit_hash, branch, commit_date, commit_message, author_name, author_email

git_files:
  id, file_path, file_type, change_type, char_length, line_count, blob_hash

git_diff_files:
  commit_hash1_id, commit_hash2_id, file_path, file_type, change_type,
  line_count1, blob_hash1, content_snapshot1, line_count2, blob_hash2, content_snapshot2
```

## Usage

### Import Git Data

- Reset database:
```bash
python main.py --reset
```

- Extract branch commit history from start/latest commit:
```bash
python main.py --repo /path/to/repo --branch <branch-name>
```

- Extract branch commit history from specific commit:
```bash
python main.py --repo /path/to/repo --branch <branch-name> --commit_hash <hash>
```

- Extract diff between two commits:
```bash
python main.py --repo /path/to/repo --diff <hash1> <hash2>
```

- Analyze existing diffs:
```bash
python main.py --analyze <hash1> <hash2>
```

## Analyzers

Git2Base 提供了一个可扩展的分析器框架，支持动态加载和注册分析器。

### 现有分析器

- RegexMatchCountAnalyzer: 统计文件中正则表达式的匹配次数
- XMLElementCountAnalyzer: 统计XML文件中的元素数量

### 实现新的分析器

1. 创建新的分析器类，继承自 `BaseAnalyzer`
2. 实现以下必需方法：
   - `get_description()`: 返回分析器描述
   - `get_test_cases()`: 返回测试用例列表
   - `analyze()`: 实现分析逻辑
3. 添加自动注册功能：
   ```python
   @classmethod
   def register(cls):
       register_analyzer("your_analyzer_name", cls)
       
   # 在文件末尾添加自动注册
   YourAnalyzer.register()
   ```

### 测试代码示例

#### RegexMatchCountAnalyzer 测试
```python
from analyzers import get_analyzer

params = {
    "patterns": [r"\bclass\b"]
}
analyzer = get_analyzer("regex_match_count", params)

content = """
public class MyClass {
    private int x;
}
"""

count, result = analyzer.analyze(content)
print(f"匹配次数: {count}")
print(f"详细结果: {result}")
```

#### XMLElementCountAnalyzer 测试
```python
from analyzers import get_analyzer

analyzer = get_analyzer("xml_element_count", {})

content = """
<root>
    <child>test</child>
</root>
"""

count, result = analyzer.analyze(content)
print(f"元素数量: {count}")
```

### 分析器注册机制

分析器框架支持动态加载和注册：
- 使用 `register_analyzer()` 注册分析器
- 使用 `get_analyzer()` 获取分析器实例
- 支持从配置文件加载分析器参数

## Sample Queries

Example SQL queries are provided in the sample-queries/ directory:

- file-count.sql: Count files by type
- stack-files-count.sql: Count files in a stack
- XMLElem.sql: Query XML element counts

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

Please ensure all code follows PEP 8 style guidelines.
