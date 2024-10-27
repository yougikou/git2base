SELECT * FROM git_commits where branch <> 'main';

SELECT 
  gc.*,
  gf.*
FROM git_files gf 
join git_commits gc
ON gc.ID = gf.commit_hash_id
WHERE
gf.file_path in ('crates/sqlez', 'crates/live_kit_server/protocol')
ORDER BY
gc.commit_date

SELECT DISTINCT file_type FROM git_files;

SELECT
    file_type,
    COUNT(*) AS file_count
FROM git_files
GROUP BY
    file_type
ORDER BY file_type;


SELECT
    file_type,
    change_type,
    COUNT(*) AS file_count
FROM git_diff_files
GROUP BY
    file_type,
    change_type
ORDER BY file_type, 
      change_type;
