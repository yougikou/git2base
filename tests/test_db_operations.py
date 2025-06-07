import unittest
import importlib
from unittest.mock import patch

SQLALCHEMY_AVAILABLE = importlib.util.find_spec('sqlalchemy') is not None

if SQLALCHEMY_AVAILABLE:
    from db.connection import initialize_db, close_db
    import db.operations as ops


@unittest.skipUnless(SQLALCHEMY_AVAILABLE, "SQLAlchemy not installed")
class TestDBOperations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config_patch = patch(
            'db.connection.load_db_config',
            return_value={
                'type': 'sqlite',
                'postgresql': {},
                'sqlite': {'database': ':memory:'}
            }
        )
        cls.analyzer_patch = patch('git.config.load_analyzer_config', return_value=[])
        cls.config_patch.start()
        cls.analyzer_patch.start()
        initialize_db()
        ops.reset_database()

    @classmethod
    def tearDownClass(cls):
        close_db()
        cls.analyzer_patch.stop()
        cls.config_patch.stop()

    def test_commit_operations(self):
        commit_data = {
            'commit_hash': 'hash1',
            'branch': 'main',
            'commit_date': 1,
            'commit_message': 'msg',
            'author_name': 'name',
            'author_email': 'name@example.com'
        }
        cid = ops.insert_commit(commit_data)
        self.assertIsInstance(cid, int)
        self.assertTrue(cid > 0)
        self.assertEqual(ops.get_commit_id('hash1'), cid)
        self.assertTrue(ops.commit_exists_in_db('hash1'))
        self.assertEqual(ops.get_latest_commit_hash_from_db('main'), 'hash1')

    def test_diff_and_analysis(self):
        c1 = ops.insert_commit({
            'commit_hash': 'hashA',
            'branch': 'dev',
            'commit_date': 2,
            'commit_message': 'msgA',
            'author_name': 'a',
            'author_email': 'a@example.com'
        })
        c2 = ops.insert_commit({
            'commit_hash': 'hashB',
            'branch': 'dev',
            'commit_date': 3,
            'commit_message': 'msgB',
            'author_name': 'b',
            'author_email': 'b@example.com'
        })
        diff_id = ops.insert_diff_file({
            'commit_1_id': c1,
            'commit_2_id': c2,
            'file_path': 'file.txt',
            'file_type': 'text',
            'change_type': 'M',
            'line_count1': 1,
            'char_length1': 10,
            'blob_hash1': '1',
            'content_snapshot1': 'foo',
            'line_count2': 2,
            'char_length2': 20,
            'blob_hash2': '2',
            'content_snapshot2': 'bar',
            'tech_stack': 'text'
        })
        ops.remove_diff_file_snapshot(diff_id)
        diffs = ops.get_diff_data('hashA', 'hashB')
        self.assertEqual(len(diffs), 1)
        self.assertIsNone(diffs[0].content_snapshot1)
        self.assertIsNone(diffs[0].content_snapshot2)
        ok = ops.save_analysis_result('sample', diff_id, c1, c2, 1, {'a': 1}, 2, {'b': 2})
        self.assertTrue(ok)
        self.assertTrue(ops.analysis_exists('sample', diff_id))


if __name__ == '__main__':
    unittest.main()
