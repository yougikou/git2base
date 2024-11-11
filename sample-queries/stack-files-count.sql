SELECT
    tech_stack,
    COUNT(*) AS file_count
FROM git_diff_files
GROUP BY
    tech_stack;


