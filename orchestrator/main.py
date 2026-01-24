import asyncio
import time
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, Response
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

from config import settings
from llm.client import LLMClient
from llm.prompts import CHARACTER_PROMPT, TOPIC_PROMPT
from models.comment import Comment
from services.comment_fetcher import YouTubeChatFetcher, TwitchChatFetcher, MockChatFetcher
from services.emotion_analyzer import extract_emotion, remove_emotion_tags
from services.memory_manager import MemoryManager
from services.priority_scorer import PriorityScorer
from services.safety_filter import SafetyFilter
from services.vts_controller import VTubeStudioController
from topic_sources.topic_generator import TopicGenerator

# Prometheusメトリクス
COMMENTS_TOTAL = Counter('vtuber_comments_total', 'Total comments processed', ['platform'])
TOPICS_TOTAL = Counter('vtuber_topics_total', 'Total topics generated')
RESPONSES_TOTAL = Counter('vtuber_responses_total', 'Total LLM responses generated')
FILTERED_TOTAL = Counter('vtuber_filtered_total', 'Total comments filtered', ['reason'])
SPEAKING_GAUGE = Gauge('vtuber_is_speaking', 'Whether the VTuber is currently speaking')
IDLE_TIME_GAUGE = Gauge('vtuber_idle_seconds', 'Seconds since last comment')
RESPONSE_LATENCY = Histogram('vtuber_response_latency_seconds', 'LLM response generation time',
                              buckets=[0.5, 1, 2, 5, 10, 30])
TTS_LATENCY = Histogram('vtuber_tts_latency_seconds', 'TTS generation time',
                         buckets=[0.1, 0.5, 1, 2, 5])

# グローバル状態
state = {
    "last_comment_time": time.time(),
    "comments_processed": 0,
    "topics_generated": 0,
    "is_speaking": False,
    "chat_fetcher": None,
}


