import feedparser

from .google_news import Topic


class HatenaBookmarkFetcher:
    FEEDS = {
        "it": "https://b.hatena.ne.jp/hotentry/it.rss",
        "game": "https://b.hatena.ne.jp/hotentry/game.rss",
        "entertainment": "https://b.hatena.ne.jp/hotentry/entertainment.rss",
        "anime": "https://b.hatena.ne.jp/hotentry/anime.rss",
    }

    def fetch(self, category: str = "it", limit: int = 5) -> list[Topic]:
        url = self.FEEDS.get(category, self.FEEDS["it"])

        try:
            feed = feedparser.parse(url)
            return [
                Topic(
                    title=entry.title,
                    url=entry.link,
                    source="はてなブックマーク",
                    category=category,
                )
                for entry in feed.entries[:limit]
            ]
        except Exception as e:
            print(f"Hatena fetch error: {e}")
            return []
