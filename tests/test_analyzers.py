import json
import unittest
import logging
from analyzers.RegexMatchCountAnalyzer import RegexMatchCountAnalyzer
from analyzers.XMLElementCountAnalyzer import XMLElementCountAnalyzer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
                logger.info(f"开始测试 {analyzer_config['name']}")
                
                # 获取测试用例
                test_cases = analyzer.get_test_cases()
                logger.info(f"{analyzer_config['name']} 测试用例数量: {len(test_cases)}")
                
                # 执行所有测试用例
                for i, test_case in enumerate(test_cases, 1):
                    with self.subTest(test_case=i):
                        logger.info(f"正在执行测试用例 {i}: {test_case['name']}")
                        logger.debug(f"测试内容:\n{test_case['content']}")
                        
                        # 执行分析
                        count, result = analyzer.analyze(test_case["content"])
                        
                        # 验证结果
                        self.assertEqual(count, test_case["expected_count"])
                        
                        # 将结果和预期结果转换为JSON字符串进行比较
                        result_json = json.dumps(result, sort_keys=True)
                        expected_json = json.dumps(test_case["expected_result"], sort_keys=True)
                        logger.debug(result_json)
                        self.assertEqual(result_json, expected_json)
                        
                        logger.info(f"测试用例 {i} 通过")
                
                logger.info(f"{analyzer_config['name']} 所有测试结束")

if __name__ == '__main__':
    unittest.main()
