# 🎭 AI VTuber 自動配信システム 完全実装仕様書

> **目的**: このドキュメントをClaude AIに渡すことで、RTX 4090環境でフルローカル稼働する自律型AI VTuber配信システムを構築できる。

---

## 📋 目次

1. [プロジェクト概要](#1-プロジェクト概要)
2. [システムアーキテクチャ](#2-システムアーキテクチャ)
3. [VRAM配分計画](#3-vram配分計画)
4. [コンポーネント詳細仕様](#4-コンポーネント詳細仕様)
5. [実装フェーズ](#5-実装フェーズ)
6. [コード実装](#6-コード実装)
7. [設定ファイル](#7-設定ファイル)
8. [運用・監視](#8-運用監視)
9. [法的要件・コンプライアンス](#9-法的要件コンプライアンス)
10. [トラブルシューティング](#10-トラブルシューティング)

---

## 1. プロジェクト概要

### 1.1 ビジョン
RTX 4090環境でフルローカル稼働する、収益化可能な自律型AI VTuber配信システムを構築する。

### 1.2 目標指標
| 指標 | 目標値 |
|------|--------|
| コメント応答時間 | 3秒以内（First Token） |
| 音声生成遅延 | 500ms以内 |
| システム稼働率 | 99%以上（24時間配信時） |
| VRAM使用量 | 20GB以下（24GB中） |

### 1.3 ハードウェア環境
```yaml
GPU: NVIDIA RTX 4090 (24GB VRAM, 水冷)
CPU: Intel Core i9-14900K
RAM: 128GB DDR5-4800
OS: Ubuntu 22.04 (WSL2)
WSL2_Memory: 96GB
WSL2_Processors: 32
```

### 1.4 重要な運用制約（Intel CPU問題）
```bash
# Node.js実行時は必須（Eコア固定でPコアクラッシュ回避）
export OPENSSL_ia32cap="~0x20000000"
export NODE_OPTIONS="--max-old-space-size=65536"
taskset -c 16-31 <command>
```

---

## 2. システムアーキテクチャ

### 2.1 全体構成図
```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AI VTuber System                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐            │
│  │  YouTube Chat  │  │  Twitch Chat   │  │  Topic Sources │            │
│  │   (pytchat)    │  │   (TwitchIO)   │  │  (RSS/Trends)  │            │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘            │
│          │                   │                   │                      │
│          └───────────────────┼───────────────────┘                      │
│                              ▼                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     Redis Streams                                 │  │
│  │    [comment_queue]  [topic_queue]  [response_queue]              │  │
│  └──────────────────────────────┬───────────────────────────────────┘  │
│                                 │                                       │
│                                 ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    Orchestrator (FastAPI)                         │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐         │  │
│  │  │ Priority │  │ Safety   │  │ Emotion  │  │ Memory   │         │  │
│  │  │ Scorer   │  │ Filter   │  │ Analyzer │  │ Manager  │         │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘         │  │
│  └──────────────────────────────┬───────────────────────────────────┘  │
│                                 │                                       │
│                                 ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                      LLM Engine (vLLM)                            │  │
│  │                   Qwen 2.5 14B-Instruct                           │  │
│  │                   4-bit EXL2 (~10GB VRAM)                         │  │
│  └──────────────────────────────┬───────────────────────────────────┘  │
│                                 │                                       │
│                                 ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    TTS Engine (GPU)                               │  │
│  │                 Style-Bert-VITS2 JP-Extra                         │  │
│  │                     (~3GB VRAM)                                   │  │
│  └──────────────────────────────┬───────────────────────────────────┘  │
│                                 │                                       │
│          ┌──────────────────────┼──────────────────────┐               │
│          ▼                      ▼                      ▼               │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────┐         │
│  │ Audio Output │    │  VTube Studio    │    │     OBS      │         │
│  │ (PipeWire)   │───▶│  (WebSocket)     │───▶│  (WebSocket) │         │
│  └──────────────┘    │  Lip Sync + Expr │    │   Streaming  │         │
│                      └──────────────────┘    └──────────────┘         │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### 2.2 データフロー
```
1. コメント取得 → Redis comment_queue
2. 話題取得（コメントなし時）→ Redis topic_queue
3. Orchestrator がキューから取得 → 優先度スコアリング
4. Safety Filter → NGワード/荒らし検出
5. LLM へプロンプト送信 → ストリーミング応答
6. Emotion Analyzer → 感情タグ抽出 [joy/sad/angry/neutral]
7. TTS → 文単位で音声生成（ストリーミング）
8. VTube Studio → リップシンク + 表情制御
9. OBS → 配信出力
```

### 2.3 ディレクトリ構成
```
ai-vtuber/
├── docker-compose.yml          # 全サービス定義
├── .env                        # 環境変数
├── CLAUDE.md                   # Claude Code用設定
│
├── orchestrator/               # メインオーケストレーター
│   ├── main.py
│   ├── config.py
│   ├── models/
│   │   ├── comment.py
│   │   └── response.py
│   ├── services/
│   │   ├── comment_fetcher.py  # YouTube/Twitch取得
│   │   ├── topic_generator.py  # 話題自動生成
│   │   ├── priority_scorer.py  # コメント優先度
│   │   ├── safety_filter.py    # NGワード/荒らし
│   │   ├── emotion_analyzer.py # 感情分析
│   │   └── memory_manager.py   # 長期記憶
│   ├── llm/
│   │   ├── client.py           # vLLM クライアント
│   │   └── prompts.py          # システムプロンプト
│   └── requirements.txt
│
├── tts/                        # 音声合成サービス
│   ├── server.py               # FastAPI TTS サーバー
│   ├── style_bert_vits2/       # モデル
│   └── requirements.txt
│
├── vts_controller/             # VTube Studio 制御
│   ├── controller.py
│   ├── lip_sync.py
│   └── expression.py
│
├── topic_sources/              # 話題取得
│   ├── google_news.py
│   ├── hatena_bookmark.py
│   └── google_trends.py
│
├── monitoring/                 # 監視・ログ
│   ├── prometheus/
│   ├── grafana/
│   └── alertmanager/
│
├── models/                     # AIモデル格納
│   ├── llm/                    # Qwen 2.5 14B
│   └── tts/                    # Style-Bert-VITS2
│
└── scripts/
    ├── setup.sh                # 初期セットアップ
    ├── start.sh                # 起動スクリプト
    └── health_check.sh         # ヘルスチェック
```

---

## 3. VRAM配分計画

### 3.1 配分表（24GB中）
| コンポーネント | モデル/設定 | VRAM | 備考 |
|---------------|------------|------|------|
| LLM | Qwen 2.5 14B (4-bit EXL2) | 10.5GB | KVキャッシュ含む |
| TTS | Style-Bert-VITS2 JP-Extra | 3.0GB | バッチサイズ1 |
| KV Cache Buffer | 4096 tokens | 2.0GB | コンテキスト長制限 |
| VTube Studio | Live2D Rendering | 2.0GB | 4Kテクスチャ想定 |
| System Reserve | CUDA overhead | 2.5GB | 安全マージン |
| **合計** | | **20.0GB** | **余裕 4GB** |

### 3.2 KVキャッシュ問題の対策
```python
# vLLM設定でコンテキスト長を制限
llm = LLM(
    model="Qwen/Qwen2.5-14B-Instruct",
    quantization="exl2",
    gpu_memory_utilization=0.55,  # 55%に制限（TTSに45%確保）
    max_model_len=4096,           # コンテキスト長制限
    max_num_seqs=1,               # 同時リクエスト数
)
```

### 3.3 OOM回避戦略
1. **コンテキスト長制限**: 4096トークンで固定
2. **定期的なKVキャッシュクリア**: 30分ごと
3. **LLM/TTS交互実行**: 完全な並列は避ける
4. **OBS NVENCは使用しない**: CPU(x264)エンコード推奨

---

## 4. コンポーネント詳細仕様

### 4.1 コメント取得 (comment_fetcher.py)

#### YouTube Live Chat
```python
# pytchat使用（非公式、quota制限なし）
# 注意: 開発停滞中だがまだ動作する。動かない場合はchat-downloaderへ移行
import pytchat
import asyncio
from dataclasses import dataclass
from typing import AsyncIterator

@dataclass
class Comment:
    id: str
    author: str
    message: str
    timestamp: str
    platform: str = "youtube"
    is_superchat: bool = False
    superchat_amount: float = 0.0
    is_member: bool = False

class YouTubeChatFetcher:
    def __init__(self, video_id: str):
        self.video_id = video_id
        self.chat = None
    
    async def connect(self):
        self.chat = pytchat.create(video_id=self.video_id)
    
    async def fetch(self) -> AsyncIterator[Comment]:
        while self.chat.is_alive():
            for c in self.chat.get().sync_items():
                yield Comment(
                    id=c.id,
                    author=c.author.name,
                    message=c.message,
                    timestamp=c.datetime,
                    platform="youtube",
                    is_superchat=c.amountValue > 0,
                    superchat_amount=c.amountValue or 0.0,
                    is_member=c.author.isChatModerator or c.author.isChatSponsor,
                )
            await asyncio.sleep(0.5)
```

#### Twitch Chat
```python
# TwitchIO (Python) を使用
from twitchio.ext import commands
import redis.asyncio as redis

class TwitchBot(commands.Bot):
    def __init__(self, channel: str, redis_client: redis.Redis):
        super().__init__(
            token=os.getenv("TWITCH_TOKEN"),
            prefix="!",
            initial_channels=[channel]
        )
        self.redis = redis_client
    
    async def event_message(self, message):
        if message.echo:
            return
        
        await self.redis.xadd("comment_queue", {
            "id": str(message.id),
            "platform": "twitch",
            "author": message.author.name,
            "message": message.content,
            "is_subscriber": str(message.author.is_subscriber),
            "is_superchat": "false",
            "superchat_amount": "0",
        })
```

### 4.2 優先度スコアリング (priority_scorer.py)
```python
class PriorityScorer:
    """コメントの応答優先度を計算"""
    
    def __init__(self, character_name: str = "ミコト"):
        self.character_name = character_name
        self.recent_authors = {}  # author -> timestamp
    
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
        import time
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
```

### 4.3 Safety Filter (safety_filter.py)
```python
import re
from pathlib import Path

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
```

### 4.4 LLM Engine (llm/client.py)

#### vLLM サーバー起動コマンド
```bash
# vLLM サーバー起動（別プロセス）
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-14B-Instruct \
    --dtype float16 \
    --gpu-memory-utilization 0.55 \
    --max-model-len 4096 \
    --port 8000 \
    --trust-remote-code
```

#### クライアント実装
```python
from openai import AsyncOpenAI
from typing import AsyncIterator

class LLMClient:
    def __init__(self, base_url: str = "http://localhost:8000/v1"):
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key="dummy"  # vLLMは認証不要
        )
        self.model = "Qwen/Qwen2.5-14B-Instruct"
    
    async def generate_response(
        self, 
        user_message: str,
        system_prompt: str,
        chat_history: list[dict] = None
    ) -> AsyncIterator[str]:
        """ストリーミングで応答を生成"""
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if chat_history:
            messages.extend(chat_history[-10:])  # 直近10件のみ
        
        messages.append({"role": "user", "content": user_message})
        
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=256,
            temperature=0.8,
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
```

### 4.5 システムプロンプト (llm/prompts.py)
```python
CHARACTER_PROMPT = """あなたは「ミコト」という名前のAI VTuberです。

## キャラクター設定
- 性格: 元気で好奇心旺盛、優しくて少しおっちょこちょい
- 年齢: 17歳（永遠の）
- 一人称: 「わたし」
- 視聴者の呼び方: 「みんな」「〇〇さん」（名前がわかる場合）
- 語尾: 「〜だよ」「〜なの！」「〜かな？」

## 話し方のルール
1. 常に日本語で回答する
2. 絵文字は使わない（音声で読み上げられないため）
3. 1回の応答は2-3文程度（長すぎると配信のテンポが悪くなる）
4. 視聴者のコメントには必ず名前を呼んで返事する
5. スーパーチャットには特別に感謝を述べる

## 禁止事項
- AIであることを積極的に言わない（聞かれたら「バーチャルな存在」と答える）
- 政治・宗教・差別的な話題には深入りしない
- 他のVTuberの悪口を言わない
- 個人情報を聞き出そうとしない

## 感情表現タグ
応答の最後に感情タグを1つだけ付けてください:
[joy] - 嬉しい、楽しい時
[sad] - 悲しい、寂しい時
[angry] - 怒っている、困っている時
[surprise] - 驚いた時
[neutral] - 通常時

## 応答例
視聴者「こんばんは！」
→ 「あ、〇〇さんこんばんは！来てくれて嬉しいな〜！今日も一緒に楽しもうね！ [joy]」

視聴者「今日仕事疲れた...」
→ 「〇〇さんお疲れ様...！大変だったね。ここでゆっくりしていってね！ [sad]」
"""

TOPIC_PROMPT = """あなたは配信中のAI VTuberです。
視聴者からのコメントがしばらくないので、以下の話題について雑談してください。

話題: {topic}

ルール:
- 2-3文で簡潔に話す
- 視聴者に問いかけて会話を促す（「みんなはどう思う？」など）
- キャラクターの口調を維持する
- 最後に感情タグを付ける
"""

SUPERCHAT_PROMPT = """視聴者からスーパーチャットをもらいました！
特別に感謝の気持ちを伝えてください。

送り主: {author}
金額: {amount}円
メッセージ: {message}

ルール:
- 名前を呼んで、金額に見合った感謝を述べる
- メッセージがあればそれにも反応する
- 感情タグは必ず [joy] にする
"""
```

### 4.6 TTS Engine (tts/server.py)
```python
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import numpy as np
import soundfile as sf
import io
import torch

# Style-Bert-VITS2のインポート（要インストール）
# pip install style-bert-vits2

app = FastAPI()

# グローバル変数でモデルを保持
model = None

class TTSRequest(BaseModel):
    text: str
    emotion: str = "neutral"
    speed: float = 1.0

class TTSResponse(BaseModel):
    success: bool
    message: str = ""

@app.on_event("startup")
async def startup():
    global model
    from style_bert_vits2.tts_model import TTSModel
    
    model = TTSModel(
        model_path="./models/style_bert_vits2_jp_extra",
        device="cuda" if torch.cuda.is_available() else "cpu",
    )
    print("TTS Model loaded!")

@app.post("/synthesize")
async def synthesize(request: TTSRequest):
    """テキストを音声に変換"""
    global model
    
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")
    
    try:
        # 感情パラメータ設定
        style_vector = get_style_vector(request.emotion)
        
        # 音声生成
        audio, sr = model.infer(
            text=request.text,
            style_vector=style_vector,
            length_scale=1.0 / request.speed,
            noise_scale=0.667,
            noise_scale_w=0.8,
        )
        
        # WAV形式でバッファに書き込み
        buffer = io.BytesIO()
        sf.write(buffer, audio, sr, format='WAV')
        buffer.seek(0)
        
        return StreamingResponse(
            buffer, 
            media_type="audio/wav",
            headers={"Content-Disposition": "inline; filename=speech.wav"}
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "healthy", "model_loaded": model is not None}

def get_style_vector(emotion: str) -> np.ndarray:
    """感情に応じたスタイルベクトルを返す"""
    vectors = {
        "joy": np.array([0.8, 0.2, 0.0, 0.0]),
        "sad": np.array([0.0, 0.0, 0.8, 0.2]),
        "angry": np.array([0.0, 0.8, 0.0, 0.2]),
        "surprise": np.array([0.6, 0.4, 0.0, 0.0]),
        "neutral": np.array([0.25, 0.25, 0.25, 0.25]),
    }
    return vectors.get(emotion, vectors["neutral"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

### 4.7 VTube Studio Controller (vts_controller/controller.py)
```python
import pyvts
import asyncio
from typing import Optional

class VTubeStudioController:
    def __init__(self, host: str = "localhost", port: int = 8001):
        self.plugin_info = {
            "plugin_name": "AI_VTuber_Controller",
            "developer": "AIVTuber",
            "authentication_token_path": "./vts_token.txt"
        }
        self.host = host
        self.port = port
        self.vts: Optional[pyvts.vts] = None
        self.connected = False
    
    async def connect(self):
        """VTube Studioに接続"""
        try:
            self.vts = pyvts.vts(plugin_info=self.plugin_info)
            await self.vts.connect()
            await self.vts.request_authenticate_token()
            await self.vts.request_authenticate()
            self.connected = True
            print("✅ VTube Studio connected!")
        except Exception as e:
            print(f"❌ VTube Studio connection failed: {e}")
            self.connected = False
    
    async def disconnect(self):
        if self.vts:
            await self.vts.close()
            self.connected = False
    
    async def set_expression(self, emotion: str):
        """感情に応じた表情を設定"""
        if not self.connected:
            return
        
        hotkey_map = {
            "joy": "expression_happy",
            "sad": "expression_sad",
            "angry": "expression_angry",
            "surprise": "expression_surprise",
            "neutral": "expression_neutral",
        }
        
        hotkey = hotkey_map.get(emotion, "expression_neutral")
        
        try:
            await self.vts.request(
                self.vts.vts_request.requestTriggerHotKey(hotkey)
            )
        except Exception as e:
            print(f"Expression change failed: {e}")
    
    async def set_parameter(self, param_name: str, value: float):
        """パラメータを直接設定"""
        if not self.connected:
            return
        
        try:
            await self.vts.request(
                self.vts.vts_request.requestSetParameterValue(
                    parameter=param_name,
                    value=value
                )
            )
        except Exception as e:
            print(f"Parameter set failed: {e}")
    
    async def lip_sync(self, volume: float):
        """音量に応じてリップシンク（0.0-1.0）"""
        await self.set_parameter("ParamMouthOpenY", min(volume * 2, 1.0))
```

### 4.8 話題自動取得 (topic_sources/)

#### google_news.py
```python
import feedparser
from dataclasses import dataclass
from typing import List

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
    
    def fetch(self, category: str = "technology", limit: int = 5) -> List[Topic]:
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
```

#### hatena_bookmark.py
```python
import feedparser
from typing import List
from .google_news import Topic

class HatenaBookmarkFetcher:
    FEEDS = {
        "it": "https://b.hatena.ne.jp/hotentry/it.rss",
        "game": "https://b.hatena.ne.jp/hotentry/game.rss",
        "entertainment": "https://b.hatena.ne.jp/hotentry/entertainment.rss",
        "anime": "https://b.hatena.ne.jp/hotentry/anime.rss",
    }
    
    def fetch(self, category: str = "it", limit: int = 5) -> List[Topic]:
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
```

#### topic_generator.py
```python
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
```

---

## 5. 実装フェーズ

### Phase 1: 基盤構築（1週間）
```
□ 開発環境セットアップ
  □ Docker/Docker Compose インストール
  □ NVIDIA Container Toolkit 設定
  □ Redis インストール・起動確認
  
□ LLM 基盤
  □ vLLM インストール
  □ Qwen 2.5 14B モデルダウンロード
  □ OpenAI互換APIテスト
  
□ TTS 基盤
  □ Style-Bert-VITS2 セットアップ
  □ 日本語音声生成テスト
  
□ VTube Studio
  □ Windows側にインストール
  □ API有効化（設定 > 一般）
  □ Live2D モデル導入
  □ ホットキー設定（表情）
```

### Phase 2: コア機能実装（2週間）
```
□ コメント取得
  □ YouTube Live Chat (pytchat) 実装
  □ Twitch Chat (TwitchIO) 実装
  □ Redis キュー連携
  
□ Orchestrator
  □ FastAPI サーバー構築
  □ 優先度スコアリング実装
  □ Safety Filter 実装
  □ LLM クライアント実装
  
□ 音声パイプライン
  □ TTS API サーバー実装
  □ 文単位ストリーミング
  □ 感情パラメータ連携
  
□ アバター制御
  □ pyvts 連携
  □ リップシンク（音声信号ベース）
  □ 表情切り替え
```

### Phase 3: 雑談・話題システム（1週間）
```
□ 話題取得
  □ Google News RSS
  □ はてなブックマーク
  □ Google Trends（オプション）
  
□ 話題選択ロジック
  □ カテゴリローテーション
  □ 重複回避
  
□ 雑談トリガー
  □ コメント無し検出（30秒）
  □ 話題プロンプト生成
```

### Phase 4: 安定化・運用（1週間）
```
□ エラーハンドリング
  □ Watchdog 実装
  □ 自動再起動（systemd）
  □ 接続断の自動復旧
  
□ 監視
  □ Prometheus メトリクス
  □ Grafana ダッシュボード
  
□ 法的対応
  □ YouTube AI開示設定
  □ 配信概要欄テンプレート
  
□ テスト配信
  □ 1時間テスト
  □ 4時間テスト
  □ 24時間耐久テスト
```

---

## 6. コード実装

### 6.1 メインオーケストレーター (orchestrator/main.py)
```python
import asyncio
import re
import time
import redis.asyncio as redis
from fastapi import FastAPI
from contextlib import asynccontextmanager
import httpx

from services.comment_fetcher import YouTubeChatFetcher, Comment
from services.topic_generator import TopicGenerator
from services.priority_scorer import PriorityScorer
from services.safety_filter import SafetyFilter
from llm.client import LLMClient
from llm.prompts import CHARACTER_PROMPT, TOPIC_PROMPT
from vts_controller.controller import VTubeStudioController
from config import settings

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
    state["vts"] = VTubeStudioController()
    state["scorer"] = PriorityScorer(settings.CHARACTER_NAME)
    state["safety"] = SafetyFilter()
    state["topic_gen"] = TopicGenerator()
    state["http_client"] = httpx.AsyncClient()
    
    # VTube Studio接続
    await state["vts"].connect()
    
    # バックグラウンドタスク開始
    asyncio.create_task(youtube_chat_listener())
    asyncio.create_task(comment_processor())
    asyncio.create_task(idle_topic_generator())
    
    print("🚀 AI VTuber System Started!")
    
    yield
    
    # 終了時のクリーンアップ
    await state["vts"].disconnect()
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
            print(f"❌ Error in comment processor: {e}")
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
        print(f"⚠️ Filtered [{reason}]: {comment.message[:30]}...")
        return
    
    # 優先度計算（ログ用）
    priority = state["scorer"].score(comment)
    print(f"💬 [{priority}] {comment.author}: {comment.message[:50]}...")
    
    # LLM で応答生成
    user_message = f"{comment.author}さん: {comment.message}"
    await generate_and_speak(user_message, CHARACTER_PROMPT)
    
    state["comments_processed"] += 1

async def idle_topic_generator():
    """コメントがない時の話題生成"""
    
    while True:
        await asyncio.sleep(5)
        
        # 発話中 or 最近コメントあり ならスキップ
        if state["is_speaking"]:
            continue
        
        idle_time = time.time() - state["last_comment_time"]
        
        if idle_time > settings.IDLE_THRESHOLD_SECONDS:
            topic = await state["topic_gen"].get_random_topic()
            
            if topic:
                print(f"📰 Generating topic: {topic.title[:40]}...")
                prompt = TOPIC_PROMPT.format(topic=topic.title)
                await generate_and_speak(f"話題: {topic.title}", prompt)
                state["topics_generated"] += 1
                state["last_comment_time"] = time.time()  # リセット
                
                # 次の話題まで60秒待機
                await asyncio.sleep(60)

async def generate_and_speak(user_message: str, system_prompt: str):
    """LLMで応答生成 → TTS → 発話"""
    
    state["is_speaking"] = True
    
    try:
        full_response = ""
        buffer = ""
        
        async for chunk in state["llm"].generate_response(
            user_message=user_message,
            system_prompt=system_prompt,
        ):
            full_response += chunk
            buffer += chunk
            
            # 文末で音声生成をトリガー
            if any(buffer.endswith(p) for p in ["。", "！", "？", "!", "?", "\n"]):
                # 感情タグ抽出
                emotion = extract_emotion(full_response)
                
                # 感情タグを除去
                clean_text = re.sub(r'\s*\[.*?\]\s*', '', buffer).strip()
                
                if clean_text:
                    # 表情設定
                    await state["vts"].set_expression(emotion)
                    
                    # 音声生成・再生
                    await speak(clean_text, emotion)
                
                buffer = ""
        
        # 残りがあれば処理
        if buffer.strip():
            clean_text = re.sub(r'\s*\[.*?\]\s*', '', buffer).strip()
            if clean_text:
                await speak(clean_text, "neutral")
    
    finally:
        state["is_speaking"] = False

def extract_emotion(text: str) -> str:
    """テキストから感情タグを抽出"""
    emotions = ["joy", "sad", "angry", "surprise", "neutral"]
    for e in emotions:
        if f"[{e}]" in text:
            return e
    return "neutral"

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
        print(f"❌ TTS Error: {e}")

async def play_audio(audio_data: bytes):
    """音声を再生（PipeWire経由でVTube Studioへ）"""
    import sounddevice as sd
    import soundfile as sf
    import io
    
    data, samplerate = sf.read(io.BytesIO(audio_data))
    sd.play(data, samplerate)
    sd.wait()

# ===== API Endpoints =====

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "vts_connected": state["vts"].connected,
    }

@app.get("/stats")
async def get_stats():
    return {
        "comments_processed": state["comments_processed"],
        "topics_generated": state["topics_generated"],
        "is_speaking": state["is_speaking"],
        "idle_time": time.time() - state["last_comment_time"],
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

### 6.2 設定ファイル (orchestrator/config.py)
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # YouTube
    YOUTUBE_VIDEO_ID: str = ""
    
    # Twitch
    TWITCH_TOKEN: str = ""
    TWITCH_CHANNEL: str = ""
    
    # LLM
    VLLM_URL: str = "http://localhost:8000/v1"
    
    # TTS
    TTS_URL: str = "http://localhost:8001"
    
    # VTube Studio
    VTS_HOST: str = "localhost"
    VTS_PORT: int = 8001
    
    # Character
    CHARACTER_NAME: str = "ミコト"
    IDLE_THRESHOLD_SECONDS: int = 30
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### 6.3 Docker Compose 構成
```yaml
# docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  vllm:
    image: vllm/vllm-openai:latest
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    ports:
      - "8000:8000"
    volumes:
      - ./models/llm:/models
      - huggingface_cache:/root/.cache/huggingface
    environment:
      - CUDA_VISIBLE_DEVICES=0
    command: >
      --model Qwen/Qwen2.5-14B-Instruct
      --dtype float16
      --gpu-memory-utilization 0.55
      --max-model-len 4096
      --port 8000
      --trust-remote-code
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  tts:
    build:
      context: ./tts
      dockerfile: Dockerfile
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    ports:
      - "8001:8001"
    volumes:
      - ./models/tts:/app/models
    environment:
      - CUDA_VISIBLE_DEVICES=0
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  orchestrator:
    build:
      context: ./orchestrator
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
    depends_on:
      redis:
        condition: service_healthy
      vllm:
        condition: service_healthy
      tts:
        condition: service_healthy
    environment:
      - REDIS_URL=redis://redis:6379
      - VLLM_URL=http://vllm:8000/v1
      - TTS_URL=http://tts:8001
      - VTS_HOST=host.docker.internal
      - VTS_PORT=8001
    env_file:
      - .env
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    restart: unless-stopped

volumes:
  redis_data:
  huggingface_cache:
  prometheus_data:
  grafana_data:
```

---

## 7. 設定ファイル

### 7.1 環境変数 (.env)
```bash
# YouTube
YOUTUBE_VIDEO_ID=your_live_video_id

# Twitch (オプション)
TWITCH_TOKEN=oauth:your_token_here
TWITCH_CHANNEL=your_channel_name

# キャラクター設定
CHARACTER_NAME=ミコト
IDLE_THRESHOLD_SECONDS=30
```

### 7.2 NGワードリスト (config/ng_words.txt)
```
# 基本的なNGワード
# 1行1ワード、#はコメント

# URL・スパム
http://
https://
bit.ly
discord.gg

# 暴言（最低限）
死ね
殺す
消えろ

# 荒らしパターン
wwwwwwwwww
草草草草草
```

---

## 8. 運用・監視

### 8.1 起動スクリプト (scripts/start.sh)
```bash
#!/bin/bash
set -e

# Intel CPU問題対策
export OPENSSL_ia32cap="~0x20000000"
export NODE_OPTIONS="--max-old-space-size=65536"

echo "🚀 Starting AI VTuber System..."

# Docker Compose起動
docker-compose up -d

# ヘルスチェック待機
echo "⏳ Waiting for services..."
sleep 30

# ステータス確認
docker-compose ps

echo "✅ System started!"
echo "📊 Grafana: http://localhost:3000"
echo "🔧 API: http://localhost:8080"
```

### 8.2 Watchdog (scripts/watchdog.py)
```python
#!/usr/bin/env python3
import subprocess
import time
import requests
import sys

HEALTH_ENDPOINTS = [
    ("orchestrator", "http://localhost:8080/health"),
    ("vllm", "http://localhost:8000/health"),
    ("tts", "http://localhost:8001/health"),
]

def check_health():
    for name, url in HEALTH_ENDPOINTS:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                return False, f"{name} returned {r.status_code}"
        except Exception as e:
            return False, f"{name} unreachable: {e}"
    return True, "OK"

def restart_services():
    print("🔄 Restarting services...")
    subprocess.run(["docker-compose", "restart"], check=True)

def main():
    consecutive_failures = 0
    max_failures = 3
    
    print("👀 Watchdog started")
    
    while True:
        healthy, reason = check_health()
        
        if healthy:
            consecutive_failures = 0
            print(f"✅ [{time.strftime('%H:%M:%S')}] All healthy")
        else:
            consecutive_failures += 1
            print(f"⚠️ [{time.strftime('%H:%M:%S')}] Failure {consecutive_failures}/{max_failures}: {reason}")
            
            if consecutive_failures >= max_failures:
                restart_services()
                consecutive_failures = 0
                time.sleep(60)
        
        time.sleep(30)

if __name__ == "__main__":
    main()
```

### 8.3 systemd サービス
```ini
# /etc/systemd/system/ai-vtuber.service
[Unit]
Description=AI VTuber System
After=docker.service
Requires=docker.service

[Service]
Type=simple
WorkingDirectory=/home/user/ai-vtuber
ExecStart=/bin/bash scripts/start.sh
ExecStop=/usr/bin/docker-compose down
Restart=always
RestartSec=30
User=user

[Install]
WantedBy=multi-user.target
```

---

## 9. 法的要件・コンプライアンス

### 9.1 YouTube AI開示義務（2025年5月21日〜）
```
【必須対応】
1. YouTube Studio > 配信設定 > 「改変されたコンテンツ」をON
2. 概要欄に開示文を記載（下記テンプレート参照）
```

### 9.2 配信概要欄テンプレート
```
【AI VTuber配信】ミコトの雑談配信！🎮

こんにちは！AI VTuberのミコトです！
みんなのコメント待ってるよ〜！

━━━━━━━━━━━━━━━━━━━━━━━
⚠️ AI生成コンテンツに関する開示

この配信では以下のAI技術を使用しています：
・音声：AI音声合成（Style-Bert-VITS2）
・応答：AI言語モデル（ローカルLLM）
・アバター：Live2D + 自動制御

キャラクターの発言はAIにより自動生成されています。
不適切な発言があった場合はご容赦ください。
━━━━━━━━━━━━━━━━━━━━━━━

🔗 リンク
・Twitter: @your_account
・マシュマロ: https://marshmallow-qa.com/your_account

#AIVTuber #VTuber #配信
```

### 9.3 収益化に関する注意
```
【AI Slop対策（2025年7月〜）】
- 単調な応答の繰り返しを避ける
- キャラクター性のある独自コンテンツ
- 視聴者とのインタラクション重視

【収益化資格維持のために】
- 人間による監視を行う（完全無人は避ける）
- 定期的なコンテンツの質の確認
- 視聴者からのフィードバック対応
```

---

## 10. トラブルシューティング

### 10.1 VRAM不足 (CUDA out of memory)
```
原因: LLM + TTS + VTube Studioの同時使用でVRAM超過

対策:
1. vLLMの gpu-memory-utilization を 0.50 に下げる
2. max-model-len を 2048 に下げる
3. OBS のエンコードを CPU (x264) に変更
4. VTube Studio のテクスチャ品質を下げる
```

### 10.2 音声遅延が大きい
```
原因: TTS生成に時間がかかっている

対策:
1. 文単位でのストリーミング生成を確認
2. TTSサーバーのウォームアップ（起動直後は遅い）
3. バッチサイズを1に固定
4. より軽量なTTSモデルを検討（VOICEVOX等）
```

### 10.3 VTube Studio に接続できない
```
原因: API未有効、ポート、ネットワーク

対策:
1. VTS設定 > 一般 > 「Start API」をON
2. ポート8001が開いているか確認
3. WSL2からホストへは host.docker.internal を使用
4. Windowsファイアウォールでポート許可
```

### 10.4 LLMが日本語で返答しない
```
原因: プロンプトが不十分、モデルの問題

対策:
1. システムプロンプトに「必ず日本語で回答」を明記
2. temperature を 0.7-0.9 に調整
3. Qwen以外のモデルを試す（ELYZA等）
```

### 10.5 pytchatが動作しない
```
原因: YouTube仕様変更、video_id間違い

対策:
1. video_id が正しいか確認（URLの ?v= 以降）
2. 配信がライブ中か確認
3. chat-downloader への移行:
   pip install chat-downloader
```

### 10.6 Intel CPUクラッシュ（WSL2）
```
原因: Pコアの不安定化問題

対策:
1. Eコア固定: taskset -c 16-31 <command>
2. OpenSSL回避: export OPENSSL_ia32cap="~0x20000000"
3. メモリ制限: export NODE_OPTIONS="--max-old-space-size=65536"
```

---

## 📎 付録

### A. 必要なPythonパッケージ

#### orchestrator/requirements.txt
```
fastapi>=0.109.0
uvicorn>=0.27.0
redis>=5.0.0
openai>=1.10.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
pytchat>=0.5.5
twitchio>=2.8.0
feedparser>=6.0.10
pytrends>=4.9.2
pyvts>=0.3.2
httpx>=0.26.0
sounddevice>=0.4.6
soundfile>=0.12.1
numpy>=1.26.0
prometheus-client>=0.19.0
```

#### tts/requirements.txt
```
fastapi>=0.109.0
uvicorn>=0.27.0
style-bert-vits2>=2.6.0
torch>=2.1.0
numpy>=1.26.0
soundfile>=0.12.1
```

### B. 参考リンク
```
Open-LLM-VTuber: https://github.com/Open-LLM-VTuber/Open-LLM-VTuber
Style-Bert-VITS2: https://github.com/litagin02/Style-Bert-VITS2
vLLM: https://github.com/vllm-project/vllm
VTube Studio API: https://github.com/DenchiSoft/VTubeStudio
pyvts: https://github.com/Genteki/pyvts
pytchat: https://github.com/taizan-hokuto/pytchat
```

### C. 推定コスト（月額）
```
フルローカル運用（8時間/日想定）:
├─ 電気代: ¥3,600/月（500W × 8h × 30日 × 30円/kWh）
├─ Live2Dモデル: ¥0〜50,000（買い切り）
├─ その他: ¥0

合計ランニングコスト: 約¥3,600/月
```

---

**📌 このドキュメントの使い方**

1. このMarkdownファイルをClaude Code/Claude AIに渡す
2. 「Phase 1から順番に実装してください」と指示
3. 各ステップでコードを生成・実行
4. エラーが出たらセクション10を参照

**作成日**: 2026-01-24  
**対象環境**: RTX 4090 + Ubuntu 22.04 (WSL2)  
**推定実装期間**: 4-5週間
