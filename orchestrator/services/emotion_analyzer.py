import re


def extract_emotion(text: str) -> str:
    """テキストから感情タグを抽出"""
    emotions = ["joy", "sad", "angry", "surprise", "neutral"]
    for e in emotions:
        if f"[{e}]" in text:
            return e
    return "neutral"


def remove_emotion_tags(text: str) -> str:
    """テキストから感情タグを除去"""
    return re.sub(r'\s*\[(?:joy|sad|angry|surprise|neutral)\]\s*', '', text).strip()
