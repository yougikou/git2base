import os
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm


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


import ipywidgets as widgets
from IPython.display import display


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
    repo_names = sorted(
        [
            name
            for name in os.listdir(base_dir)
            if os.path.isdir(os.path.join(base_dir, name))
        ]
    )

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
        if selected_repo:
            run_path = os.path.join(base_dir, selected_repo, "runs")
            runs = sorted(os.listdir(run_path), reverse=True)
            run_selector.options = runs
            if runs:
                run_selector.value = runs[0]

    repo_selector.observe(update_runs, names="value")
    update_runs()

    display(repo_selector, run_selector)

    return repo_selector, run_selector


import pandas as pd
from typing import Dict, Tuple


def load_csv_results(
    repo_selector, run_selector, base_dir
) -> Tuple[str, Dict[str, pd.DataFrame]]:
    """
    根据 repo_selector 和 run_selector 加载指定路径下的标准 CSV 文件。
    返回值：
        - 选定路径
        - 加载后的 DataFrame 字典（键是变量名）
    """
    selected_repo = str(repo_selector.value)
    selected_run = str(run_selector.value)
    selected_path = os.path.join(base_dir, selected_repo, "runs", selected_run, "data")
    print("Selected path:", selected_path)

    # 要加载的文件名列表
    csv_files = {
        "commit_files.csv": "commit_files_df",
        "diff_results.csv": "diff_results_df",
        "analysis_results.csv": "analysis_results_df",
        "commits.csv": "commits_df",
    }

    # 用于保存加载结果
    loaded_dfs: Dict[str, pd.DataFrame] = {}

    for file_name, var_name in csv_files.items():
        file_path = os.path.join(selected_path, file_name)
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path)
                loaded_dfs[var_name] = df
                print(f"✅ Loaded: {file_name} ({len(df)} rows)")
            except Exception as e:
                print(f"⚠️ Failed to load: {file_name}, error: {e}")
        else:
            print(f"❌ File not found: {file_name}")

    return selected_path, loaded_dfs
