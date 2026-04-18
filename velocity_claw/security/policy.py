from dataclasses import dataclass
from typing import List


@dataclass
class SecurityAction:
    description: str
    command: str
    risk_level: int


class SecurityManager:
    dangerous_keywords = ["rm -rf", "format", "shutdown", "reboot", "git reset", "git rebase", "dd ", "mkfs", ":(){" ]
    confirm_threshold = 5

    def __init__(self, safe_mode: bool = True, dev_mode: bool = False, trusted_mode: bool = False):
        self.safe_mode = safe_mode
        self.dev_mode = dev_mode
        self.trusted_mode = trusted_mode

    def is_dangerous_command(self, command: str) -> bool:
        normalized = command.lower()
        return any(key in normalized for key in self.dangerous_keywords)

    def requires_confirmation(self, command: str) -> bool:
        if self.trusted_mode:
            return False
        if self.safe_mode:
            return self.is_dangerous_command(command)
        return self.is_dangerous_command(command) and not self.dev_mode

    def can_execute(self, command: str) -> bool:
        if self.requires_confirmation(command):
            return False
        return True

    def review_action(self, command: str) -> SecurityAction:
        risk = 1
        if self.is_dangerous_command(command):
            risk = self.confirm_threshold
        return SecurityAction(description="Review command for potential danger", command=command, risk_level=risk)
