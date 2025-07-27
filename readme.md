# Git2Base

[English Version](doc/README_EN.md)

Git2Base 是一个将Git仓库数据提取并分析到PostgreSQL数据库的Python工具。它提供以下功能：

- 将Git提交历史和文件变更导入结构化数据库模式或者CSV以供数据分析挖掘
- 提交之间的差异分析
- 可扩展的仓库数据处理框架

## 安装

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 在config.yaml中配置CSV输出或者数据库连接：
```yaml
output:
  type: "csv"  # 支持postgresql或sqlite或者csv
  csv:
    path: "<full path>"
  postgresql:
    host: "localhost"
    port: 5432
    database: "gitbase"
    user: "gituser"
    password: "giko"
  sqlite:
    database: "<full path>/gitbase.db"  # SQLite数据库文件路径
```

## 使用的数据结构

以下是Git2Base使用的数据结构，以及：
- Diff: 分析两个提交/分支的差异时候主要使用DiffResult
  - 2个Commit
  - 多个DiffResult
  - 每个DiffResult有新旧两组AnalysisResult

- Snapshot: 分析某个提交的快照的时候主要使用CommitFile
  - 1个Commit
  - 多个CommitFile
  - 每个CommitFile有一组AnalysisResult

- History: （TODO）用于收集所有提交以及每个提交（和父提交）的文件差异（Hunk）
  - 多个Commit
  - 多个DiffResult（包含Hunk的字符串/行数变更，无需针对文件的静态分析）

<img src="doc/assets/gitbase-er.svg" alt="架构图" width="600">

### 表说明

- `git_commit`: 存储Git提交的基本信息，包括提交哈希、作者、提交者、时间等。
- `git_commit_file`: 存储每个提交中包含的文件信息，包括文件路径、技术栈分类等。
- `git_diff_result`: 存储两个提交之间文件差异的信息，包括变更类型、文件哈希等。
- `git_analysis_result`: 存储分析器对文件的分析结果，包括匹配次数和详细内容。
- `git_file_snapshot`: 存储文件内容的快照，用于分析和比较。

## 使用说明

### 导入Git数据

- 重置数据库：
```bash
python main.py --reset-db
```

- 从指定提交提取完整文件结构快照进行分析（如果省略--branch则使用当前检出分支，如果省略提交哈希则使用当前分支最新提交）：
```bash
# 使用当前检出的分支和最新提交
python main.py --repo /path/to/repo

# 指定分支和最新提交
python main.py --repo /path/to/repo --branch main

# 指定分支和特定提交
python main.py --repo /path/to/repo --branch main --commit_hash a1b2c3d
```

- 提取两个提交之间的差异文件进行分析（不指定分支的时候使用当前检出的分支）：
```bash
# 比较两个提交的差异（使用当前分支）
python main.py --repo /path/to/repo --diff a1b2c3d e5f6g7h

# 比较两个提交的差异（指定分支）
python main.py --repo /path/to/repo --branch main --diff a1b2c3d e5f6g7h
```

- 提取两个分支之间的差异文件进行分析（自动使用各个分支的最新提交）：
```bash
# 比较两个分支的最新提交
python main.py --repo /path/to/repo --diff-branch main feature-branch
```

### 配置输出模式

Git2Base 支持多种输出模式，包括 CSV、PostgreSQL 和 SQLite。可以通过修改 `config/config.yaml` 文件中的 `output.type` 参数来切换输出模式。

#### CSV 模式
```bash
# 在 config.yaml 中设置 output.type 为 "csv"
# 然后运行命令
python main.py --repo /path/to/repo --branch main
```

#### PostgreSQL 模式
```bash
# 在 config.yaml 中设置 output.type 为 "postgresql"
# 配置相应的数据库连接参数
# 然后运行命令
python main.py --repo /path/to/repo --branch main
```

#### SQLite 模式
```bash
# 在 config.yaml 中设置 output.type 为 "sqlite"
# 配置相应的数据库文件路径
# 然后运行命令
python main.py --repo /path/to/repo --branch main
```

## 分析器

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

### 测试说明

#### 运行测试
```bash
python -m unittest tests/test_analyzers.py -v
```

#### 测试用例结构
每个测试用例应包含以下字段：
- content: 测试内容（字符串）
- expected_count: 预期匹配次数（整数）
- expected_result: 预期结果（字典，将被转换为JSON字符串进行比较）
- name: 测试用例名称（可选）

#### 测试结果比较
测试框架使用JSON字符串比较来验证分析结果：
1. 将实际结果和预期结果转换为JSON字符串
2. 对JSON字符串进行排序和规范化
3. 比较规范化后的JSON字符串

#### 测试代码示例
```python
{
    "name": "简单类定义匹配",
    "content": "public class MyClass {}",
    "expected_count": 1,
    "expected_result": {
        "class": ["MyClass"]
    }
}
```

### 分析器注册机制

分析器框架支持动态加载和注册：
- 使用 `register_analyzer()` 注册分析器
- 使用 `get_analyzer()` 获取分析器实例
- 支持从配置文件加载分析器参数

## 结果统计示例查询

示例SQL查询位于sample-queries/目录中：

- file-count.sql: 按类型统计文件数量
- stack-files-count.sql: 统计堆栈中的文件数量
- XMLElem.sql: 查询XML元素数量

## 与Git工具的集成
在Git工具中使用命令行配置快捷命令可以达到通过图形界面的使用目的。因此本工具对于数据收集部分不打算提供图形界面的支持。


## 贡献指南

1. Fork 本仓库
2. 创建特性分支
3. 提交Pull Request

请确保所有代码遵循PEP 8风格指南。
