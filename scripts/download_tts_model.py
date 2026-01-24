#!/usr/bin/env python3
"""
Style-Bert-VITS2 モデルダウンロードスクリプト
利用可能なモデル: https://huggingface.co/litagin/style_bert_vits2_jvnv
"""
import argparse
import os
import sys
from pathlib import Path

try:
    from huggingface_hub import hf_hub_download, snapshot_download
except ImportError:
    print("Error: huggingface_hub not installed")
    print("Run: pip install huggingface_hub")
    sys.exit(1)


# 利用可能なモデル
AVAILABLE_MODELS = {
    "jvnv-F1-jp": {
        "repo_id": "litagin/style_bert_vits2_jvnv",
        "subfolder": "jvnv-F1-jp",
        "description": "女性声（明るい）",
    },
    "jvnv-F2-jp": {
        "repo_id": "litagin/style_bert_vits2_jvnv",
        "subfolder": "jvnv-F2-jp",
        "description": "女性声（落ち着き）",
    },
    "jvnv-M1-jp": {
        "repo_id": "litagin/style_bert_vits2_jvnv",
        "subfolder": "jvnv-M1-jp",
        "description": "男性声（若い）",
    },
    "jvnv-M2-jp": {
        "repo_id": "litagin/style_bert_vits2_jvnv",
        "subfolder": "jvnv-M2-jp",
        "description": "男性声（落ち着き）",
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
        # モデルファイルをダウンロード
        local_dir = output_dir / model_name
        local_dir.mkdir(parents=True, exist_ok=True)

        # 必要なファイル
        files = [
            f"{subfolder}/config.json",
            f"{subfolder}/{model_name}.safetensors",
            f"{subfolder}/style_vectors.npy",
        ]

        for file_path in files:
            print(f"  Downloading: {file_path}")
            hf_hub_download(
                repo_id=repo_id,
                filename=file_path,
                local_dir=output_dir,
                local_dir_use_symlinks=False,
            )

        # ファイルを正しい場所に移動
        src_dir = output_dir / subfolder
        if src_dir.exists() and src_dir != local_dir:
            for f in src_dir.iterdir():
                (local_dir / f.name).write_bytes(f.read_bytes())
            import shutil
            shutil.rmtree(src_dir)

        print(f"\nSuccess! Model saved to: {local_dir}")
        print(f"\nTo use this model, set MODEL_NAME={model_name} in your .env file")

    except Exception as e:
        print(f"Error downloading model: {e}")
        sys.exit(1)


def list_models():
    """利用可能なモデル一覧を表示"""
    print("Available Style-Bert-VITS2 models:\n")
    for name, info in AVAILABLE_MODELS.items():
        print(f"  {name}: {info['description']}")
    print(f"\nUsage: python {sys.argv[0]} <model_name>")


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
