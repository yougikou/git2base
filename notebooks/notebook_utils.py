from typing import Dict, Tuple

import ipywidgets as widgets
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import display

from quickstart_dashboard import CSV_FILE_MAP, RunDataLoader


def set_cjk_font(verbose=True):
    # Preferred fonts list (for CJ: Chinese/Japanese)
    preferred_fonts = [
        "Noto Sans CJK JP",
        "Noto Sans CJK SC",
        "Microsoft YaHei",
        "SimHei",
        "Arial Unicode MS",
        "AppleGothic",
        "MS PGothic",
    ]

    for font in preferred_fonts:
        if any(font in f.name for f in fm.fontManager.ttflist):
            plt.rcParams["font.family"] = font
            plt.rcParams["axes.unicode_minus"] = False
            if verbose:
                print(f"✅ 已设置字体为：{font}")
            return font

    if verbose:
        print("⚠️ No available CJK font found. Please install Noto Sans CJK JP.")
    return None


def select_repo_and_run(
    base_dir="../artifacts",
) -> tuple[widgets.Dropdown, widgets.Dropdown]:
    """
    在 Jupyter Notebook 中创建两个级联下拉框用于选择：
    - repo（即仓库文件夹名）
    - run（每次执行生成的文件夹）

    返回：repo_selector, run_selector 两个 ipywidgets.Dropdown 对象
    """
    # 获取 repo 文件夹名
    loader = RunDataLoader(base_dir=base_dir)
    repo_names = loader.list_repos()

    # 创建 widgets
    repo_selector = widgets.Dropdown(
        options=repo_names, description="Repo:", layout=widgets.Layout(width="50%")
    )

    run_selector = widgets.Dropdown(
        options=[], description="Run:", layout=widgets.Layout(width="50%")
    )

    # repo 改变时更新 run 下拉框
    def update_runs(*args):
        selected_repo = repo_selector.value
        runs = loader.list_runs(selected_repo) if selected_repo else []
        run_selector.options = runs
        if runs:
            run_selector.value = runs[0]
        else:
            run_selector.value = None

    repo_selector.observe(update_runs, names="value")
    update_runs()

    display(repo_selector, run_selector)

    return repo_selector, run_selector


def load_csv_results(
    repo_selector, run_selector, base_dir
) -> Tuple[str, Dict[str, pd.DataFrame]]:
    """
    根据 repo_selector 和 run_selector 加载指定路径下的标准 CSV 文件。
    返回值：
        - 选定路径
        - 加载后的 DataFrame 字典（键是变量名）
    """
    loader = RunDataLoader(base_dir=base_dir)

    selected_repo = str(repo_selector.value)
    selected_run = str(run_selector.value)

    if not selected_repo or not selected_run:
        print("❌ Repo 或 Run 未选择，无法加载数据。")
        return "", {}

    run_data = loader.load_run(selected_repo, selected_run)
    if run_data is None:
        print("❌ 未找到指定运行的分析结果。")
        return "", {}

    selected_path = str(run_data.path)
    print("Selected path:", selected_path)

    loaded_dfs: Dict[str, pd.DataFrame] = {}
    for file_name, var_name in CSV_FILE_MAP.items():
        csv_path = run_data.path / file_name
        df = run_data.dataframes.get(var_name)
        if df is not None:
            loaded_dfs[var_name] = df
            print(f"✅ Loaded: {file_name} ({len(df)} rows)")
        elif csv_path.exists():
            # 文件存在但解析失败会在 load_run 中打印 warning
            print(f"⚠️ Failed to parse: {file_name}")
        else:
            print(f"❌ File not found: {file_name}")

    return selected_path, loaded_dfs
