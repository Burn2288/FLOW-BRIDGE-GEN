"""Negative checks for the offline documentation validator."""
import unittest
import check_foundation_contracts as checker


class FoundationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix, cls.owners, cls.registry = [p.read_text(encoding='utf-8') for p in
                                                 (checker.MATRIX, checker.OWNER, checker.REGISTRY)]

    def test_actual(self):
        checker.validate(self.matrix, self.owners, self.registry)

    def test_duplicate(self):
        with self.assertRaises(ValueError):
            checker.validate(self.matrix.replace('| C-031 |', '| C-030 |'), self.owners, self.registry)

    def test_claim_implemented(self):
        with self.assertRaises(ValueError):
            checker.validate(self.matrix.replace('| PARTIAL:', '| IMPLEMENTED:', 1), self.owners, self.registry)

    def test_broken_link(self):
        with self.assertRaises(ValueError):
            checker.validate(self.matrix.replace('../contracts/IDENTITY_CONSENT.md', '../contracts/missing.md', 1), self.owners, self.registry)

    def test_missing_env(self):
        with self.assertRaises(ValueError):
            checker.validate(self.matrix.replace('`MINIAPP_URL`', '`MISSING_URL`'), self.owners, self.registry)

    def test_missing_owner_gate(self):
        with self.assertRaises(ValueError):
            checker.validate(self.matrix.replace('OWNER_DECISION_REQUIRED', 'PENDING'), self.owners, self.registry)


if __name__ == '__main__':
    unittest.main()
