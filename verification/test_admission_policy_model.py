"""Model-only race examples; no claims about application or database behavior."""
import concurrent.futures
import threading
import unittest
from admission_policy_model import CentralModel, Denied, RolloutModel, VersionConflict


class ModelTests(unittest.TestCase):
    def test_revocation_precedes_confirm(self):
        policy = CentralModel()
        policy.update(1, set(), 'revoke')
        with self.assertRaises(Denied):
            policy.confirm(101)
        self.assertEqual((policy.jobs, policy.ledger), ([], []))

    def test_authorized_transaction_finishes_before_waiting_revoke(self):
        policy = CentralModel()
        entered, proceed, revoke_started = threading.Event(), threading.Event(), threading.Event()
        def revoke():
            revoke_started.set()
            return policy.update(1, set(), 'revoke')
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            authorized = executor.submit(policy.confirm, 101, entered, proceed)
            self.assertTrue(entered.wait(5))
            revoked = executor.submit(revoke)
            self.assertTrue(revoke_started.wait(5))
            proceed.set()
            self.assertEqual(authorized.result(timeout=5), (1, 'confirm'))
            self.assertEqual(revoked.result(timeout=5), 2)
        with self.assertRaises(Denied):
            policy.confirm(101)
        self.assertEqual(policy.ledger, [('reserve', 101)])

    def test_old_quote_session_and_callback_rechecked(self):
        policy = CentralModel()
        for action in ('quote', 'session', 'callback'):
            self.assertEqual(policy.authorize(101, action)[0], 1)
        policy.update(1, set(), 'revoke')
        for action in ('confirm', 'session', 'callback'):
            with self.assertRaises(Denied):
                policy.authorize(101, action)

    def test_unavailable_policy_fails_closed(self):
        policy = CentralModel()
        policy.available = False
        with self.assertRaises(Denied):
            policy.confirm(101)
        with self.assertRaises(Denied):
            policy.update(1, set(), 'revoke')

    def test_idempotency_and_compare_and_swap(self):
        policy = CentralModel()
        self.assertEqual(policy.update(1, set(), 'same'), 2)
        self.assertEqual(policy.update(1, set(), 'same'), 2)
        with self.assertRaises(VersionConflict):
            policy.update(1, {101}, 'same')
        with self.assertRaises(VersionConflict):
            policy.update(1, {101}, 'other')

    def test_two_concurrent_updates_do_not_both_commit(self):
        policy = CentralModel()
        barrier = threading.Barrier(2)
        def update(key):
            barrier.wait(timeout=5)
            try:
                return policy.update(1, {102}, key)
            except VersionConflict:
                return 'conflict'
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(update, ('a', 'b')))
        self.assertCountEqual(outcomes, [2, 'conflict'])

    def test_rollout_cannot_open_with_stale_or_missing_instance(self):
        rollout = RolloutModel(('telegram_a', 'telegram_b', 'miniapp'))
        rollout.begin()
        rollout.acknowledge('telegram_a', 2)
        rollout.acknowledge('miniapp', 2)
        with self.assertRaises(Denied):
            rollout.commit()
        self.assertTrue(rollout.fenced)
        rollout.acknowledge('telegram_b', 2)
        rollout.commit()
        self.assertFalse(rollout.fenced)
        self.assertEqual(rollout.version, 2)

    def test_rollout_wrong_version_cannot_acknowledge(self):
        rollout = RolloutModel(('a',))
        with self.assertRaises(ValueError):
            rollout.acknowledge('a', 3)
        with self.assertRaises(ValueError):
            rollout.acknowledge('unknown', 2)


if __name__ == '__main__':
    unittest.main()
