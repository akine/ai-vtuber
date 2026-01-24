# AI VTuber 自動配信システム - Claude Code 設定

## 🖥️ ハードウェア構成

- **CPU**: Intel Core i9-14900K (BIOS Ver 3107 / Microcode 0x12F 適用済み)
- **RAM**: 128GB (DDR5-4800 32GBx4)
- **GPU**: NVIDIA GeForce RTX 4090 (24GB VRAM / 水冷)
- **OS**: Windows 11 Pro + WSL2 (Ubuntu 22.04)

## ⚙️ WSL2 設定 (.wslconfig)

- **Memory**: 96GB (物理128GB中)
- **Processors**: 32 (全スレッド)
- **Swap**: 32GB

## ⚠️ 運用上の制約 (重要・必読)

Intel CPUの不安定化問題回避のため、**Node.js実行時は以下を必須**とする:

```bash
# 1. Eコア固定: Pコア(0-15)を回避
taskset -c 16-31 <command>

# 2. メモリ最大化: 64GB割り当て
export NODE_OPTIONS="--max-old-space-size=65536"

# 3. OpenSSL回避: 暗号化エラー防止
export OPENSSL_ia32cap="~0x20000000"
```

### 起動エイリアス（.bash_aliases 登録済み）

```bash
alias cc='export OPENSSL_ia32cap="~0x20000000" && export NODE_OPTIONS="--max-old-space-size=65536" && taskset -c 16-31 claude'
```

### 📌 重要な注意事項

- **必ずEコア(16-31)で実行**: Pコア使用はCPUクラッシュリスクあり
- **OpenSSL回避設定は必須**: 設定なしで暗号化通信時エラー
- **メモリ64GB割り当て推奨**: 大規模コードベース解析時に必要

---

## 📁 プロジェクト情報

- **プロジェクト名**: AI VTuber 自動配信システム
- **説明**: RTX 4090環境でフルローカル稼働する自律型AI VTuber配信システム
- **目標**: 視聴者コメントへのリアルタイム応答 + 自動雑談生成による24時間配信

## 🛠️ 技術スタック

| レイヤー | 技術 | 備考 |
|---------|------|------|
| LLM | Qwen 2.5 14B-Instruct (4-bit) | vLLM経由、~10GB VRAM |
| TTS | Style-Bert-VITS2 JP-Extra | ~3GB VRAM |
| アバター | VTube Studio + Live2D | Windows側、WebSocket API |
| オーケストレーション | Python 3.11 + FastAPI | 非同期処理 |
| キュー | Redis Streams | コメント/話題キュー |
| 配信 | OBS Studio | x264エンコード推奨 |
| コンテナ | Docker Compose | 全サービス管理 |

## 📂 ディレクトリ構成

```
ai-vtuber/
├── CLAUDE.md                   # この設定ファイル
├── docker-compose.yml
├── .env
│
├── orchestrator/               # メインサービス
│   ├── main.py                 # FastAPIエントリポイント
│   ├── config.py               # pydantic-settings
│   ├── services/               # ビジネスロジック
│   ├── llm/                    # LLMクライアント
│   └── requirements.txt
│
├── tts/                        # 音声合成サービス
│   ├── server.py
│   └── Dockerfile
│
├── vts_controller/             # VTube Studio制御
│   └── controller.py
│
├── models/                     # AIモデル格納
│   ├── llm/
│   └── tts/
│
├── monitoring/                 # 監視設定
│   ├── prometheus/
│   │   └── prometheus.yml
│   └── grafana/
│       └── provisioning/
│           ├── datasources/prometheus.yml
│           └── dashboards/ai-vtuber.json
│
└── scripts/                    # 運用スクリプト
    ├── start.sh
    ├── stop.sh
    ├── health_check.sh
    └── watchdog.py
```

## 🎯 開発ガイドライン

### コーディング規約

1. **Python 3.11+** を使用
2. **型ヒント必須** - すべての関数に型アノテーション
3. **非同期優先** - I/O処理はすべて `async/await`
4. **Pydantic** - データモデルはPydanticで定義
5. **docstring** - 公開関数にはdocstring必須

### VRAM配分ルール（24GB中）

```
LLM (Qwen 14B 4-bit):  10.5GB
TTS (Style-Bert-VITS2): 3.0GB
KV Cache:               2.0GB
VTube Studio:           2.0GB
System Reserve:         2.5GB
─────────────────────────────
合計:                  20.0GB（余裕4GB）
```

### 重要な設計原則

1. **LLMとTTSは同時実行しない** - VRAM競合回避
2. **コンテキスト長は4096トークンに制限** - KVキャッシュ爆発防止
3. **文単位でTTS生成** - レイテンシ最適化
4. **OBSはCPUエンコード(x264)** - GPU負荷軽減

## 🔧 よく使うコマンド

```bash
# サービス起動
docker-compose up -d

# ログ確認
docker-compose logs -f orchestrator

# vLLM単体テスト
curl http://localhost:8000/v1/models

# TTS単体テスト
curl -X POST http://localhost:8001/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "こんにちは", "emotion": "joy"}'

# ヘルスチェック
curl http://localhost:8080/health
```

## 📝 実装時の注意点

