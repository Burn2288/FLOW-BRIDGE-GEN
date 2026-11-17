"""Illustrative isolated state machine; not production authorization or PostgreSQL."""
import threading


class Denied(Exception):
    pass


class VersionConflict(Exception):
    pass


class CentralModel:
    def __init__(self):
        self.lock = threading.Lock()
        self.version = 1
        self.allowed = {101}
        self.available = True
        self.receipts = {}
        self.jobs = []
        self.ledger = []

    def authorize(self, subject, action):
        with self.lock:
            return self._check(subject, action)

    def _check(self, subject, action):
        if not self.available or subject not in self.allowed:
            raise Denied()
        return self.version, action

    def confirm(self, subject, enter=None, proceed=None):
        with self.lock:
            decision = self._check(subject, 'confirm')
            if enter is not None:
                enter.set()
                if not proceed.wait(5):
                    raise TimeoutError('model test barrier')
            self.jobs.append((subject, decision[0]))
            self.ledger.append(('reserve', subject))
            return decision

    def update(self, expected, members, key):
        with self.lock:
            payload = frozenset(members)
            if not self.available:
                raise Denied()
            if key in self.receipts:
                old_payload, old_version = self.receipts[key]
                if old_payload != payload:
                    raise VersionConflict()
                return old_version
            if expected != self.version:
                raise VersionConflict()
            self.version += 1
            self.allowed = set(payload)
            self.receipts[key] = (payload, self.version)
            return self.version


class RolloutModel:
    def __init__(self, instances):
        self.instances = dict.fromkeys(instances, 1)
        self.fenced = True
        self.version = 1

    def begin(self):
        self.fenced = True

    def acknowledge(self, instance, version):
        if instance not in self.instances or version != self.version + 1:
            raise ValueError('unexpected rollout acknowledgement')
        self.instances[instance] = version

    def commit(self):
        if not self.fenced or any(v != self.version + 1 for v in self.instances.values()):
            raise Denied()
        self.version += 1
        self.fenced = False
