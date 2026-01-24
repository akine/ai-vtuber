import time

from models.comment import Comment


class PriorityScorer:
    """コメントの応答優先度を計算"""

    def __init__(self, character_name: str = "ミコト"):
        self.character_name = character_name
        self.recent_authors: dict[str, float] = {}

    def score(self, comment: Comment) -> int:
        score = 50  # ベーススコア

        # スーパーチャット/投げ銭（最優先）
        if comment.is_superchat:
            score += min(int(comment.superchat_amount * 10), 200)

        # メンバー/サブスクライバー
        if comment.is_member:
            score += 30

        # 質問（?を含む）
        if "?" in comment.message or "？" in comment.message:
            score += 25

        # 呼びかけ（キャラ名を含む）
        if self.character_name in comment.message:
            score += 20

        # あいさつ
        greetings = ["こんにちは", "こんばんは", "おはよう", "初見"]
        if any(g in comment.message for g in greetings):
            score += 15

        # 短すぎるコメントは減点
        if len(comment.message) < 3:
            score -= 30

        # 連続投稿者は減点（荒らし対策）
        if self._is_spam_user(comment.author):
            score -= 50

        return max(0, min(score, 300))

    def _is_spam_user(self, author: str) -> bool:
        now = time.time()

        # 過去の投稿をクリーンアップ（60秒以上前）
        self.recent_authors = {
            a: t for a, t in self.recent_authors.items()
            if now - t < 60
        }

        # 同じ人が10秒以内に連続投稿
        if author in self.recent_authors:
            if now - self.recent_authors[author] < 10:
                return True

        self.recent_authors[author] = now
        return False
