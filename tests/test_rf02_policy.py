from itertools import product
import unittest
from unittest.mock import patch

from elevenbot.referral_reward_policy import CaptureFunding, allocate_reserve, cumulative_refund, reward_tokens
from elevenbot.referral_rewards import functional_test_database


class ReferralRewardPolicyTests(unittest.TestCase):
    def test_reward_only_uses_explicit_disposable_database_profiles(self):
        dev = {
            'RF02_FUNCTIONAL_TEST': 'YES',
            'FLOWBRIDGE_DEV_FIXTURE': 'YES',
            'DATABASE_URL': 'postgresql://postgres:isolated-test-only@127.0.0.1:5432/flowbridge_dev',
        }
        with patch.dict('os.environ', dev, clear=True):
            self.assertEqual(functional_test_database(), 'flowbridge_dev')
        for overrides in (
            {'RF02_FUNCTIONAL_TEST': 'NO'},
            {'FLOWBRIDGE_DEV_FIXTURE': ''},
            {'DATABASE_URL': dev['DATABASE_URL'].replace('127.0.0.1', 'db.example.test')},
            {'DATABASE_URL': dev['DATABASE_URL'].replace('/flowbridge_dev', '/main')},
            {'DATABASE_MIGRATION_URL': 'configured-elsewhere'},
            {'TEST_DATABASE_URL': 'different-test-profile'},
        ):
            with patch.dict('os.environ', dev | overrides, clear=True), self.subTest(overrides=overrides):
                self.assertIsNone(functional_test_database())
        with patch.dict('os.environ', {
            'RF02_FUNCTIONAL_TEST': 'YES',
            'TEST_DATABASE_URL': 'postgresql://postgres:isolated-test-only@127.0.0.1:5432/elevenbot_test',
            'DISPOSABLE_POSTGRES_PROFILE': 'compose-service',
            'DISPOSABLE_POSTGRES_CONFIRM': 'YES',
        }, clear=True):
            self.assertEqual(functional_test_database(), 'elevenbot_test')

    def test_reserve_spend_order(self):
        available = CaptureFunding(5, 7, 11, 13)
        self.assertEqual(allocate_reserve(available, 8).amounts, (5, 3, 0, 0))
        self.assertEqual(allocate_reserve(available, 17).amounts, (5, 7, 5, 0))
        self.assertEqual(allocate_reserve(available, 29).amounts, (5, 7, 11, 6))

    def test_reserve_cannot_overdraw(self):
        available = CaptureFunding(1, 2, 3, 4)
        for amount in (-1, 11):
            with self.assertRaises(ValueError):
                allocate_reserve(available, amount)

    def test_monotone_exact_and_bounded_for_all_small_captures(self):
        for amounts in product(range(5), repeat=4):
            capture = CaptureFunding(*amounts)
            previous = (0, 0, 0, 0)
            for returned in range(sum(amounts) + 1):
                allocation = cumulative_refund(capture, returned).amounts
                self.assertEqual(sum(allocation), returned)
                self.assertTrue(all(a <= b <= c for a, b, c in zip(previous, allocation, amounts)))
                previous = allocation
            self.assertEqual(previous, amounts)

    def test_ties_are_deterministic(self):
        capture = CaptureFunding(1, 1, 1, 1)
        self.assertEqual(cumulative_refund(capture, 2).amounts, (1, 1, 0, 0))

    def test_paid_only_and_cumulative_recalculation(self):
        capture = CaptureFunding(7, 11, 41, 13)
        recognized = reward_tokens(capture, 0, 500)
        self.assertEqual(recognized, 2)
        balances = [reward_tokens(capture, n, 500) for n in range(73)]
        self.assertEqual(sum(a - b for a, b in zip(balances, balances[1:])), recognized)
        self.assertEqual(balances[-1], 0)
        self.assertEqual(reward_tokens(CaptureFunding(100, 100, 0, 100), 0, 500), 0)

    def test_large_integers_and_invalid_values(self):
        amount = 2**63 - 1
        capture = CaptureFunding(0, 0, amount, 0)
        self.assertEqual(reward_tokens(capture, 0, 500), amount // 20)
        with self.assertRaises(ValueError):
            cumulative_refund(capture, amount + 1)
        with self.assertRaises(ValueError):
            reward_tokens(capture, 0, 10001)
        with self.assertRaises(ValueError):
            CaptureFunding(0, -1, 0, 0)
