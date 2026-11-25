from itertools import product
import unittest

from elevenbot.referral_reward_policy import CaptureFunding, cumulative_refund, reward_tokens


class ReferralRewardPolicyTests(unittest.TestCase):
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
