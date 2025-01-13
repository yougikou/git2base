# Git2Base

Git2Base 是一个将Git仓库数据提取并分析到PostgreSQL数据库的Python工具。它提供以下功能：

- 将Git提交历史和文件变更导入结构化数据库模式
- 提交之间的差异分析
- 可扩展的仓库数据处理框架

## 安装

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 在config.yaml中配置数据库连接：
```yaml
database:
  host: localhost
  port: 5432
  dbname: git2base
  user: postgres
  password: password
```

3. 初始化数据库模式：
```bash
python main.py --reset
```

## 数据库模式

```sql
git_commits:
  id, commit_hash, branch, commit_date, commit_message, author_name, author_email

git_files:
  id, file_path, file_type, change_type, char_length, line_count, blob_hash

git_diff_files:
  commit_hash1_id, commit_hash2_id, file_path, file_type, change_type,
  line_count1, blob_hash1, content_snapshot1, line_count2, blob_hash2, content_snapshot2
```

## 使用说明

### 导入Git数据

- 重置数据库：
```bash
python main.py --reset
```

- 从起始/最新提交提取分支提交历史：
```bash
python main.py --repo /path/to/repo --branch <branch-name>
```

- 从特定提交提取分支提交历史：
```bash
python main.py --repo /path/to/repo --branch <branch-name> --commit_hash <hash>
```

- 提取两个提交之间的差异：
```bash
python main.py --repo /path/to/repo --diff <hash1> <hash2>
```

- 分析现有差异：
```bash
python main.py --analyze <hash1> <hash2>
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

## 贡献指南

1. Fork 本仓库
2. 创建特性分支
3. 提交Pull Request

请确保所有代码遵循PEP 8风格指南。
