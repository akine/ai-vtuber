import asyncio
from typing import Optional

import pyvts


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
            print("VTube Studio connected!")
        except Exception as e:
            print(f"VTube Studio connection failed: {e}")
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