### pytchat について
- 開発停滞中（最終更新2021年）だが動作する
- 動かない場合は `chat-downloader` へ移行
- YouTube API quota制限を回避できる

### VTube Studio連携
- Windows側で起動、API有効化必須
- WSL2からは `host.docker.internal:8001` で接続
- pyvts ライブラリを使用

### 感情タグ
- LLM応答の末尾に `[joy]` `[sad]` `[angry]` `[surprise]` `[neutral]` を付与
- TTSのスタイルベクトルとVTS表情切り替えに使用
- 正規表現で除去してから音声化

## 🚨 トラブルシューティング

| 症状 | 原因 | 対策 |
|------|------|------|
| CUDA OOM | VRAM超過 | gpu-memory-utilization を 0.50 に |
| 音声遅延 | TTS生成遅い | 文単位ストリーミング確認 |
| VTS接続失敗 | API未有効 | VTS設定でAPI ON |
| 日本語で返答しない | プロンプト不足 | 「必ず日本語で」を明記 |

## 📚 参照ドキュメント

- **実装仕様書**: `ai-vtuber-system-spec.md` を参照
- **Open-LLM-VTuber**: https://github.com/Open-LLM-VTuber/Open-LLM-VTuber
- **Style-Bert-VITS2**: https://github.com/litagin02/Style-Bert-VITS2

---

## 📊 実装進捗 (2026-01-24)

### Phase 1: 基盤構築 ✅ 完了

- [x] ディレクトリ構造作成
- [x] Docker Compose設定（Redis, vLLM, TTS, Orchestrator）
- [x] NVIDIA Container Toolkit設定
- [x] vLLM + Qwen 2.5 14B-AWQ 起動確認（VRAM 16.7GB/24GB）
- [x] TTS基盤（Style-Bert-VITS2ダミーモード）
- [x] Orchestrator基盤（FastAPI）
- [x] 各種設定ファイル（.env, ng_words.txt, scripts/）

### Phase 2: コア機能実装 ✅ 完了

- [x] YouTube Chat取得強化（エラーハンドリング、再接続ロジック）
- [x] Twitch対応スケルトン作成
- [x] MockChatFetcher作成（テスト用）
- [x] main.py統合（モックモード対応）
- [ ] 実際のYouTube Live配信でのテスト

### Phase 3: 話題・雑談システム ✅ 完了

- [x] Google News RSS取得
- [x] はてなブックマーク取得
- [x] 話題選択ロジック（カテゴリローテーション、重複回避）

### Phase 4: 安定化・運用 ✅ 完了

- [x] Prometheusメトリクス統合（main.py）
  - COMMENTS_TOTAL, RESPONSES_TOTAL, TOPICS_TOTAL (Counter)
  - FILTERED_TOTAL (Counter with reason label)
  - SPEAKING_GAUGE, IDLE_TIME_GAUGE (Gauge)
  - RESPONSE_LATENCY, TTS_LATENCY (Histogram)
  - /metrics エンドポイント追加
- [x] Grafana ダッシュボード設定
  - Prometheus datasource自動設定
  - AI VTuberダッシュボード (ai-vtuber.json)
  - コメント数、応答数、レイテンシグラフ等
- [x] Watchdog強化（scripts/watchdog.py）
  - Slack/Discord通知対応
  - GPU VRAM監視
  - サービス別再起動
  - 復旧検知・通知
- [x] VTube Studio連携
  - 感情に応じた表情変更（joy, sad, angry, surprise, neutral）
  - リアルタイムリップシンク（音量RMS解析）
  - 自動再接続サポート
  - VTS_ENABLED=true で有効化

---

## 🔧 現在の起動コマンド

```bash
# 全サービス起動
cd ~/workspace/ai-vtuber
docker compose up -d

# ステータス確認
docker compose ps

# ログ確認
docker compose logs -f orchestrator

# テストコメント送信
curl -X POST 'http://localhost:8080/test/comment?author=TestUser&message=Hello'
```

## 📝 技術的メモ

### LLMモデル変更履歴
- 当初: Qwen 2.5 14B (float16) → VRAM 28GB必要で失敗
- 現在: **Qwen 2.5 14B-AWQ** (4bit量子化) → VRAM 9.4GB、正常動作

### VRAM実測値
- vLLM (AWQ): ~9.4GB
- KV Cache: ~7GB
- 合計: ~16.7GB / 24GB（余裕7GB）

---

**このファイルをプロジェクトルートに配置することで、Claude Codeがプロジェクトの文脈を理解した上で実装を支援します。**

---

## 🚀 次回セッション用引き継ぎプロンプト

以下をコピペして次回セッションを開始:

```
AI VTuberプロジェクトの続きをやろう。

現在の状況:
- Phase 1〜4 + VTube Studio連携 完了
- 全コア機能実装済み（LLM応答、TTS、チャット取得、話題生成、監視、VTS表情/リップシンク）

次のステップ候補:
1. 実際のYouTube Live配信テスト
2. Style-Bert-VITS2の実モデル設定（現在はダミー）
3. VTube Studio側のホットキー設定ガイド作成
4. OBS連携・配信設定
5. その他改善

まずは現在のコードベースを確認して、何から始めるか提案して。
```
