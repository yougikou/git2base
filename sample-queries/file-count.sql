SELECT
    file_type,
    COUNT(*) AS file_count,
    SUM(line_count1) AS line_count1,
    SUM(line_count2) AS line_count2,
    SUM(char_length1) AS char_length1,
    SUM(char_length2) AS char_length2
FROM git_diff_files
GROUP BY
    file_type;

SELECT
    file_type,
    COUNT(*) AS file_count
FROM git_files
GROUP BY
    file_type;