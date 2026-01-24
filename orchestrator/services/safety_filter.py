import re
from pathlib import Path

from models.comment import Comment


class SafetyFilter:
    """NGワード・荒らし・危険コンテンツのフィルタリング"""

    def __init__(self, ng_words_path: str = "./config/ng_words.txt"):
        self.ng_words = self._load_ng_words(ng_words_path)

    def _load_ng_words(self, path: str) -> set[str]:
        words = set()
        if Path(path).exists():
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        words.add(line.lower())
        return words

    def is_safe(self, comment: Comment) -> tuple[bool, str]:
        text = comment.message.lower()

        # NGワードチェック
        for word in self.ng_words:
            if word in text:
                return False, f"NG_WORD: {word}"

        # URL検出（スパム対策）
        if re.search(r'https?://', text):
            return False, "URL_DETECTED"

        # 個人情報パターン
        if self._contains_pii(comment.message):
            return False, "PII_DETECTED"

        # 連続文字（荒らし）
        if self._is_spam_pattern(text):
            return False, "SPAM_PATTERN"

        return True, "OK"

    def _contains_pii(self, text: str) -> bool:
        patterns = [
            r'\d{2,4}-\d{2,4}-\d{4}',  # 電話番号
            r'\d{3}-\d{4}',             # 郵便番号
            r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+',  # メール
        ]
        return any(re.search(p, text) for p in patterns)

    def _is_spam_pattern(self, text: str) -> bool:
        # 同じ文字が10回以上連続
        if re.search(r'(.)\1{9,}', text):
            return True
        # 同じ単語が5回以上連続
        if re.search(r'(\S+)\s+\1\s+\1\s+\1\s+\1', text):
            return True
        return False
