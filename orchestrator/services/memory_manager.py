from collections import deque
from dataclasses import dataclass
from typing import Optional


@dataclass
class MemoryEntry:
    role: str
    content: str
    author: Optional[str] = None


class MemoryManager:
    """会話履歴を管理するシンプルなメモリマネージャー"""

    def __init__(self, max_history: int = 20):
        self.history: deque[MemoryEntry] = deque(maxlen=max_history)

    def add_user_message(self, content: str, author: str):
        self.history.append(MemoryEntry(
            role="user",
            content=f"{author}さん: {content}",
            author=author
        ))

    def add_assistant_message(self, content: str):
        self.history.append(MemoryEntry(
            role="assistant",
            content=content
        ))

    def get_history(self, limit: int = 10) -> list[dict]:
        """OpenAI形式の会話履歴を返す"""
        entries = list(self.history)[-limit:]
        return [
            {"role": e.role, "content": e.content}
            for e in entries
        ]

    def clear(self):
        self.history.clear()
