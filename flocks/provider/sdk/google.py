"""
Google (Gemini) provider implementation
"""

from typing import List, AsyncIterator, Optional, Dict, Any
import os

from flocks.provider.provider import (
    BaseProvider,
    ModelInfo,
    ModelCapabilities,
    ChatMessage,
    ChatResponse,
    StreamChunk,
)


class GoogleProvider(BaseProvider):
    """Google (Gemini) provider"""

    CATALOG_ID = "google"

    def __init__(self):
        super().__init__(provider_id="google", name="Google")
        self._api_key = os.getenv("GOOGLE_API_KEY")
        self._client = None
    
    def is_configured(self) -> bool:
        """Check if provider is configured"""
        api_key = self._config.api_key if self._config else self._api_key
        return bool(api_key)

    def get_meta(self):
        from flocks.provider.model_catalog import get_provider_meta
        return get_provider_meta("google") or super().get_meta()

    def _get_client(self):
        """Get or create Google Generative AI client"""
        if self._client is None:
            try:
                from google import genai
                api_key = self._config.api_key if self._config else self._api_key
                if not api_key:
                    raise ValueError("Google API key not configured")
                self._client = genai.Client(api_key=api_key)
            except ImportError:
                raise ImportError("google-genai package not installed. Install with: pip install google-genai")
        return self._client
    
    def get_models(self) -> List[ModelInfo]:
        """Return models from flocks.json (_config_models) only.

        catalog.json is not consulted at runtime; it is only used when
        credentials are first saved to pre-populate flocks.json.
        """
        return list(getattr(self, "_config_models", []))
    
    def _convert_messages(self, messages: List[ChatMessage]) -> tuple[Optional[str], List[Dict[str, str]]]:
        """Convert messages to Gemini format"""
        system_msg = None
        gemini_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            elif msg.role == "user":
                gemini_messages.append({"role": "user", "parts": [{"text": msg.content}]})
            elif msg.role == "assistant":
                gemini_messages.append({"role": "model", "parts": [{"text": msg.content}]})
        
        return system_msg, gemini_messages
    
    async def chat(
        self,
        model_id: str,
        messages: List[ChatMessage],
        **kwargs
    ) -> ChatResponse:
        """Send chat completion request to Google"""
        client = self._get_client()
        
        system_msg, gemini_messages = self._convert_messages(messages)
        
        # Build generation config
        config = {
            "temperature": kwargs.get("temperature", 0.7),
            "max_output_tokens": kwargs.get("max_tokens", 2048),
        }
        
        # Add thinking config if provided
        if kwargs.get("thinkingConfig"):
            config["thinking_config"] = kwargs["thinkingConfig"]
        
        # Add system instruction if provided
        if system_msg:
            config["system_instruction"] = system_msg
        
        # Generate response using new API
        response = await client.aio.models.generate_content(
            model=model_id,
            contents=gemini_messages,
            config=config
        )
        
        return ChatResponse(
            id="gemini-" + model_id,
            model=model_id,
            content=response.text,
            finish_reason="stop",
            usage={
                "prompt_tokens": response.usage_metadata.prompt_token_count if response.usage_metadata else 0,
                "completion_tokens": response.usage_metadata.candidates_token_count if response.usage_metadata else 0,
                "total_tokens": response.usage_metadata.total_token_count if response.usage_metadata else 0,
            }
        )
    
    async def chat_stream(
        self,
        model_id: str,
        messages: List[ChatMessage],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """Send streaming chat completion request to Google"""
        client = self._get_client()
        
        system_msg, gemini_messages = self._convert_messages(messages)
        
        # Build generation config
        config = {
            "temperature": kwargs.get("temperature", 0.7),
            "max_output_tokens": kwargs.get("max_tokens", 2048),
        }
        
        # Add thinking config if provided
        if kwargs.get("thinkingConfig"):
            config["thinking_config"] = kwargs["thinkingConfig"]
        
        # Add system instruction if provided
        if system_msg:
            config["system_instruction"] = system_msg
        
        # Stream response using new API
        response = await client.aio.models.generate_content_stream(
            model=model_id,
            contents=gemini_messages,
            config=config
        )
        
        async for chunk in response:
            if chunk.text:
                yield StreamChunk(delta=chunk.text, finish_reason=None)
        
        yield StreamChunk(delta="", finish_reason="stop")
    
    # Embeddings support (added for memory system)
    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        **kwargs
    ) -> List[float]:
        """Generate embedding using Gemini API"""
        client = self._get_client()
        model = model or "models/text-embedding-004"
        
        try:
            result = await client.aio.models.embed_content(
                model=model,
                content=text,
                **kwargs
            )
            return result.embeddings[0].values
        except Exception as e:
            self.log.error("google.embed.failed", {"error": str(e), "model": model})
            raise
    
    async def embed_batch(
        self,
        texts: List[str],
        model: Optional[str] = None,
        batch_size: Optional[int] = 100,
        **kwargs
    ) -> List[List[float]]:
        """Batch embeddings with Gemini API"""
        client = self._get_client()
        model = model or "models/text-embedding-004"
        
        all_embeddings = []
        
        try:
            # Process in batches
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                result = await client.aio.models.embed_content(
                    model=model,
                    content=batch,
                    **kwargs
                )
                # Extract embeddings from response
                for embedding in result.embeddings:
                    all_embeddings.append(embedding.values)
            
            return all_embeddings
        except Exception as e:
            self.log.error("google.embed_batch.failed", {
                "error": str(e),
                "model": model,
                "batch_count": len(texts)
            })
            raise
    
    def get_embedding_models(self) -> List[str]:
        """Get Gemini embedding models"""
        return [
            "models/text-embedding-004",
            "models/embedding-001",
        ]
