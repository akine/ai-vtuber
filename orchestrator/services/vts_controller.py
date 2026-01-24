"""VTube Studio連携コントローラー"""
import asyncio
from typing import Optional

import pyvts


class VTubeStudioController:
    """VTube Studioとの連携を管理"""

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
        self._reconnect_task: Optional[asyncio.Task] = None
        self._current_emotion = "neutral"

        # 感情からホットキー名へのマッピング（VTube Studio側で設定が必要）
        self.emotion_hotkeys = {
            "joy": "expression_happy",
            "happy": "expression_happy",
            "sad": "expression_sad",
            "angry": "expression_angry",
            "surprise": "expression_surprise",
            "neutral": "expression_neutral",
        }

        # リップシンク用パラメータ名
        self.mouth_param = "ParamMouthOpenY"

    async def connect(self) -> bool:
        """VTube Studioに接続"""
        try:
            self.vts = pyvts.vts(plugin_info=self.plugin_info)
            await self.vts.connect()

            # 認証トークン取得（初回のみユーザー確認が必要）
            await self.vts.request_authenticate_token()
            await self.vts.request_authenticate()

            self.connected = True
            print(f"VTube Studio connected! ({self.host}:{self.port})")
            return True

        except Exception as e:
            print(f"VTube Studio connection failed: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        """接続を切断"""
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None

        if self.vts:
            try:
                await self.vts.close()
            except Exception:
                pass
        self.connected = False
        print("VTube Studio disconnected")

    async def ensure_connected(self) -> bool:
        """接続を確認し、必要なら再接続"""
        if self.connected:
            return True

        print("VTube Studio reconnecting...")
        return await self.connect()

    async def set_expression(self, emotion: str):
        """感情に応じた表情を設定"""
        if not await self.ensure_connected():
            return

        # 同じ感情なら変更しない
        if emotion == self._current_emotion:
            return

        hotkey = self.emotion_hotkeys.get(emotion.lower(), "expression_neutral")

        try:
            await self.vts.request(
                self.vts.vts_request.requestTriggerHotKey(hotkey)
            )
            self._current_emotion = emotion
            print(f"Expression changed to: {emotion}")
        except Exception as e:
            print(f"Expression change failed: {e}")
            self.connected = False

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
        if not self.connected:
            return

        # 音量を口の開きに変換（調整可能）
        mouth_open = min(volume * 1.5, 1.0)
        await self.set_parameter(self.mouth_param, mouth_open)

    async def reset_lip_sync(self):
        """リップシンクをリセット（口を閉じる）"""
        await self.set_parameter(self.mouth_param, 0.0)

    def is_connected(self) -> bool:
        return self.connected
