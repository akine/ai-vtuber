from dataclasses import dataclass

import feedparser


@dataclass
class Topic:
    title: str
    summary: str = ""
    source: str = ""
    url: str = ""
    category: str = ""


class GoogleNewsFetcher:
    BASE_URL = "https://news.google.com/rss/headlines/section/topic/{category}?hl=ja&gl=JP&ceid=JP:ja"

    CATEGORIES = {
        "technology": "TECHNOLOGY",
        "entertainment": "ENTERTAINMENT",
        "sports": "SPORTS",
        "science": "SCIENCE",
        "business": "BUSINESS",
    }

    def fetch(self, category: str = "technology", limit: int = 5) -> list[Topic]:
        cat_code = self.CATEGORIES.get(category, "TECHNOLOGY")
        url = self.BASE_URL.format(category=cat_code)

        try:
            feed = feedparser.parse(url)
            topics = []

            for entry in feed.entries[:limit]:
                topics.append(Topic(
                    title=entry.title,
                    summary=entry.get("summary", ""),
                    source="Google News",
                    url=entry.link,
                    category=category,
                ))

            return topics
        except Exception as e:
            print(f"Google News fetch error: {e}")
            return []
