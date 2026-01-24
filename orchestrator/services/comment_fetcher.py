import asyncio
import time
from typing import AsyncIterator, Protocol

from models.comment import Comment


class ChatFetcher(Protocol):
    """チャット取得の共通インターフェース"""
    async def connect(self) -> bool: ...
    async def disconnect(self) -> None: ...
    async def fetch(self) -> AsyncIterator[Comment]: ...
    def is_connected(self) -> bool: ...


class YouTubeChatFetcher:
    """YouTube Live Chatを取得（pytchat使用）"""

    def __init__(self, video_id: str):
        self.video_id = video_id
        self.chat = None
        self._connected = False
        self._retry_count = 0
        self._max_retries = 5
        self._retry_delay = 5  # seconds

    async def connect(self) -> bool:
        """YouTube Liveチャットに接続"""
        try:
            import pytchat
            self.chat = pytchat.create(video_id=self.video_id)
            self._connected = True
            self._retry_count = 0
            print(f"YouTube Chat connected: {self.video_id}")
            return True
        except Exception as e:
            print(f"YouTube Chat connection failed: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """接続を切断"""
        if self.chat:
            try:
                self.chat.terminate()
            except Exception:
                pass
        self._connected = False
        print("YouTube Chat disconnected")

    def is_connected(self) -> bool:
        """接続状態を確認"""
        if not self.chat:
            return False
        try:
            return self.chat.is_alive()
        except Exception:
            return False

    async def fetch(self) -> AsyncIterator[Comment]:
        """コメントを取得（自動再接続付き）"""
        while True:
            try:
                if not self.is_connected():
                    if self._retry_count >= self._max_retries:
                        print(f"Max retries ({self._max_retries}) reached. Stopping.")
                        break

                    self._retry_count += 1
                    print(f"Reconnecting... (attempt {self._retry_count}/{self._max_retries})")
                    await asyncio.sleep(self._retry_delay)

                    if not await self.connect():
                        continue

                # コメント取得
                for c in self.chat.get().sync_items():
                    self._retry_count = 0  # 成功したらリセット
                    yield Comment(
                        id=c.id,
                        author=c.author.name,
                        message=c.message,
                        timestamp=c.datetime,
                        platform="youtube",
                        is_superchat=c.amountValue > 0 if hasattr(c, 'amountValue') else False,
                        superchat_amount=c.amountValue or 0.0 if hasattr(c, 'amountValue') else 0.0,
                        is_member=(
                            getattr(c.author, 'isChatModerator', False) or
                            getattr(c.author, 'isChatSponsor', False)
                        ),
                    )

                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"YouTube Chat error: {e}")
                self._connected = False
                await asyncio.sleep(self._retry_delay)


class TwitchChatFetcher:
    """Twitch Chatを取得（TwitchIO使用）- スケルトン実装"""

    def __init__(self, channel: str, token: str):
        self.channel = channel
        self.token = token
        self._connected = False
        self._bot = None
        self._comment_queue: asyncio.Queue[Comment] = asyncio.Queue()

    async def connect(self) -> bool:
        """Twitchチャットに接続"""
        try:
            from twitchio.ext import commands

            class TwitchBot(commands.Bot):
                def __init__(bot_self, token: str, channel: str, queue: asyncio.Queue):
                    super().__init__(token=token, prefix="!", initial_channels=[channel])
                    bot_self.queue = queue

                async def event_message(bot_self, message):
                    if message.echo:
                        return
                    await bot_self.queue.put(Comment(
                        id=str(message.id) if message.id else str(time.time()),
                        author=message.author.name if message.author else "unknown",
                        message=message.content,
                        timestamp=str(time.time()),
                        platform="twitch",
                        is_superchat=False,  # Twitch bits handling would go here
                        superchat_amount=0.0,
                        is_member=message.author.is_subscriber if message.author else False,
                    ))

            self._bot = TwitchBot(self.token, self.channel, self._comment_queue)
            # Start bot in background
            asyncio.create_task(self._bot.start())
            self._connected = True
            print(f"Twitch Chat connected: {self.channel}")
            return True

        except Exception as e:
            print(f"Twitch Chat connection failed: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """接続を切断"""
        if self._bot:
            try:
                await self._bot.close()
            except Exception:
                pass
        self._connected = False
        print("Twitch Chat disconnected")

    def is_connected(self) -> bool:
        return self._connected

    async def fetch(self) -> AsyncIterator[Comment]:
        """コメントを取得"""
        while self._connected:
            try:
                comment = await asyncio.wait_for(
                    self._comment_queue.get(),
                    timeout=1.0
                )
                yield comment
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Twitch Chat error: {e}")
                await asyncio.sleep(1)


class MockChatFetcher:
    """テスト用のモックチャット取得"""

    def __init__(self, interval: float = 5.0):
        self.interval = interval
        self._connected = False
        self._comment_id = 0
        self._test_comments = [
            ("テストユーザー1", "こんにちは！初見です！"),
            ("テストユーザー2", "ミコトちゃんかわいい！"),
            ("テストユーザー3", "今日は何の話するの？"),
            ("テストユーザー4", "仕事終わったー疲れた..."),
            ("スパチャマン", "応援してます！"),  # スパチャ扱い
            ("テストユーザー5", "好きな食べ物は？"),
            ("メンバーさん", "メンバーになりました！"),
            ("テストユーザー6", "wwwwww"),
            ("テストユーザー7", "質問いいですか？"),
            ("テストユーザー8", "こんばんは！"),
        ]

    async def connect(self) -> bool:
        self._connected = True
        print("Mock Chat connected (test mode)")
        return True

    async def disconnect(self) -> None:
        self._connected = False
        print("Mock Chat disconnected")

    def is_connected(self) -> bool:
        return self._connected

    async def fetch(self) -> AsyncIterator[Comment]:
        """定期的にテストコメントを生成"""
        while self._connected:
            await asyncio.sleep(self.interval)

            if not self._connected:
                break

            idx = self._comment_id % len(self._test_comments)
            author, message = self._test_comments[idx]
            self._comment_id += 1

            is_superchat = "スパチャ" in author
            is_member = "メンバー" in author

            yield Comment(
                id=f"mock_{self._comment_id}",
                author=author,
                message=message,
                timestamp=str(time.time()),
                platform="mock",
                is_superchat=is_superchat,
                superchat_amount=500.0 if is_superchat else 0.0,
                is_member=is_member,
            )
