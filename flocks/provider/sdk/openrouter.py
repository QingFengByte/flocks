"""
OpenRouter provider implementation

Based on @openrouter/ai-sdk-provider from Flocks's bundled providers
Multi-model routing provider
"""

from typing import List, AsyncIterator, Optional
import os

from flocks.provider.provider import (
    BaseProvider,
    ModelInfo,
    ModelCapabilities,
    ChatMessage,
    ChatResponse,
    StreamChunk,
)


class OpenRouterProvider(BaseProvider):
    """OpenRouter provider - multi-model routing"""
    
    def __init__(self):
        super().__init__(provider_id="openrouter", name="OpenRouter")
        self._api_key = os.getenv("OPENROUTER_API_KEY")
        self._base_url = "https://openrouter.ai/api/v1"
        self._client = None
    
    def _get_client(self):
        """Get or create OpenRouter client (OpenAI compatible)"""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                api_key = self._config.api_key if self._config else self._api_key
                if not api_key:
                    raise ValueError("OpenRouter API key not configured. Set OPENROUTER_API_KEY environment variable.")
                
                self._client = AsyncOpenAI(
                    api_key=api_key,
                    base_url=self._base_url,
                    default_headers={
                        "HTTP-Referer": "https://opencode.ai/",
                        "X-Title": "opencode",
                    }
                )
            except ImportError:
                raise ImportError("openai package not installed. Install with: pip install openai")
        return self._client
    
    def get_models(self) -> List[ModelInfo]:
        """Get list of popular OpenRouter models"""
        return [
            ModelInfo(
                id="anthropic/claude-3.5-sonnet",
                name="Claude 3.5 Sonnet",
                provider_id=self.id,
                capabilities=ModelCapabilities(
                    supports_streaming=True,
                    supports_tools=True,
                    supports_vision=True,
                    max_tokens=8192,
                    context_window=200000,
                ),
            ),
            ModelInfo(
                id="openai/gpt-4-turbo",
                name="GPT-4 Turbo",
                provider_id=self.id,
                capabilities=ModelCapabilities(
                    supports_streaming=True,
                    supports_tools=True,
                    supports_vision=True,
                    max_tokens=4096,
                    context_window=128000,
                ),
            ),
            ModelInfo(
                id="google/gemini-pro-1.5",
                name="Gemini Pro 1.5",
                provider_id=self.id,
                capabilities=ModelCapabilities(
                    supports_streaming=True,
                    supports_tools=True,
                    supports_vision=True,
                    max_tokens=8192,
                    context_window=1000000,
                ),
            ),
            ModelInfo(
                id="meta-llama/llama-3.1-70b-instruct",
                name="Llama 3.1 70B",
                provider_id=self.id,
                capabilities=ModelCapabilities(
                    supports_streaming=True,
                    supports_tools=True,
                    supports_vision=False,
                    max_tokens=4096,
                    context_window=131072,
                ),
            ),
            ModelInfo(
                id="mistralai/mistral-large",
                name="Mistral Large",
                provider_id=self.id,
                capabilities=ModelCapabilities(
                    supports_streaming=True,
                    supports_tools=True,
                    supports_vision=False,
                    max_tokens=8192,
                    context_window=128000,
                ),
            ),
        ]
    
    async def chat(
        self,
        model_id: str,
        messages: List[ChatMessage],
        **kwargs
    ) -> ChatResponse:
        """Send chat completion request to OpenRouter"""
        client = self._get_client()
        
        formatted_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        response = await client.chat.completions.create(
            model=model_id,
            messages=formatted_messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens"),
        )
        
        choice = response.choices[0]
        return ChatResponse(
            id=response.id,
            model=response.model,
            content=choice.message.content or "",
            finish_reason=choice.finish_reason,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }
        )
    
    async def chat_stream(
        self,
        model_id: str,
        messages: List[ChatMessage],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """Send streaming chat completion request to OpenRouter"""
        client = self._get_client()
        
        formatted_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        stream = await client.chat.completions.create(
            model=model_id,
            messages=formatted_messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens"),
            stream=True,
        )
        
        async for chunk in stream:
            if chunk.choices:
                choice = chunk.choices[0]
                if choice.delta.content:
                    yield StreamChunk(
                        delta=choice.delta.content,
                        finish_reason=choice.finish_reason,
                    )
