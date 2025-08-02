from typing import Dict, Any, List
from analyzers.base_analyzer import BaseAnalyzer, register_analyzer
import re

class RegexMatchCountAnalyzer(BaseAnalyzer):
    """正则表达式匹配计数分析器"""
    
    @classmethod
    def register(cls):
        """注册分析器"""
        register_analyzer("regex_match_count", cls)

    def __init__(self, params: Dict[str, Any]):
        if isinstance(params["patterns"], list):
            self.patterns = params["patterns"]
        else:
            raise ValueError("patterns参数必须是字符串列表")

    def get_description(self) -> str:
        return "分析文件中符合正规表达式的匹配数"

    def analyze(self, file_content: str) -> tuple[int, dict | None]:
        results = {}
        
        # 遍历patterns，对每个pattern进行匹配
        # 把匹配到的字符串储存到results中
        # 把匹配到的次数储存到count中
        for pattern in self.patterns:
            matches = re.findall(pattern, file_content)
            results[pattern] = {
                'count': len(matches),
                'matches': matches
            }
            
        return sum(value['count'] for value in results.values()), results

    def get_test_cases(self) -> List[Dict[str, Any]]:
        """获取测试用例"""
        return [
            {
                "name": "基本Java类定义",
                "content": """
                public class MyClass {
                    private int x;
                }
                """,
                "expected_count": 1,
                "expected_result": {
                    "(?<!\\w)\\bclass\\s+(\\w+)\\b(?:\\s+extends\\s+(\\w+))?(?:\\s+implements\\s+([\\w\\s,]+))?\\s*\\{": {
                        "count": 1, 
                        "matches": [["MyClass", "", ""]]
                    }
                }
            },
            {
                "name": "继承和实现的Java类",
                "content": """
                public class MyClass extends BaseClass implements Interface1, Interface2 {
                    private String name;
                }
                """, 
                "expected_count": 1,
                "expected_result": {
                    "(?<!\\w)\\bclass\\s+(\\w+)\\b(?:\\s+extends\\s+(\\w+))?(?:\\s+implements\\s+([\\w\\s,]+))?\\s*\\{": {
                        "count": 1, 
                        "matches": [["MyClass", "BaseClass", "Interface1, Interface2 "]]
                    }
                }
            }
        ]

# 模块加载时自动注册分析器
RegexMatchCountAnalyzer.register()
