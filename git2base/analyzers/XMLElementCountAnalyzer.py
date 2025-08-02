from typing import Dict, Any, List
import xml.etree.ElementTree as ET
from analyzers.base_analyzer import BaseAnalyzer, register_analyzer

class XMLElementCountAnalyzer(BaseAnalyzer):
    """XML元素计数分析器"""
    
    @classmethod
    def register(cls):
        """注册分析器"""
        register_analyzer("xml_element_count", cls)

    
    def get_description(self) -> str:
        return "分析XML文件中的元素总数"
    
    def get_test_cases(self) -> List[Dict[str, Any]]:
        """获取测试用例"""
        return [
            {
                "name": "基本XML",
                "content": "<root><child>test</child></root>",
                "expected_count": 2,
                "expected_result": None
            }
        ]

    def analyze(self, file_content: str) -> tuple[int, dict | None]:
        try:
            root = ET.fromstring(file_content)
            count = sum(1 for _ in root.iter())
            return count, None
            
        except ET.ParseError:
            return 0, None

# 模块加载时自动注册分析器
XMLElementCountAnalyzer.register()
