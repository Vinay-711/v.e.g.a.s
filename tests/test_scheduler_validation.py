import importlib.util
import math
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("scheduler_under_test", Path(__file__).parents[1] / "vegas/scheduler/engine.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class SchedulerValidationTests(unittest.TestCase):
    def test_invalid_intervals_do_not_register(self):
        for value in (0, -1, math.nan, math.inf, -math.inf, True, "60", None):
            with self.subTest(value=value):
                scheduler = module.VegasScheduler()
                with self.assertRaises(ValueError):
                    scheduler.register_job("bad", value, lambda: None)
                self.assertEqual(scheduler.jobs, {})
    def test_invalid_iteration_limits_do_not_register(self):
        for value in (0, -1, 1.5, True, "3"):
            with self.subTest(value=value):
                scheduler = module.VegasScheduler()
                with self.assertRaises(ValueError):
                    scheduler.register_job("bad", 1, lambda: None, value)
                self.assertEqual(scheduler.jobs, {})
    def test_callback_must_be_callable(self):
        scheduler = module.VegasScheduler()
        with self.assertRaises(ValueError):
            scheduler.register_job("bad", 1, None)
        self.assertEqual(scheduler.jobs, {})
    def test_valid_registration_does_not_execute_callback(self):
        calls = []
        scheduler = module.VegasScheduler()
        for interval, limit in ((1, None), (0.5, 1), (60, 3)):
            scheduler.register_job(str(interval), interval, lambda: calls.append(1), limit)
        self.assertEqual(len(scheduler.jobs), 3)
        self.assertEqual(calls, [])
        self.assertFalse(scheduler.running)
