from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class TaskRecord:
    task: str
    result: Any
    created_at: datetime


@dataclass
class PreferenceRecord:
    key: str
    value: Any
