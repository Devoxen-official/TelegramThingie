import unittest
from src.utils.logger import Logger, logger

def log_globally():
    return logger.format_info("test")

class TestUtils(unittest.TestCase):
    def test_logger_context(self):
        class TestClass:
            def get_log(self):
                return logger.format_info("test")
        
        self.assertEqual(TestClass().get_log(), "[TestClass] INFO:test")
        # When called from within TestUtils, it should be [TestUtils]
        self.assertEqual(logger.format_info("test"), "[TestUtils] INFO:test")
        # When called from a global function, it should be [App]
        self.assertEqual(log_globally(), "[App] INFO:test")