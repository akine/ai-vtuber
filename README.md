# 🎭 AI VTuber — Fully-Local Autonomous Streaming System

> An autonomous AI VTuber that listens to live chat, decides what to say, speaks, and animates an avatar — running entirely on **local, open models**. No cloud LLM required.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-orchestrator-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Redis_Streams-bus-DC382D?style=for-the-badge&logo=redis&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker_Compose-deploy-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/LLM-Qwen_2.5_14B--AWQ_(local)-6f42c1?style=for-the-badge" />
</p>

---

## ✨ What it does

A self-hosted pipeline that turns a **local LLM + local TTS + VTube Studio** into a 24/7 autonomous VTuber:

- 👂 **Listens** to live chat from YouTube (`pytchat`) and Twitch (`TwitchIO`), plus topic feeds (Google News, Hatena Bookmark)
- 🧠 **Decides** which comments to answer with a *priority scorer*, a *safety / NG-word filter*, and an *emotion analyzer*
- 💾 **Remembers** context across the stream with a *memory manager*
- 🗣️ **Speaks** through a local TTS server (design target: <500 ms generation latency)
- 🎭 **Moves** the avatar via a VTube Studio (VTS) controller
- 🖥️ **Runs locally** on a single RTX 4090 (24 GB) using a quantized open model (Qwen 2.5 14B-AWQ) — fully offline, no cloud inference

---

## 🏗️ Architecture

```
  YouTube / Twitch chat        Topic sources
  (pytchat / TwitchIO)      (Google News / Hatena)
            │                        │
            └───────────┬────────────┘
                        ▼
              ┌── Redis Streams ──┐
              │ comment · topic · │
              │     response      │
              └─────────┬─────────┘
                        ▼
            Orchestrator (FastAPI)
   ┌──────────┬──────────┬──────────┬──────────┐
   │ Priority │  Safety   │ Emotion  │  Memory  │
   │  Scorer  │  Filter   │ Analyzer │ Manager  │
   └──────────┴──────────┴──────────┴──────────┘
                        ▼
        Local LLM → Local TTS → VTube Studio avatar
```

---

## 🚀 Quick start

```bash
git clone https://github.com/akine/ai-vtuber.git
cd ai-vtuber
cp .env.example .env          # set your API keys / channel IDs
docker compose up -d          # orchestrator + tts + redis + monitoring
```

- Full implementation spec: [`ai-vtuber-system-spec.md`](./ai-vtuber-system-spec.md)
- Step-by-step guide: [`ai-vtuber-quickstart.md`](./ai-vtuber-quickstart.md)

---

## 📦 Tech stack

Python · FastAPI · Redis Streams · Docker Compose · local LLM (Qwen 2.5 14B-AWQ) · local TTS · VTube Studio API · Prometheus + Grafana

## 📊 Monitoring

Prometheus metrics and a ready-made Grafana dashboard ship in [`monitoring/`](./monitoring) for live latency / uptime / VRAM tracking during 24h streams.

## 🛡️ Safety

Every generated line passes a safety filter and an NG-word check ([`config/ng_words.txt`](./config/ng_words.txt)) **before** it is ever spoken.

---

## 📝 Status

Personal / experimental project exploring **fully-local, open-model autonomous streaming** — built and maintained in the open. Ideas and contributions welcome.
