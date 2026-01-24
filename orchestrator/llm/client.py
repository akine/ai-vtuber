from openai import AsyncOpenAI
from typing import AsyncIterator


class LLMClient:
    def __init__(self, base_url: str = "http://localhost:8000/v1"):
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key="dummy"  # vLLMは認証不要
        )
        self.model = "Qwen/Qwen2.5-14B-Instruct-AWQ"

    async def generate_response(
        self,
        user_message: str,
        system_prompt: str,
        chat_history: list[dict] | None = None
    ) -> AsyncIterator[str]:
        """ストリーミングで応答を生成"""

        messages = [{"role": "system", "content": system_prompt}]

        if chat_history:
            messages.extend(chat_history[-10:])  # 直近10件のみ

        messages.append({"role": "user", "content": user_message})

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=256,
            temperature=0.8,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
