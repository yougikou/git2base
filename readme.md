使用python以及git的低层次库pygit2，进度显示插件tqdm，以及数据库连接插件psycopg2来实现一下功能。

功能概要：把git数据按照一定方式导入到数据库
数据库模型：
1. git_commits: id, commit_hash, branch, commit_date, commit_message, author_name, author_email
2. git_files: id, file_path, file_type, change_type, char_length, line_count, blob_hash
3. git_diff_files: commit_hash1_id, commit_hash2_id, file_path, file_type, change_type, line_count1, blob_hash1, content_snapshot1, line_count2, blob_hash2, content_snapshot2

导入功能
1. 支持数据库重置，通过--reset参数实现数据库重置
2. 初始化，把指定branch的指定commit_hash过后的git history导入到git_commits和git_files
3. 增量更新，如果没有指定commit_hash，只指定了branch，则从数据库尝试获取最新的commit_hash，然后继续获取它之后的git history导入到git_commits和git_files。数据库的commit请以一个commit为单位。
4. 获取Diff，把指定commit hash（branch），以commit_hash1为基准，获取commit_hash2先对于它的变更文件，把相应的数据导入到git_commits和git_diff_files, content_snapshot1和content_snapshot2则获取各个文件的commit_hash1和commit_hash2对应的完整snapshot。数据库的commit请以每100个文件为单位。

其他要求
- 把数据库配置放到外部配置文件，文件格式为yaml。
- 参数指定的时候，需要可以接受短hash的输入
- file_type储存文件扩展名, 从file_path中获取，对于以“.”开头的文件，譬如.gitignore之类的文件的file_type设为<dev-config>
- change_type应以git标准的A,M,D 等类型来保存

命令行
- reset database:
python main.py --reset

- extract branch commit history from start/latest commit in database
python main.py --repo /path/to/your/repo --branch <branch-name>

- extract branch commit history from specified commit(not include the commit)
python main.py --repo /path/to/your/repo --branch <branch-name> --commit_hash <hash>

- extract branch diff from two commits(of two branch)
python main.py --repo /path/to/your/repo --diff <hash1> <hash2>