def create_chat_fetcher():
    """設定に基づいてチャット取得を作成"""
    mode = settings.CHAT_MODE.lower()

    if mode == "youtube":
        if not settings.YOUTUBE_VIDEO_ID:
            print("Warning: YOUTUBE_VIDEO_ID not set, falling back to mock mode")
            return MockChatFetcher(interval=settings.MOCK_INTERVAL)
        return YouTubeChatFetcher(settings.YOUTUBE_VIDEO_ID)

    elif mode == "twitch":
        if not settings.TWITCH_TOKEN or not settings.TWITCH_CHANNEL:
            print("Warning: Twitch credentials not set, falling back to mock mode")
            return MockChatFetcher(interval=settings.MOCK_INTERVAL)
        return TwitchChatFetcher(settings.TWITCH_CHANNEL, settings.TWITCH_TOKEN)

    else:  # mock
        return MockChatFetcher(interval=settings.MOCK_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時の初期化
    state["redis"] = await redis.from_url(settings.REDIS_URL)
    state["llm"] = LLMClient(settings.VLLM_URL)
    state["scorer"] = PriorityScorer(settings.CHARACTER_NAME)
    state["safety"] = SafetyFilter()
    state["memory"] = MemoryManager()
    state["http_client"] = httpx.AsyncClient()

    # チャット取得を作成
    state["chat_fetcher"] = create_chat_fetcher()

    # 話題ジェネレータを作成
    state["topic_generator"] = TopicGenerator()

    # VTube Studio連携（オプション）
    if settings.VTS_ENABLED:
        vts = VTubeStudioController(settings.VTS_HOST, settings.VTS_PORT)
        if await vts.connect():
            state["vts"] = vts
        else:
            print("VTube Studio disabled (connection failed)")
            state["vts"] = None
    else:
        state["vts"] = None

    # バックグラウンドタスク開始
    asyncio.create_task(chat_listener())
    asyncio.create_task(comment_processor())
    asyncio.create_task(idle_topic_generator())

    print(f"AI VTuber System Started! (Chat mode: {settings.CHAT_MODE})")

    yield

    # 終了時のクリーンアップ
    if state["chat_fetcher"]:
        await state["chat_fetcher"].disconnect()
    if state.get("vts"):
        await state["vts"].disconnect()
    await state["redis"].close()
    await state["http_client"].aclose()


app = FastAPI(lifespan=lifespan)


async def chat_listener():
    """チャットを監視してRedisに投入"""
    fetcher = state["chat_fetcher"]

    if not await fetcher.connect():
        print("Failed to connect to chat. Retrying...")
        await asyncio.sleep(5)
        if not await fetcher.connect():
            print("Chat connection failed. Running without chat input.")
            return

    async for comment in fetcher.fetch():
        try:
            await state["redis"].xadd("comment_queue", {
                "id": comment.id,
                "platform": comment.platform,
                "author": comment.author,
                "message": comment.message,
                "is_superchat": str(comment.is_superchat),
                "superchat_amount": str(comment.superchat_amount),
                "is_member": str(comment.is_member),
            })
        except Exception as e:
            print(f"Error adding comment to queue: {e}")


async def comment_processor():
    """コメント処理メインループ"""

    while True:
        try:
            # 発話中はスキップ
            if state["is_speaking"]:
                await asyncio.sleep(0.1)
                continue

            # Redis からコメント取得（1秒待機）
            result = await state["redis"].xread(
                {"comment_queue": "0"},
                block=1000,
                count=1
            )

            if result:
                state["last_comment_time"] = time.time()
                stream, messages = result[0]

                for msg_id, data in messages:
                    # bytes to str 変換
                    data = {k.decode(): v.decode() for k, v in data.items()}
                    await process_comment(data)
                    await state["redis"].xdel("comment_queue", msg_id)

        except Exception as e:
            print(f"Error in comment processor: {e}")
            await asyncio.sleep(1)


async def process_comment(data: dict):
    """単一コメントを処理して応答"""

    # Comment オブジェクトに変換
    comment = Comment(
        id=data["id"],
        author=data["author"],
        message=data["message"],
        timestamp="",
        platform=data["platform"],
        is_superchat=data["is_superchat"] == "True",
        superchat_amount=float(data["superchat_amount"]),
        is_member=data["is_member"] == "True",
    )

    # 安全性チェック
    is_safe, reason = state["safety"].is_safe(comment)
    if not is_safe:
        print(f"Filtered [{reason}]: {comment.message[:30]}...")
        FILTERED_TOTAL.labels(reason=reason.split(':')[0]).inc()
        return

    # 優先度計算（ログ用）
    priority = state["scorer"].score(comment)
    print(f"[{priority}] {comment.author}: {comment.message[:50]}...")

    # メモリに追加
    state["memory"].add_user_message(comment.message, comment.author)

    # LLM で応答生成
    user_message = f"{comment.author}さん: {comment.message}"
    await generate_and_speak(user_message, CHARACTER_PROMPT)

    # メトリクス更新
    COMMENTS_TOTAL.labels(platform=comment.platform).inc()
    state["comments_processed"] += 1


async def idle_topic_generator():
    """コメントがない時の話題生成（ニュース/はてブから取得）"""
    topic_gen = state["topic_generator"]

    # フォールバック用の話題リスト
    fallback_topics = [
        "最近のテクノロジーニュース",
        "おすすめのゲーム",
        "今日の天気について",
        "好きな食べ物の話",
        "最近見たアニメについて",
    ]
    fallback_index = 0

    while True:
        await asyncio.sleep(5)

        # 発話中 or 最近コメントあり ならスキップ
        if state["is_speaking"]:
            continue

        idle_time = time.time() - state["last_comment_time"]
        IDLE_TIME_GAUGE.set(idle_time)

        if idle_time > settings.IDLE_THRESHOLD_SECONDS:
            # ニュース/はてブから話題取得を試みる
            topic = await topic_gen.get_random_topic()

            if topic:
                topic_title = topic.title
                topic_source = topic.source
                print(f"Topic from {topic_source}: {topic_title[:50]}...")
            else:
                # フォールバック
                topic_title = fallback_topics[fallback_index % len(fallback_topics)]
                fallback_index += 1
                print(f"Fallback topic: {topic_title[:50]}...")

            prompt = TOPIC_PROMPT.format(topic=topic_title)
            await generate_and_speak(f"話題: {topic_title}", prompt)
            state["topics_generated"] += 1
            TOPICS_TOTAL.inc()
            state["last_comment_time"] = time.time()  # リセット

            # 次の話題まで60秒待機
            await asyncio.sleep(60)


async def generate_and_speak(user_message: str, system_prompt: str):
    """LLMで応答生成 -> TTS -> 発話"""

    state["is_speaking"] = True
    SPEAKING_GAUGE.set(1)
    start_time = time.time()

    try:
        full_response = ""
        buffer = ""

        async for chunk in state["llm"].generate_response(
            user_message=user_message,
            system_prompt=system_prompt,
            chat_history=state["memory"].get_history(),
        ):
            full_response += chunk
            buffer += chunk

            # 文末で音声生成をトリガー
            if any(buffer.endswith(p) for p in ["。", "！", "？", "!", "?", "\n"]):
                # 感情タグ抽出
                emotion = extract_emotion(full_response)

                # 感情タグを除去
                clean_text = remove_emotion_tags(buffer)

                if clean_text:
                    # 音声生成・再生
                    await speak(clean_text, emotion)

                buffer = ""

        # 残りがあれば処理
        if buffer.strip():
            clean_text = remove_emotion_tags(buffer)
            if clean_text:
                await speak(clean_text, "neutral")

        # メモリに追加
        clean_response = remove_emotion_tags(full_response)
        if clean_response:
            state["memory"].add_assistant_message(clean_response)
            print(f"Response: {clean_response[:100]}...")

    except Exception as e:
        print(f"Error generating response: {e}")

    finally:
        state["is_speaking"] = False
        SPEAKING_GAUGE.set(0)
        RESPONSE_LATENCY.observe(time.time() - start_time)
        RESPONSES_TOTAL.inc()


async def speak(text: str, emotion: str):
    """TTS APIを呼び出して音声再生"""
    tts_start = time.time()
    try:
        # VTube Studioの表情を変更
        vts = state.get("vts")
        if vts:
            await vts.set_expression(emotion)

        response = await state["http_client"].post(
            f"{settings.TTS_URL}/synthesize",
            json={"text": text, "emotion": emotion},
            timeout=30.0
        )

        if response.status_code == 200:
            TTS_LATENCY.observe(time.time() - tts_start)
            # 音声データを再生（実際はPipeWire/PulseAudioへ出力）
            audio_data = response.content
            await play_audio(audio_data, vts)

    except Exception as e:
        print(f"TTS Error: {e}")


async def play_audio(audio_data: bytes, vts=None):
    """音声を再生（PipeWire経由でVTube Studioへ）+ リップシンク"""
    try:
        import io

        import numpy as np
        import sounddevice as sd
        import soundfile as sf

        data, samplerate = sf.read(io.BytesIO(audio_data))

        # リップシンク用：音声データをチャンクに分割して再生
        if vts and vts.is_connected():
            chunk_size = int(samplerate * 0.05)  # 50msごとに更新
            total_samples = len(data)

            for i in range(0, total_samples, chunk_size):
                chunk = data[i:i + chunk_size]

                # このチャンクの音量（RMS）を計算
                if len(chunk) > 0:
                    rms = np.sqrt(np.mean(chunk ** 2))
                    # 音量を0-1に正規化（調整可能）
                    volume = min(rms * 5, 1.0)
                    await vts.lip_sync(volume)

                # チャンクを再生
                sd.play(chunk, samplerate)
                sd.wait()

            # 再生終了後、口を閉じる
            await vts.reset_lip_sync()
        else:
            # VTSなしの場合は通常再生
            sd.play(data, samplerate)
            sd.wait()

    except Exception as e:
        print(f"Audio playback error: {e}")


# ===== API Endpoints =====


@app.get("/metrics")
async def metrics():
    """Prometheusメトリクスエンドポイント"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health_check():
    fetcher = state.get("chat_fetcher")
    return {
        "status": "healthy",
        "chat_mode": settings.CHAT_MODE,
        "chat_connected": fetcher.is_connected() if fetcher else False,
    }


@app.get("/stats")
async def get_stats():
    return {
        "comments_processed": state["comments_processed"],
        "topics_generated": state["topics_generated"],
        "is_speaking": state["is_speaking"],
        "idle_time": time.time() - state["last_comment_time"],
        "chat_mode": settings.CHAT_MODE,
    }


@app.post("/test/comment")
async def test_comment(author: str = "テストユーザー", message: str = "こんにちは！"):
    """テスト用：コメントを手動で投入"""
    await state["redis"].xadd("comment_queue", {
        "id": f"test_{time.time()}",
        "platform": "test",
        "author": author,
        "message": message,
        "is_superchat": "False",
        "superchat_amount": "0",
        "is_member": "False",
    })
    return {"status": "ok", "message": f"Comment from {author} added to queue"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
