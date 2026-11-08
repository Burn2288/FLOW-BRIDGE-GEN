"""Process-local Telegram admin sessions and per-account login throttling."""

from hashlib import sha256
from hmac import compare_digest
from time import monotonic

SESSION_SECONDS = 8 * 60 * 60
PROMPT_SECONDS = 5 * 60
ATTEMPT_LIMIT = 5
ATTEMPT_WINDOW = 15 * 60
PASSWORD_PROMPT = 'Ответьте на это сообщение паролем Admin Edition. Для отмены отправьте /admin_logout.'


def digest(password):
    return sha256(password.encode('utf-8')).digest()


class AdminAccess:
    def __init__(self):
        self.sessions = {}
        self.prompts = {}
        self.failures = {}

    def active(self, chat, password):
        session = self.sessions.get(chat)
        if password and session and monotonic()<session[0] and compare_digest(session[1],digest(password)):
            return True
        self.sessions.pop(chat,None)
        return False

    def locked(self, chat):
        failure = self.failures.get(chat)
        if failure and monotonic()<failure[1]:
            return failure[0]>=ATTEMPT_LIMIT
        self.failures.pop(chat,None)
        return False

    def challenge(self, chat, message_id):
        self.prompts[chat]=(message_id,monotonic()+PROMPT_SECONDS)

    def verify(self, chat, password, candidate, reply_id):
        prompt = self.prompts.get(chat)
        if not password or not prompt or monotonic()>=prompt[1]:
            self.prompts.pop(chat,None)
            return 'expired'
        if reply_id is not None and reply_id!=prompt[0]:
            return 'expired'
        if self.locked(chat):
            return 'locked'
        expected = digest(password)
        if not compare_digest(expected,digest(candidate)):
            failures,until = self.failures.get(chat,(0,monotonic()+ATTEMPT_WINDOW))
            self.failures[chat]=(failures+1,until)
            return 'locked' if failures+1>=ATTEMPT_LIMIT else 'incorrect'
        self.prompts.pop(chat,None)
        self.failures.pop(chat,None)
        self.sessions[chat]=(monotonic()+SESSION_SECONDS,expected)
        return 'ok'

    def logout(self, chat):
        self.sessions.pop(chat,None)
        self.prompts.pop(chat,None)
