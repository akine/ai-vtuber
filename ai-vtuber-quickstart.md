# 🚀 AI VTuber クイックスタートガイド

## このドキュメントセットの使い方

### 📦 含まれるファイル

| ファイル | 用途 |
|---------|------|
| `ai-vtuber-system-spec.md` | 完全実装仕様書（Claude AIに投げる用） |
| `ai-vtuber-CLAUDE.md` | Claude Code用設定（プロジェクトルートに配置） |

---

## Step 1: Claude AIで実装を開始

### 方法A: Claude.ai（Web版）

1. https://claude.ai を開く
2. 新規チャットで以下を送信:

```
以下の仕様書に基づいて、AI VTuber自動配信システムを実装してください。
Phase 1（基盤構築）から順番に進めてください。

[ai-vtuber-system-spec.md の内容をコピペ]
```

### 方法B: Claude Code（ターミナル）

1. プロジェクトディレクトリを作成:
```bash
mkdir -p ~/ai-vtuber
cd ~/ai-vtuber
```

2. CLAUDE.md を配置:
```bash
cp ai-vtuber-CLAUDE.md ~/ai-vtuber/CLAUDE.md
```

3. Claude Code を起動（Intel CPU対策付き）:
```bash
export OPENSSL_ia32cap="~0x20000000"
export NODE_OPTIONS="--max-old-space-size=65536"
taskset -c 16-31 claude
```

4. 実装を依頼:
```
ai-vtuber-system-spec.md を読んで、Phase 1から実装を始めてください。
```

---

## Step 2: 前提条件の確認

### 必要なソフトウェア

```bash
# Docker & Docker Compose
docker --version
docker-compose --version

# NVIDIA Container Toolkit
nvidia-smi

# Python 3.11+
python3 --version

# Redis（Docker経由でも可）
redis-cli --version
```

### VTube Studio（Windows側）

1. Steam からインストール
2. 設定 > 一般 > 「Start API (Allow Plugins)」をON
3. ポート 8001 を確認
4. Live2D モデルを用意

---

## Step 3: 最初の実装目標

### Phase 1 完了チェックリスト

- [ ] Docker Compose で Redis 起動
- [ ] vLLM サーバー起動（Qwen 2.5 14B）
- [ ] Style-Bert-VITS2 セットアップ
- [ ] VTube Studio API 接続テスト
- [ ] 簡単な「Hello World」応答

### 最小動作確認コマンド

```bash
# 1. Redis 起動
docker run -d -p 6379:6379 redis:7-alpine

# 2. vLLM 起動確認（モデルDL後）
curl http://localhost:8000/v1/models

# 3. TTS テスト
curl -X POST http://localhost:8001/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "こんにちは、わたしはミコトだよ！", "emotion": "joy"}'
```

---

## 💡 Tips

### Claude AIへの効果的な指示

```
❌ 悪い例: 「AIVTuber作って」
✅ 良い例: 「ai-vtuber-system-spec.md のPhase 2、コメント取得の実装をしてください。pytchatを使ってYouTube Live Chatからコメントを取得し、Redisキューに投入するコードを書いてください。」
```

### 段階的に進める

1. まず **Phase 1** を完全に動作させる
2. 各コンポーネントを **個別にテスト**
3. 全部動いてから **統合**

### デバッグのコツ

```bash
# vLLM のログを見る
docker-compose logs -f vllm

# GPU使用量を監視
watch -n 1 nvidia-smi

# Redis キューの中身を確認
redis-cli XREAD STREAMS comment_queue 0
```

---

## 📞 困ったら

1. **仕様書のセクション10**（トラブルシューティング）を確認
2. **GitHub Issues** を検索（Open-LLM-VTuber等）
3. **Claude AI** にエラーメッセージを貼って質問

---

**Good luck! 🎭✨**

