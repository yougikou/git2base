from abc import ABC, abstractmethod
from typing import Dict, Any, List
import importlib

from git2base.config import load_analyzer_config

# 分析器注册表
ANALYZER_REGISTRY = {}


def load_and_register_analyzers():
    user_module = None
    try:
        user_module = importlib.import_module("user_analyzers")
    except Exception as e:
        print(f"Warn: module user_analyzers load failed: {e} - only build-in analyzers will be loaded")

    analyzers_config = load_analyzer_config()
    for cfg in analyzers_config:
        class_name = cfg["class"]
        analyzer_name = cfg["name"]

        try:
            if ANALYZER_REGISTRY.get(analyzer_name, None):
                continue
            module = importlib.import_module(f"git2base.analyzers")
            analyzer_class = getattr(module, class_name)
            if not analyzer_class and user_module:
                analyzer_class = getattr(user_module, class_name)
            ANALYZER_REGISTRY[analyzer_name] = analyzer_class
        except Exception as e:
            print(f"Analyzer {analyzer_name} load failed: {e}")


class BaseAnalyzer(ABC):
    """
    分析器的基类，定义了所有分析器必须实现的接口
    """

    def __init__(self, params: Dict[str, Any]):
        pass

    @abstractmethod
    def get_description(self) -> str:
        """
        获取分析器的描述信息

        Returns:
            str: 分析器的描述文本
        """
        pass

    @abstractmethod
    def get_test_cases(self) -> List[Dict[str, Any]]:
        """
        获取测试用例列表

        Returns:
            List[Dict[str, Any]]: 测试用例列表，每个测试用例包含：
                - name: 测试用例名称
                - content: 测试内容
                - expected_count: 期望的分析数值结果
                - expected_result: 期望的分析详细结果
        """
        pass

    def analyze(self, file_content: str) -> tuple[int, dict | None]:
        """
        分析文件内容

        Args:
            file_content: 要分析的文件内容

        Returns:
            tuple[int, dict]: 返回一个元组，包含:
                - count: 分析得到的数值结果
                - result: 分析得到的详细结果字典
        """
        raise NotImplementedError("分析器必须实现 analyze 方法")

    def validate_result(self, count: int, result: Dict[str, Any]) -> bool:
        """
        验证分析结果是否有效

        Args:
            count: 分析得到的数值结果
            result: 分析得到的详细结果字典

        Returns:
            bool: 结果有效返回 True，否则返回 False
        """
        return isinstance(count, int) and isinstance(result, dict)
