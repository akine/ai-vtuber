import io
from typing import Optional

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI()

# グローバル変数でモデルを保持
model = None
device = "cuda" if torch.cuda.is_available() else "cpu"


class TTSRequest(BaseModel):
    text: str
    emotion: str = "neutral"
    speed: float = 1.0


class TTSResponse(BaseModel):
    success: bool
    message: str = ""


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


@app.on_event("startup")
async def startup():
    global model
    print(f"TTS Server starting on device: {device}")

    # Style-Bert-VITS2のインポートとモデルロード
    # 注意: 実際のモデルパスは環境に応じて調整が必要
    try:
        # Style-Bert-VITS2がインストールされている場合
        from style_bert_vits2.tts_model import TTSModel

        model_path = "./models/style_bert_vits2_jp_extra"
        model = TTSModel(
            model_path=model_path,
            device=device,
        )
        print("Style-Bert-VITS2 model loaded!")
    except ImportError:
        print("Warning: style-bert-vits2 not installed. Using dummy TTS mode.")
        model = None
    except Exception as e:
        print(f"Warning: Could not load TTS model: {e}")
        print("Using dummy TTS mode for testing.")
        model = None


@app.post("/synthesize")
async def synthesize(request: TTSRequest):
    """テキストを音声に変換"""
    global model

    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")

    try:
        if model is not None:
            # 実際のTTS処理
            style_vector = get_style_vector(request.emotion)

            audio, sr = model.infer(
                text=request.text,
                style_vector=style_vector,
                length_scale=1.0 / request.speed,
                noise_scale=0.667,
                noise_scale_w=0.8,
            )
        else:
            # ダミーモード: 無音を返す（テスト用）
            sr = 22050
            duration = len(request.text) * 0.1  # 文字数に応じた長さ
            audio = np.zeros(int(sr * duration), dtype=np.float32)
            print(f"[Dummy TTS] Generated silence for: {request.text[:30]}...")

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
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "device": device
    }


@app.get("/")
async def root():
    return {
        "service": "AI VTuber TTS Server",
        "model_loaded": model is not None,
        "endpoints": ["/synthesize", "/health"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
