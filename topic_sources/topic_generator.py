import random
from typing import Optional

from .google_news import GoogleNewsFetcher, Topic
from .hatena_bookmark import HatenaBookmarkFetcher


class TopicGenerator:
    def __init__(self):
        self.google_news = GoogleNewsFetcher()
        self.hatena = HatenaBookmarkFetcher()
        self.used_topics: set[str] = set()
        self.categories = ["technology", "entertainment", "game", "anime"]
        self.category_index = 0

    async def get_random_topic(self) -> Optional[Topic]:
        """ランダムな話題を取得（重複回避）"""

        # カテゴリをローテーション
        category = self.categories[self.category_index]
        self.category_index = (self.category_index + 1) % len(self.categories)

        # 複数ソースから取得
        topics = []
        topics.extend(self.google_news.fetch(category, 5))
        topics.extend(self.hatena.fetch(category, 5))

        # 未使用の話題をフィルタ
        unused = [t for t in topics if t.title not in self.used_topics]

        if not unused:
            # 全部使用済みならリセット
            self.used_topics.clear()
            unused = topics

        if unused:
            topic = random.choice(unused)
            self.used_topics.add(topic.title)
            return topic

        return None
