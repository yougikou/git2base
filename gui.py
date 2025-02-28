import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import datetime
import pygit2
from git_operations import get_git_commits, get_git_commits_ui

class GitTab(ttk.Frame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.repo = None
        self.create_widgets()
        
    def create_widgets(self):
        # 仓库选择
        self.repo_frame = ttk.LabelFrame(self, text="仓库选择")
        self.repo_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.repo_entry = ttk.Entry(self.repo_frame)
        self.repo_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        self.repo_btn = ttk.Button(self.repo_frame, text="选择", command=self.select_repo)
        self.repo_btn.pack(side=tk.RIGHT, padx=5)
        
        # 分支选择
        self.branch_frame = ttk.LabelFrame(self, text="分支选择")
        self.branch_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.branch_var = tk.StringVar()
        self.branch_combo = ttk.Combobox(self.branch_frame, textvariable=self.branch_var)
        self.branch_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        self.refresh_btn = ttk.Button(self.branch_frame, text="刷新分支", command=self.refresh_branches)
        self.refresh_btn.pack(side=tk.RIGHT, padx=5)
        
        # 提交密度和过滤选项
        self.filter_frame = ttk.Frame(self)
        self.filter_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.density_frame = ttk.LabelFrame(self.filter_frame, text="提交密度")
        self.density_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        self.density_var = tk.StringVar(value="全部")
        self.density_combo = ttk.Combobox(self.density_frame, textvariable=self.density_var)
        self.density_combo['values'] = ("全部", "1周", "2周", "1个月", "3个月", "6个月", "1年")
        self.density_combo.pack(fill=tk.X, padx=5, pady=5)
        
        self.filter_branch_var = tk.BooleanVar(value=True)
        self.filter_branch_check = ttk.Checkbutton(self.filter_frame, 
                                                text="仅显示当前分支提交",
                                                variable=self.filter_branch_var)
        self.filter_branch_check.pack(side=tk.RIGHT, padx=5)
        
        self.refresh_commits_btn = ttk.Button(self.filter_frame, text="刷新提交列表", command=self.refresh_commits)
        self.refresh_commits_btn.pack(side=tk.RIGHT, padx=5)
        
        # 提交列表
        self.commit_frame = ttk.LabelFrame(self, text="提交列表")
        self.commit_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        columns = ("hash", "message", "author", "date", "branch")
        self.commit_tree = ttk.Treeview(self.commit_frame, columns=columns, show="headings")
        
        for col in columns:
            self.commit_tree.heading(col, text=col.capitalize())
            self.commit_tree.column(col, width=100)
            
        self.commit_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 提交输入框
        self.input_frame = ttk.Frame(self)
        self.input_frame.pack(fill=tk.X, padx=5, pady=5)

        # 提交1输入框
        self.commit1_frame = ttk.LabelFrame(self.input_frame, text="提交1")
        self.commit1_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.commit1_entry = ttk.Entry(self.commit1_frame)
        self.commit1_entry.pack(fill=tk.X, padx=5, pady=5)

        # 提交2输入框
        self.commit2_frame = ttk.LabelFrame(self.input_frame, text="提交2")
        self.commit2_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.commit2_entry = ttk.Entry(self.commit2_frame)
        self.commit2_entry.pack(fill=tk.X, padx=5, pady=5)

        # 设置拖拽功能
        self.commit_tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.commit1_entry.bind("<ButtonRelease-1>", lambda e: self.on_drop(e, self.commit1_entry))
        self.commit2_entry.bind("<ButtonRelease-1>", lambda e: self.on_drop(e, self.commit2_entry))

        # 操作按钮
        self.btn_frame = ttk.Frame(self)
        self.btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.get_all_btn = ttk.Button(self.btn_frame, text="获取分支所有提交", command=self.get_all_commits_cmd_preview)
        self.get_all_btn.pack(side=tk.LEFT, padx=5)
        
        self.get_after_btn = ttk.Button(self.btn_frame, text="获取指定提交后的所有提交", command=self.get_all_commit_after_cmd_preview)
        self.get_after_btn.pack(side=tk.LEFT, padx=5)
        
        self.compare_btn = ttk.Button(self.btn_frame, text="比较两个提交", command=self.get_compare_commits_cmd_preview)
        self.compare_btn.pack(side=tk.LEFT, padx=5)
        
        self.analyze_btn = ttk.Button(self.btn_frame, text="比较并分析两个提交", command=self.get_compare_commits_analyze_cmd_preview)
        self.analyze_btn.pack(side=tk.LEFT, padx=5)
        
        self.analyze_diff_btn = ttk.Button(self.btn_frame, text="分析两个提交", command=self.get_analyze_commits_diff_cmd_preview)
        self.analyze_diff_btn.pack(side=tk.LEFT, padx=5)
        
        # 命令行预览
        self.cmd_frame = ttk.LabelFrame(self, text="命令行预览")
        self.cmd_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.cmd_text = tk.Text(self.cmd_frame, height=2)
        self.cmd_text.pack(fill=tk.X, padx=5, pady=5)

        self.exec_btn = ttk.Button(self.cmd_frame, text="执行", command=self.execute_command)
        self.exec_btn.pack(side=tk.RIGHT, padx=5)

        # 重置数据库按钮
        self.reset_db_btn = ttk.Button(self.cmd_frame, text="重置数据库", command=self.reset_db_cmd)
        self.reset_db_btn.pack(side=tk.RIGHT, padx=5)        

        # 命令行输出窗口
        self.output_frame = ttk.LabelFrame(self, text="命令行输出")
        self.output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.output_text = tk.Text(self.output_frame)
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
    def select_repo(self):
        """选择git仓库目录"""
        repo_path = filedialog.askdirectory(title="选择Git仓库目录")
        if not repo_path:
            return
            
        try:
            # 验证是否是有效的git仓库
            self.repo = pygit2.Repository(repo_path)
            self.repo_entry.delete(0, tk.END)
            self.repo_entry.insert(0, repo_path)
            self.refresh_branches()  # 自动刷新分支列表
        except pygit2.GitError as e:
            messagebox.showerror("错误", f"选择的目录不是有效的Git仓库:\n{str(e)}")
            self.repo = None
        
    def refresh_branches(self):
        """刷新分支列表"""
        if not self.repo:
            messagebox.showwarning("警告", "请先选择有效的Git仓库")
            return
            
        try:
            # 获取所有本地分支
            branches = [
                ref.replace("refs/heads/", "")
                for ref in self.repo.listall_references()
                if ref.startswith("refs/heads/")
            ]
            
            self.branch_combo['values'] = branches
            if branches:
                self.branch_combo.current(0)
        except Exception as e:
            messagebox.showerror("错误", f"刷新分支失败:\n{str(e)}")

    def refresh_commits(self):
        if not self.repo:
            messagebox.showwarning("警告", "请先选择有效的Git仓库")
            return
        
        try:
            # 获取当前选择的提交密度
            density = self.density_var.get()
            
            # "仅显示当前分支提交"勾选框勾选时，仅获取当前分支
            if self.filter_branch_var.get():
                branch_name = self.branch_var.get()
                
                # 获取当前分支的所有提交
                commits = get_git_commits_ui(self.repo, branch_name, density, show_only_current=True)
            else:
                # 获取所有提交，以当前分支为主体
                branch_name = self.branch_var.get()
                commits = get_git_commits_ui(self.repo, branch_name, density, show_only_current=False)
                
            # 清空现有提交列表
            self.commit_tree.delete(*self.commit_tree.get_children())
            
            # 插入提交到treeview
            for commit in commits:
                commit_hash = commit["commit_hash"][:7]
                message = commit["commit_message"].strip()
                author = commit["author_name"]
                date = datetime.datetime.fromtimestamp(commit["commit_date"]).strftime('%Y-%m-%d %H:%M')
                branch_name = commit["branch"]
                
                self.commit_tree.insert("", "end", values=(
                    commit_hash,
                    message,
                    author,
                    date,
                    branch_name
                ))
        except Exception as e:
            messagebox.showerror("错误", f"获取提交失败:\n{str(e)}")
        
    def get_all_commits_cmd_preview(self):
        """生成获取所有提交的命令行预览"""
        if not self.repo:
            messagebox.showwarning("警告", "请先选择有效的Git仓库")
            return
            
        # 生成命令行预览
        repo_path = self.repo_entry.get()
        if repo_path:
            cmd = f"python main.py --repo {repo_path}"
            if self.branch_var.get():
                cmd += f" --branch {self.branch_var.get()}"
            self.cmd_text.delete(1.0, tk.END)
            self.cmd_text.insert(tk.END, cmd)
        
    def get_all_commit_after_cmd_preview(self):
        """生成获取指定提交后所有提交的命令行预览"""
        if not self.repo:
            messagebox.showwarning("警告", "请先选择有效的Git仓库")
            return
            
        if not self.branch_var.get():
            messagebox.showwarning("警告", "请先选择分支")
            return
            
        commit_hash = self.commit1_entry.get()
        if not commit_hash:
            messagebox.showwarning("警告", "请在提交1输入框中输入提交哈希")
            return
            
        # 生成命令行预览
        repo_path = self.repo_entry.get()
        if repo_path:
            cmd = f"python main.py --repo {repo_path} --branch {self.branch_var.get()} --commit_hash {commit_hash}"
            self.cmd_text.delete(1.0, tk.END)
            self.cmd_text.insert(tk.END, cmd)
        
    def get_compare_commits_cmd_preview(self):
        """生成比较两个提交的命令行预览"""
        if not self.repo:
            messagebox.showwarning("警告", "请先选择有效的Git仓库")
            return
            
        hash1 = self.commit1_entry.get()
        hash2 = self.commit2_entry.get()
        if not hash1 or not hash2:
            messagebox.showwarning("警告", "请在提交1和提交2输入框中输入提交哈希")
            return
            
        # 生成命令行预览
        repo_path = self.repo_entry.get()
        if repo_path:
            cmd = f"python main.py --repo {repo_path} --diff {hash1} {hash2}"
            self.cmd_text.delete(1.0, tk.END)
            self.cmd_text.insert(tk.END, cmd)
        
    def get_compare_commits_analyze_cmd_preview(self):
        """生成比较并分析两个提交的命令行预览"""
        if not self.repo:
            messagebox.showwarning("警告", "请先选择有效的Git仓库")
            return
            
        hash1 = self.commit1_entry.get()
        hash2 = self.commit2_entry.get()
        if not hash1 or not hash2:
            messagebox.showwarning("警告", "请在提交1和提交2输入框中输入提交哈希")
            return
            
        # 生成命令行预览
        repo_path = self.repo_entry.get()
        if repo_path:
            cmd = f"python main.py --repo {repo_path} --diff {hash1} {hash2} --analyze"
            self.cmd_text.delete(1.0, tk.END)
            self.cmd_text.insert(tk.END, cmd)
        
    def on_tree_select(self, event):
        """处理Treeview选择事件，设置拖拽数据"""
        selected = self.commit_tree.selection()
        if selected:
            self.drag_data = self.commit_tree.item(selected[0])['values'][0]
        else:
            self.drag_data = None

    def on_drop(self, event, entry):
        """处理拖放事件，将提交哈希填入输入框"""
        if self.drag_data:
            entry.delete(0, tk.END)
            entry.insert(0, self.drag_data)

    def get_analyze_commits_diff_cmd_preview(self):
        """生成分析两个提交差异的命令行预览"""
        if not self.repo:
            messagebox.showwarning("警告", "请先选择有效的Git仓库")
            return
            
        hash1 = self.commit1_entry.get()
        hash2 = self.commit2_entry.get()
        if not hash1 or not hash2:
            messagebox.showwarning("警告", "请在提交1和提交2输入框中输入提交哈希")
            return
            
        # 生成命令行预览
        cmd = f"python main.py --analyze {hash1} {hash2}"
        self.cmd_text.delete(1.0, tk.END)
        self.cmd_text.insert(tk.END, cmd)
        
        # 显示提示框
        messagebox.showinfo("提示", f"请确保提交1 {hash1}, 提交2 {hash2} 的比较结果已经保存在数据库中。该操作仅仅执行分析处理。")

    def reset_db_cmd(self):
        # 生成命令行预览
        cmd = "python main.py --reset-db"
        self.cmd_text.delete(1.0, tk.END)
        self.cmd_text.insert(tk.END, cmd)
        
        # 显示确认对话框
        confirm = messagebox.askyesno("确认", "确定要重置数据库吗？此操作将删除所有分析数据！")
        if confirm:
            self.execute_command()

    def execute_command(self):
        """执行命令行预览中的命令"""
        if not self.repo:
            messagebox.showwarning("警告", "请先选择有效的Git仓库")
            return
            
        # 获取命令行内容
        cmd = self.cmd_text.get(1.0, tk.END).strip()
        if not cmd:
            messagebox.showwarning("警告", "没有可执行的命令")
            return
            
        try:
            # 在仓库目录中执行命令
            repo_path = self.repo_entry.get()
            if not repo_path:
                raise ValueError("未选择仓库路径")
                
            # 切换到仓库目录并执行命令
            old_dir = os.getcwd()
            os.chdir(repo_path)
            
            # 执行命令并捕获输出
            process = os.popen(cmd)
            output = process.read()
            process.close()
            
            # 恢复原目录
            os.chdir(old_dir)
            
            # 在输出窗口显示执行结果
            self.output_text.delete(1.0, tk.END)
            self.output_text.insert(tk.END, output)
            
        except Exception as e:
            messagebox.showerror("错误", f"命令执行失败:\n{str(e)}")

def main():
    root = tk.Tk()
    root.title("Git 操作")
    root.geometry("800x800")
    
    git_tab = GitTab(root)
    git_tab.pack(fill=tk.BOTH, expand=True)
    
    root.mainloop()

if __name__ == "__main__":
    main()
