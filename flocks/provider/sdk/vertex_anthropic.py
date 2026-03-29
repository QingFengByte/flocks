"""
Google Vertex Anthropic Provider SDK

Provides integration with Anthropic models through Google Cloud Vertex AI.
This allows using Claude models with Google Cloud authentication and billing.

Ported from original @ai-sdk/google-vertex/anthropic implementation.
"""

import os
from typing import Optional, Dict, Any, List, AsyncIterator

from flocks.provider.provider import (
    BaseProvider,
    ModelInfo,
    ModelCapabilities,
    ChatMessage,
    ChatResponse,
    StreamChunk,
)
from flocks.utils.log import Log

log = Log.create(service="provider.vertex-anthropic")


class VertexAnthropicProvider(BaseProvider):
    """
    Google Vertex Anthropic Provider
    
    Integrates with Anthropic's Claude models through Google Cloud Vertex AI:
    - Uses Google Cloud authentication (Application Default Credentials)
    - Billing through Google Cloud
    - Access to Claude models in Google's infrastructure
    
    Environment Variables:
        GOOGLE_CLOUD_PROJECT: GCP project ID (also GCP_PROJECT, GCLOUD_PROJECT)
        GOOGLE_CLOUD_LOCATION: Region (default: global)
        GOOGLE_APPLICATION_CREDENTIALS: Path to service account JSON
    """
    
    # Claude models available through Vertex AI
    DEFAULT_MODELS = [
        {
            "id": "claude-3-5-sonnet@20241022",
            "name": "Claude 3.5 Sonnet (Vertex)",
            "context_window": 200000,
            "max_tokens": 8192,
            "supports_tools": True,
            "supports_vision": True,
            "supports_streaming": True,
        },
        {
            "id": "claude-3-5-haiku@20241022",
            "name": "Claude 3.5 Haiku (Vertex)",
            "context_window": 200000,
            "max_tokens": 8192,
            "supports_tools": True,
            "supports_vision": True,
            "supports_streaming": True,
        },
        {
            "id": "claude-3-opus@20240229",
            "name": "Claude 3 Opus (Vertex)",
            "context_window": 200000,
            "max_tokens": 4096,
            "supports_tools": True,
            "supports_vision": True,
            "supports_streaming": True,
        },
        {
            "id": "claude-3-sonnet@20240229",
            "name": "Claude 3 Sonnet (Vertex)",
            "context_window": 200000,
            "max_tokens": 4096,
            "supports_tools": True,
            "supports_vision": True,
            "supports_streaming": True,
        },
        {
            "id": "claude-3-haiku@20240307",
            "name": "Claude 3 Haiku (Vertex)",
            "context_window": 200000,
            "max_tokens": 4096,
            "supports_tools": True,
            "supports_vision": True,
            "supports_streaming": True,
        },
    ]
    
    def __init__(
        self,
        project: Optional[str] = None,
        location: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize Google Vertex Anthropic provider.
        
        Args:
            project: GCP project ID (or from GOOGLE_CLOUD_PROJECT env)
            location: GCP region (default: global)
            **kwargs: Additional configuration
        """
        super().__init__(provider_id="google-vertex-anthropic", name="Google Vertex Anthropic")
        
        # Get project from environment if not provided
        self.project = (
            project or
            os.environ.get("GOOGLE_CLOUD_PROJECT") or
            os.environ.get("GCP_PROJECT") or
            os.environ.get("GCLOUD_PROJECT") or
            ""
        )
        
        # Get location (Vertex Anthropic typically uses 'global')
        self.location = (
            location or
            os.environ.get("GOOGLE_CLOUD_LOCATION") or
            os.environ.get("VERTEX_LOCATION") or
            "global"
        )
        
        self._client = None
        self._models_config = self.DEFAULT_MODELS.copy()
        
        log.info("vertex_anthropic.initialized", {
            "project": self.project,
            "location": self.location,
        })
    
    async def _get_access_token(self) -> str:
        """
        Get access token using Google Cloud Application Default Credentials.
        
        Returns:
            Access token string
        """
        try:
            # Try to use google-auth library for ADC
            import google.auth
            import google.auth.transport.requests
            
            credentials, project = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            
            # Refresh credentials if needed
            request = google.auth.transport.requests.Request()
            credentials.refresh(request)
            
            return credentials.token
            
        except ImportError:
            # Fallback: try to get token from gcloud CLI
            import subprocess
            result = subprocess.run(
                ["gcloud", "auth", "print-access-token"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
            raise ValueError(
                "Could not get Google Cloud credentials. "
                "Install google-auth: pip install google-auth "
                "or authenticate with: gcloud auth application-default login"
            )
    
    def _get_api_url(self, model_id: str) -> str:
        """
        Build the Vertex AI Anthropic API URL.
        
        Args:
            model_id: Model identifier
            
        Returns:
            API endpoint URL
        """
        # Vertex AI Anthropic uses a specific endpoint format
        return (
            f"https://{self.location}-aiplatform.googleapis.com/v1/"
            f"projects/{self.project}/locations/{self.location}/"
            f"publishers/anthropic/models/{model_id}"
        )
    
    def get_models(self) -> List[ModelInfo]:
        """Get available Vertex Anthropic models."""
        models = []
        for config in self._models_config:
            models.append(ModelInfo(
                id=config["id"],
                name=config["name"],
                provider_id=self.id,
                capabilities=ModelCapabilities(
                    supports_streaming=config.get("supports_streaming", True),
                    supports_tools=config.get("supports_tools", True),
                    supports_vision=config.get("supports_vision", True),
                    max_tokens=config.get("max_tokens", 4096),
                    context_window=config.get("context_window", 200000),
                ),
            ))
        return models
    
    async def chat(
        self,
        model_id: str,
        messages: List[ChatMessage],
        **kwargs
    ) -> ChatResponse:
        """
        Create a chat completion using Vertex Anthropic.
        
        Args:
            model_id: Model to use (e.g., claude-3-5-sonnet@20241022)
            messages: List of conversation messages
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            Chat completion response
        """
        if not self.project:
            raise ValueError(
                "Google Cloud project not configured. "
                "Set GOOGLE_CLOUD_PROJECT environment variable."
            )
        
        token = await self._get_access_token()
        
        # Convert messages to Anthropic format
        system_message = None
        anthropic_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                anthropic_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        # Build request payload (Anthropic format)
        payload = {
            "anthropic_version": "vertex-2023-10-16",
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
        }
        
        if system_message:
            payload["system"] = system_message
        
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        
        try:
            import httpx
            
            url = f"{self._get_api_url(model_id)}:rawPredict"
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=120.0,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract content from Anthropic response format
                    content = ""
                    if "content" in data and data["content"]:
                        for block in data["content"]:
                            if block.get("type") == "text":
                                content += block.get("text", "")
                    
                    return ChatResponse(
                        id=data.get("id", "vertex-anthropic-response"),
                        model=model_id,
                        content=content,
                        finish_reason=data.get("stop_reason", "end_turn"),
                        usage={
                            "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                            "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
                            "total_tokens": (
                                data.get("usage", {}).get("input_tokens", 0) +
                                data.get("usage", {}).get("output_tokens", 0)
                            ),
                        }
                    )
                else:
                    log.error("vertex_anthropic.chat.error", {
                        "status": response.status_code,
                        "body": response.text[:500],
                    })
                    raise Exception(f"Vertex Anthropic API error: {response.status_code}")
                    
        except Exception as e:
            log.error("vertex_anthropic.chat.error", {"error": str(e), "model": model_id})
            raise
    
    async def chat_stream(
        self,
        model_id: str,
        messages: List[ChatMessage],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        Create a streaming chat completion using Vertex Anthropic.
        
        Args:
            model_id: Model to use
            messages: List of conversation messages
            **kwargs: Additional parameters
            
        Yields:
            Streaming response chunks
        """
        if not self.project:
            raise ValueError(
                "Google Cloud project not configured. "
                "Set GOOGLE_CLOUD_PROJECT environment variable."
            )
        
        token = await self._get_access_token()
        
        # Convert messages to Anthropic format
        system_message = None
        anthropic_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                anthropic_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        # Build request payload with streaming
        payload = {
            "anthropic_version": "vertex-2023-10-16",
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "stream": True,
        }
        
        if system_message:
            payload["system"] = system_message
        
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]
        
        try:
            import httpx
            import json
            
            url = f"{self._get_api_url(model_id)}:streamRawPredict"
            
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=120.0,
                ) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            
                            try:
                                event = json.loads(data)
                                event_type = event.get("type", "")
                                
                                if event_type == "content_block_delta":
                                    delta = event.get("delta", {})
                                    if delta.get("type") == "text_delta":
                                        yield StreamChunk(
                                            delta=delta.get("text", ""),
                                            finish_reason=None,
                                        )
                                
                                elif event_type == "message_stop":
                                    yield StreamChunk(
                                        delta="",
                                        finish_reason="end_turn",
                                    )
                                    
                            except json.JSONDecodeError:
                                continue
                    
        except Exception as e:
            log.error("vertex_anthropic.stream.error", {"error": str(e), "model": model_id})
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Vertex Anthropic service health."""
        if not self.project:
            return {
                "healthy": False,
                "provider": self.id,
                "error": "Project not configured",
            }
        
        try:
            # Try to get access token as health check
            token = await self._get_access_token()
            
            return {
                "healthy": True,
                "provider": self.id,
                "project": self.project,
                "location": self.location,
                "has_token": bool(token),
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "provider": self.id,
                "error": str(e),
            }


# Provider factory function
def create_provider(**kwargs) -> VertexAnthropicProvider:
    """Create a Google Vertex Anthropic provider instance."""
    return VertexAnthropicProvider(**kwargs)
