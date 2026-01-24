import asyncio
import re
import time
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as redis
from fastapi import FastAPI

from config import settings
from llm.client import LLMClient
from llm.prompts import CHARACTER_PROMPT, TOPIC_PROMPT
from models.comment import Comment
from services.comment_fetcher import YouTubeChatFetcher
from services.emotion_analyzer import extract_emotion, remove_emotion_tags
from services.memory_manager import MemoryManager
from services.priority_scorer import PriorityScorer
from services.safety_filter import SafetyFilter

# グローバル状態
state = {
    "last_comment_time": time.time(),
    "comments_processed": 0,
    "topics_generated": 0,
    "is_speaking": False,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時の初期化
    state["redis"] = await redis.from_url(settings.REDIS_URL)
    state["llm"] = LLMClient(settings.VLLM_URL)
    state["scorer"] = PriorityScorer(settings.CHARACTER_NAME)
    state["safety"] = SafetyFilter()
    state["memory"] = MemoryManager()
    state["http_client"] = httpx.AsyncClient()

    # バックグラウンドタスク開始
    if settings.YOUTUBE_VIDEO_ID:
        asyncio.create_task(youtube_chat_listener())
    asyncio.create_task(comment_processor())
    asyncio.create_task(idle_topic_generator())

    print("AI VTuber System Started!")

    yield

    # 終了時のクリーンアップ
    await state["redis"].close()
    await state["http_client"].aclose()


app = FastAPI(lifespan=lifespan)


async def youtube_chat_listener():
    """YouTubeチャットを監視してRedisに投入"""
    fetcher = YouTubeChatFetcher(settings.YOUTUBE_VIDEO_ID)
    await fetcher.connect()

    async for comment in fetcher.fetch():
        await state["redis"].xadd("comment_queue", {
            "id": comment.id,
            "platform": comment.platform,
            "author": comment.author,
            "message": comment.message,
            "is_superchat": str(comment.is_superchat),
            "superchat_amount": str(comment.superchat_amount),
            "is_member": str(comment.is_member),
        })


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
        return

    # 優先度計算（ログ用）
    priority = state["scorer"].score(comment)
    print(f"[{priority}] {comment.author}: {comment.message[:50]}...")

    # メモリに追加
    state["memory"].add_user_message(comment.message, comment.author)

    # LLM で応答生成
    user_message = f"{comment.author}さん: {comment.message}"
    await generate_and_speak(user_message, CHARACTER_PROMPT)

    state["comments_processed"] += 1


async def idle_topic_generator():
    """コメントがない時の話題生成"""
    # Note: topic_sources は Phase 3 で実装
    # ここでは仮の話題リストを使用
    topics = [
        "最近のテクノロジーニュース",
        "おすすめのゲーム",
        "今日の天気について",
        "好きな食べ物の話",
        "最近見たアニメについて",
    ]
    topic_index = 0

    while True:
        await asyncio.sleep(5)

        # 発話中 or 最近コメントあり ならスキップ
        if state["is_speaking"]:
            continue

        idle_time = time.time() - state["last_comment_time"]

        if idle_time > settings.IDLE_THRESHOLD_SECONDS:
            topic = topics[topic_index % len(topics)]
            topic_index += 1

            print(f"Generating topic: {topic[:40]}...")
            prompt = TOPIC_PROMPT.format(topic=topic)
            await generate_and_speak(f"話題: {topic}", prompt)
            state["topics_generated"] += 1
            state["last_comment_time"] = time.time()  # リセット

            # 次の話題まで60秒待機
            await asyncio.sleep(60)


async def generate_and_speak(user_message: str, system_prompt: str):
    """LLMで応答生成 -> TTS -> 発話"""

    state["is_speaking"] = True

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
        state["memory"].add_assistant_message(clean_response)

    finally:
        state["is_speaking"] = False


async def speak(text: str, emotion: str):
    """TTS APIを呼び出して音声再生"""
    try:
        response = await state["http_client"].post(
            f"{settings.TTS_URL}/synthesize",
            json={"text": text, "emotion": emotion},
            timeout=30.0
        )

        if response.status_code == 200:
            # 音声データを再生（実際はPipeWire/PulseAudioへ出力）
            audio_data = response.content
            await play_audio(audio_data)

    except Exception as e:
        print(f"TTS Error: {e}")


async def play_audio(audio_data: bytes):
    """音声を再生（PipeWire経由でVTube Studioへ）"""
    try:
        import io

        import sounddevice as sd
        import soundfile as sf

        data, samplerate = sf.read(io.BytesIO(audio_data))
        sd.play(data, samplerate)
        sd.wait()
    except Exception as e:
        print(f"Audio playback error: {e}")


# ===== API Endpoints =====


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
    }


@app.get("/stats")
async def get_stats():
    return {
        "comments_processed": state["comments_processed"],
        "topics_generated": state["topics_generated"],
        "is_speaking": state["is_speaking"],
        "idle_time": time.time() - state["last_comment_time"],
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
