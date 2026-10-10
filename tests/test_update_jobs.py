"""Run: python -m unittest discover -s tests -v"""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).parents[1] / 'scripts' / 'update_jobs.py'
spec = importlib.util.spec_from_file_location('updater', path)
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)


class TestUpdateJobs(unittest.TestCase):
    def test_reject_irrelevant_content(self):
        self.assertIsNone(u.candidate_from_result({'title':'采购面试经验总结','link':'https://example.com/post/1','snippet':'2028年实习'}, '天津'))
        self.assertIsNone(u.candidate_from_result({'title':'2027届采购岗位正式校招','link':'https://example.com/job','snippet':'北京 2027'}, '北京'))

    def test_data_never_assumes_location_or_graduation(self):
        obj = u.candidate_from_result({'title':'供应链分析实习生','link':'https://example.com/job/?utm_source=abc','snippet':'招募实习生'}, '天津')
        self.assertEqual(obj['city'], '地点待确认')
        self.assertEqual(obj['graduation_requirement'], '未明确（待核实）')
        self.assertEqual(obj['availability'], '待核验')
        self.assertNotIn('utm_', obj['url'])

    def test_weekly_update_collects_new_and_preserves_history(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp) / 'jobs.json'
            report = Path(temp) / 'report.md'
            data.write_text(json.dumps({'jobs':[]}), encoding='utf-8')
            results = [{'title':'天津供应链管理实习生-甲公司','link':'https://example.com/jobs/tj-1','snippet':'天津，实习生，2028届，每周5天'}]
            with patch.object(u, 'DATA', data), patch.object(u, 'REPORT', report), patch.dict(os.environ, {'SERPER_API_KEY':'test-key'}), patch.object(u, 'search', return_value=results), patch.object(u.time, 'sleep', return_value=None):
                self.assertEqual(u.run(), 0)
                out = json.loads(data.read_text(encoding='utf-8'))
                self.assertEqual(out['collection_status'], 'success')
                self.assertEqual(len(out['jobs']), 1)
                self.assertEqual(out['jobs'][0]['first_seen'], u.TODAY)
                self.assertIn('检索', report.read_text(encoding='utf-8'))
                self.assertEqual(u.run(), 0)
                self.assertEqual(len(json.loads(data.read_text(encoding='utf-8'))['jobs']), 1)

    def test_missing_key_keeps_existing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp) / 'jobs.json'
            data.write_text('{"jobs": [{"id":"a"}]}', encoding='utf-8')
            with patch.object(u, 'DATA', data), patch.dict(os.environ, {'SERPER_API_KEY':''}):
                self.assertEqual(u.run(), 0)
            self.assertIn('"a"', data.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
