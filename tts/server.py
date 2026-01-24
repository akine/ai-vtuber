"""
Style-Bert-VITS2 TTS Server
AI VTuber用の感情付き音声合成サーバー
"""
import io
import os
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="AI VTuber TTS Server")

# グローバル変数
tts_model = None
device = "cuda" if torch.cuda.is_available() else "cpu"

# モデルパス設定
MODEL_DIR = Path(os.getenv("MODEL_DIR", "/app/models"))
MODEL_NAME = os.getenv("MODEL_NAME", "jvnv-F1-jp")  # デフォルトモデル


class TTSRequest(BaseModel):
    text: str
    emotion: str = "neutral"
    speed: float = 1.0
    speaker_id: int = 0


# 感情からスタイルへのマッピング
EMOTION_TO_STYLE = {
    "joy": "Happy",
    "happy": "Happy",
    "sad": "Sad",
    "angry": "Angry",
    "surprise": "Happy",  # Surpriseがない場合Happyで代用
    "neutral": "Neutral",
}


@app.on_event("startup")
async def startup():
    global tts_model
    print(f"TTS Server starting on device: {device}")
    print(f"Model directory: {MODEL_DIR}")

    try:
        from style_bert_vits2.nlp import bert_models
        from style_bert_vits2.constants import Languages
        from style_bert_vits2.tts_model import TTSModel

        # BERTモデルのロード（日本語）
        bert_models.load_model(Languages.JP, "ku-nlp/deberta-v2-large-japanese-char-wwm")
        bert_models.load_tokenizer(Languages.JP, "ku-nlp/deberta-v2-large-japanese-char-wwm")

        # TTSモデルのパスを探す
        model_path = MODEL_DIR / MODEL_NAME
        if not model_path.exists():
            # models/tts/ 以下も探す
            alt_path = MODEL_DIR / "tts" / MODEL_NAME
            if alt_path.exists():
                model_path = alt_path

        config_path = model_path / "config.json"
        style_file = model_path / "style_vectors.npy"

        # モデルファイルを検索（バージョン番号付きの場合あり）
        model_file = None
        for f in model_path.glob("*.safetensors"):
            model_file = f
            break

        if not config_path.exists() or model_file is None:
            print(f"Warning: Model config not found at {config_path}")
            print("Running in dummy mode. Download a model first.")
            tts_model = None
            return

        tts_model = TTSModel(
            model_path=str(model_file),
            config_path=str(config_path),
            style_vec_path=str(style_file) if style_file.exists() else None,
            device=device,
        )
        print(f"Style-Bert-VITS2 model loaded: {MODEL_NAME}")

    except ImportError as e:
        print(f"Warning: style-bert-vits2 not installed: {e}")
        print("Running in dummy mode.")
        tts_model = None
    except Exception as e:
        print(f"Warning: Could not load TTS model: {e}")
        print("Running in dummy mode.")
        tts_model = None


@app.post("/synthesize")
async def synthesize(request: TTSRequest):
    """テキストを音声に変換"""
    global tts_model

    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")

    try:
        if tts_model is not None:
            # Style-Bert-VITS2で音声生成
            style = EMOTION_TO_STYLE.get(request.emotion.lower(), "Neutral")

            sr, audio = tts_model.infer(
                text=text,
                language="JP",
                speaker_id=request.speaker_id,
                style=style,
                style_weight=1.0,
                length=1.0 / request.speed,
            )
            audio = audio.astype(np.float32) / 32768.0  # int16 -> float32

        else:
            # ダミーモード: サイン波を生成（テスト確認用）
            sr = 22050
            duration = max(len(text) * 0.08, 0.5)  # 最低0.5秒
            t = np.linspace(0, duration, int(sr * duration))
            # 440Hzのサイン波（確認用）
            audio = (np.sin(2 * np.pi * 440 * t) * 0.3).astype(np.float32)
            print(f"[Dummy TTS] Generated tone for: {text[:30]}...")

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
        print(f"TTS Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "model_loaded": tts_model is not None,
        "model_name": MODEL_NAME if tts_model else None,
        "device": device
    }


@app.get("/")
async def root():
    return {
        "service": "AI VTuber TTS Server (Style-Bert-VITS2)",
        "model_loaded": tts_model is not None,
        "model_name": MODEL_NAME,
        "endpoints": ["/synthesize", "/health"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
