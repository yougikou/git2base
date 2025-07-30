import json
import unittest
from analyzers.RegexMatchCountAnalyzer import RegexMatchCountAnalyzer
from analyzers.XMLElementCountAnalyzer import XMLElementCountAnalyzer
from config.config import get_logger

logger = get_logger("analyzer_test")

class TestAnalyzers(unittest.TestCase):
    
    def test_analyzers(self):
        """通用分析器测试方法"""
        # 定义要测试的分析器及其参数
        analyzers = [
            {
                "class": RegexMatchCountAnalyzer,
                "params": {"patterns": [r"(?<!\w)\bclass\s+(\w+)\b(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w\s,]+))?\s*\{"]},
                "name": "RegexMatchCountAnalyzer"
            },
            {
                "class": XMLElementCountAnalyzer,
                "params": {},
                "name": "XMLElementCountAnalyzer"
            }
        ]
        
        for analyzer_config in analyzers:
            with self.subTest(analyzer=analyzer_config["name"]):
                # 初始化分析器
                analyzer = analyzer_config["class"](analyzer_config["params"])
                logger.info(f"Start testing {analyzer_config['name']}")
                
                # 获取测试用例
                test_cases = analyzer.get_test_cases()
                logger.info(f"{analyzer_config['name']} Number of test cases: {len(test_cases)}")
                
                # 执行所有测试用例
                for i, test_case in enumerate(test_cases, 1):
                    with self.subTest(test_case=i):
                        logger.info(f"Executing test cases {i}: {test_case['name']}")
                        logger.debug(f"Test content:\n{test_case['content']}")
                        
                        # 执行分析
                        count, result = analyzer.analyze(test_case["content"])
                        
                        # 验证结果
                        self.assertEqual(count, test_case["expected_count"])
                        
                        # 将结果和预期结果转换为JSON字符串进行比较
                        result_json = json.dumps(result, sort_keys=True)
                        expected_json = json.dumps(test_case["expected_result"], sort_keys=True)
                        logger.debug(result_json)
                        self.assertEqual(result_json, expected_json)
                        
                        logger.info(f"Test case {i} passed")
                
                logger.info(f"{analyzer_config['name']} All tests completed")

if __name__ == '__main__':
    unittest.main()
