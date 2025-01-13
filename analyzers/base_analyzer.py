from abc import ABC, abstractmethod
from typing import Dict, Any, List, Type
import importlib

# 分析器注册表
_ANALYZER_REGISTRY = {}

def register_analyzer(name: str, analyzer_class: Type['BaseAnalyzer']):
    """注册分析器类"""
    _ANALYZER_REGISTRY[name] = analyzer_class

def get_analyzer(name: str, params: Dict[str, Any]) -> 'BaseAnalyzer':
    """获取分析器实例"""
    if name not in _ANALYZER_REGISTRY:
        # 尝试动态加载模块
        module_name = f"analyzers.{name}"
        try:
            importlib.import_module(module_name)
        except ImportError:
            raise ValueError(f"无法找到分析器: {name}")
            
    if name not in _ANALYZER_REGISTRY:
        raise ValueError(f"分析器 {name} 未注册")
        
    return _ANALYZER_REGISTRY[name](params)

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
    
    def analyze(self, file_content: str) -> tuple[int, dict]:
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
        return (
            isinstance(count, int) and
            isinstance(result, dict)
        )
