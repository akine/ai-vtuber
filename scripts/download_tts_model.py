#!/usr/bin/env python3
"""
Style-Bert-VITS2 モデルダウンロードスクリプト
利用可能なモデル: https://huggingface.co/litagin/style_bert_vits2_jvnv
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

try:
    from huggingface_hub import snapshot_download
except ImportError:
    print("Error: huggingface_hub not installed")
    print("Run: pip install huggingface_hub")
    sys.exit(1)


# 利用可能なモデル
AVAILABLE_MODELS = {
    "jvnv-F1-jp": {
        "repo_id": "litagin/style_bert_vits2_jvnv",
        "subfolder": "jvnv-F1-jp",
        "description": "女性声（明るい・日本語）",
    },
    "jvnv-F2-jp": {
        "repo_id": "litagin/style_bert_vits2_jvnv",
        "subfolder": "jvnv-F2-jp",
        "description": "女性声（落ち着き・日本語）",
    },
    "jvnv-M1-jp": {
        "repo_id": "litagin/style_bert_vits2_jvnv",
        "subfolder": "jvnv-M1-jp",
        "description": "男性声（若い・日本語）",
    },
    "jvnv-M2-jp": {
        "repo_id": "litagin/style_bert_vits2_jvnv",
        "subfolder": "jvnv-M2-jp",
        "description": "男性声（落ち着き・日本語）",
    },
}


def download_model(model_name: str, output_dir: Path):
    """指定されたモデルをダウンロード"""
    if model_name not in AVAILABLE_MODELS:
        print(f"Error: Unknown model '{model_name}'")
        print(f"Available models: {', '.join(AVAILABLE_MODELS.keys())}")
        sys.exit(1)

    model_info = AVAILABLE_MODELS[model_name]
    repo_id = model_info["repo_id"]
    subfolder = model_info["subfolder"]

    print(f"Downloading: {model_name} ({model_info['description']})")
    print(f"Repository: {repo_id}")
    print(f"Output: {output_dir / model_name}")

    try:
        # サブフォルダのみをダウンロード
        local_dir = snapshot_download(
            repo_id=repo_id,
            allow_patterns=[f"{subfolder}/*"],
            local_dir=output_dir,
        )

        # ダウンロードしたフォルダを確認
        src_dir = Path(local_dir) / subfolder
        dst_dir = output_dir / model_name

        if src_dir.exists() and src_dir != dst_dir:
            # 既存の dst_dir を削除してから移動
            if dst_dir.exists():
                shutil.rmtree(dst_dir)
            shutil.move(str(src_dir), str(dst_dir))

        print(f"\nSuccess! Model saved to: {dst_dir}")
        print(f"\nFiles downloaded:")
        for f in dst_dir.iterdir():
            print(f"  - {f.name}")

        print(f"\nTo use this model, set TTS_MODEL_NAME={model_name} in your .env file")

    except Exception as e:
        print(f"Error downloading model: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def list_models():
    """利用可能なモデル一覧を表示"""
    print("Available Style-Bert-VITS2 models:\n")
    for name, info in AVAILABLE_MODELS.items():
        print(f"  {name}: {info['description']}")
    print(f"\nUsage: python {sys.argv[0]} <model_name>")
    print(f"Example: python {sys.argv[0]} jvnv-F1-jp")


def main():
    parser = argparse.ArgumentParser(description="Download Style-Bert-VITS2 models")
    parser.add_argument("model", nargs="?", help="Model name to download")
    parser.add_argument("-l", "--list", action="store_true", help="List available models")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path(__file__).parent.parent / "models" / "tts",
        help="Output directory"
    )

    args = parser.parse_args()

    if args.list or not args.model:
        list_models()
        return

    download_model(args.model, args.output)


if __name__ == "__main__":
    main()
