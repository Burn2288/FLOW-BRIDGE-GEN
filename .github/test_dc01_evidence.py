import unittest
import check_dc01_evidence as check


class Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = check.REPORT.read_text(encoding='utf-8')

    def test_valid(self):
        check.validate(self.report)

    def test_duplicate(self):
        with self.assertRaises(ValueError):
            check.validate(self.report.replace('| C-031 |', '| C-030 |'))

    def test_false_implementation(self):
        with self.assertRaises(ValueError):
            check.validate(self.report.replace('PARTIAL:', 'IMPLEMENTED:', 1))

    def test_mutable_link(self):
        with self.assertRaises(ValueError):
            check.validate(self.report.replace(check.SHA + '/src/', 'main/src/', 1))


if __name__ == '__main__':
    unittest.main()
