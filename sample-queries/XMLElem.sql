SELECT 
  df.file_path,
  df.file_type,
  df.change_type,
  -- df.commit_hash1_id,
  -- df.commit_hash2_id,
  df.line_count1 || ' -> ' || df.line_count2 line_count,
  df.char_length1 || ' -> ' || df.char_length2 char_length,
  rst1.count || ' -> ' || rst2.count rst_count,
  df.blob_hash1,
  df.blob_hash2,
  rst1.content rst_content1,
  rst2.content rst_content2
FROM git_diff_files df
LEFT JOIN javaclasscount_results rst1
ON df.id = rst1.diff_file_id 
AND df.commit_hash1_id = rst1.commit_hash_id
LEFT JOIN javaclasscount_results rst2
ON df.id = rst2.diff_file_id 
AND df.commit_hash2_id = rst2.commit_hash_id
WHERE tech_stack = 'XML'