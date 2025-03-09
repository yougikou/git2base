

import importlib
from db.operations import get_diff_data, save_analysis_result, analysis_exists
from git.config import load_analyzer_config
from tqdm import tqdm

def _load_analyzers(analyzers):
    """加载分析器类
    
    Args:
        analyzers: 分析器配置列表
        
    Returns:
        dict: 已加载的分析器类字典
        
    Raises:
        ImportError: 如果无法加载分析器
    """
    loaded_analyzers = {}
    for analyzer_config in analyzers:
        class_name = analyzer_config['class']
        module_name = f'analyzers.{class_name}'
        try:
            module = importlib.import_module(module_name)
            analyzer_class = getattr(module, class_name)
            loaded_analyzers[class_name] = analyzer_class
        except (ImportError, AttributeError) as e:
            raise ImportError(f"Failed to load {class_name} from {module_name}: {e}")
    return loaded_analyzers

def analyze_existing_diffs(commit_hash1, commit_hash2):
    # 获取数据库中的diff数据，然后进行分析
    diff_data = get_diff_data(commit_hash1, commit_hash2)

    total_files = len(diff_data)
    processed_count = 0

    with tqdm(total=total_files, desc="Processing analyzing", unit="file", bar_format="{desc}: {n_fmt}/{total_fmt} files") as pbar:
        for diff in diff_data:
            _analyze_diff(diff.id, diff.commit_1_id, diff.commit_2_id, 
                        diff.content_snapshot1, diff.content_snapshot2, diff.tech_stack)
            processed_count += 1
            pbar.n = processed_count
            pbar.refresh()

def _analyze_diff(diff_id, commit_1_id, commit_2_id, snapshot1, snapshot2, tech_stack):
    analyzers = load_analyzer_config()
    loadedAnalyzers = _load_analyzers(analyzers) if analyzers else {}

    if tech_stack:
        for analyzer_config in analyzers:
            if tech_stack in analyzer_config['tech_stacks']:
                analyzer_name = analyzer_config['name']
                
                # 检查是否已经分析过
                if not analysis_exists(analyzer_name, diff_id):
                    # 实例化分析器类
                    analyzer_class = loadedAnalyzers[analyzer_config['class']]
                    params = analyzer_config.get('params', None)
                    analyzer = analyzer_class(params or {})
                        
                    # 分析两个快照
                    if snapshot1 and snapshot1 not in ['<added>', '<binary>']:
                        count1, result1 = analyzer.analyze(snapshot1)
                    else:
                        count1, result1 = 0, None
                        
                    if snapshot2 and snapshot2 not in ['<deleted>', '<binary>']:
                        count2, result2 = analyzer.analyze(snapshot2)
                    else:
                        count2, result2 = 0, None
                    
                    save_analysis_result(analyzer_name, diff_id, commit_1_id, commit_2_id, count1, result1, count2, result2)

