from typing import Dict, Any, List
from analyzers.base_analyzer import BaseAnalyzer, register_analyzer


class FileCharCountAnalyzer(BaseAnalyzer):
    """文件字符计数分析器"""

    @classmethod
    def register(cls):
        """注册分析器"""
        register_analyzer("file_char_count", cls)

    def get_description(self) -> str:
        return "分析文件中的字符总数"

    def get_test_cases(self) -> List[Dict[str, Any]]:
        """获取测试用例"""
        return [
            {
                "name": "基本文本",
                "content": "这是一个测试文本。",
                "expected_count": 10,
                "expected_result": None,
            }
        ]

    def analyze(self, file_content: str) -> tuple[int, dict | None]:
        try:
            # 获取文件中的字符总数
            count = len(file_content)
            return count, None

        except Exception:
            return 0, None


# 模块加载时自动注册分析器
FileCharCountAnalyzer.register()
