"""
Amazon Bedrock provider implementation

Bedrock AI provider for AWS Bedrock runtime service
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
from flocks.utils.log import Log


log = Log.create(service="bedrock-provider")


class BedrockProvider(BaseProvider):
    """Amazon Bedrock provider"""
    
    def __init__(self):
        super().__init__(provider_id="amazon-bedrock", name="Amazon Bedrock")
        self._region = os.getenv("AWS_REGION", "us-east-1")
        self._client = None
    
    def _get_client(self):
        """Get or create Bedrock client"""
        if self._client is None:
            try:
                import boto3
                
                # Get region from config or environment
                region = self._region
                if self._config and self._config.custom_settings.get("region"):
                    region = self._config.custom_settings["region"]
                
                self._client = boto3.client(
                    "bedrock-runtime",
                    region_name=region,
                )
            except ImportError:
                raise ImportError("boto3 package not installed. Install with: pip install boto3")
        return self._client
    
    def _get_region_prefix(self, model_id: str) -> str:
        """Get cross-region inference prefix if needed"""
        region = self._region
        if self._config and self._config.custom_settings.get("region"):
            region = self._config.custom_settings["region"]
        
        region_prefix = region.split("-")[0]
        
        # US regions
        if region_prefix == "us":
            requires_prefix = any(m in model_id for m in [
                "nova-micro", "nova-lite", "nova-pro", "claude", "deepseek"
            ])
            if requires_prefix and not region.startswith("us-gov"):
                return f"{region_prefix}."
        
        # EU regions
        elif region_prefix == "eu":
            requires_prefix = any(m in model_id for m in [
                "claude", "nova-lite", "nova-micro", "llama3"
            ])
            if requires_prefix:
                return f"{region_prefix}."
        
        return ""
    
    def get_models(self) -> List[ModelInfo]:
        """Get list of Bedrock models"""
        return [
            ModelInfo(
                id="anthropic.claude-3-5-sonnet-20241022-v2:0",
                name="Claude 3.5 Sonnet v2 (Bedrock)",
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
                id="anthropic.claude-3-5-haiku-20241022-v1:0",
                name="Claude 3.5 Haiku (Bedrock)",
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
                id="amazon.nova-pro-v1:0",
                name="Amazon Nova Pro",
                provider_id=self.id,
                capabilities=ModelCapabilities(
                    supports_streaming=True,
                    supports_tools=True,
                    supports_vision=True,
                    max_tokens=5120,
                    context_window=300000,
                ),
            ),
            ModelInfo(
                id="amazon.nova-lite-v1:0",
                name="Amazon Nova Lite",
                provider_id=self.id,
                capabilities=ModelCapabilities(
                    supports_streaming=True,
                    supports_tools=True,
                    supports_vision=True,
                    max_tokens=5120,
                    context_window=300000,
                ),
            ),
        ]
    
    async def chat(
        self,
        model_id: str,
        messages: List[ChatMessage],
        **kwargs
    ) -> ChatResponse:
        """Send chat completion request to Bedrock using Converse API"""
        import json
        
        client = self._get_client()
        
        # Add region prefix if needed
        prefix = self._get_region_prefix(model_id)
        full_model_id = f"{prefix}{model_id}" if prefix else model_id
        
        # Convert messages to Bedrock format
        bedrock_messages = []
        system_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_messages.append({"text": msg.content})
            else:
                bedrock_messages.append({
                    "role": msg.role,
                    "content": [{"text": msg.content}]
                })
        
        # Build request
        request_params = {
            "modelId": full_model_id,
            "messages": bedrock_messages,
        }
        
        if system_messages:
            request_params["system"] = system_messages
        
        # Build inference config
        inference_config = {
            "temperature": kwargs.get("temperature", 0.7),
        }
        if kwargs.get("max_tokens"):
            inference_config["maxTokens"] = kwargs["max_tokens"]
        
        # Add reasoning config for Anthropic models on Bedrock
        if kwargs.get("reasoningConfig"):
            reasoning_config = kwargs["reasoningConfig"]
            if "anthropic" in model_id:
                inference_config["reasoningConfig"] = reasoning_config
        
        if inference_config:
            request_params["inferenceConfig"] = inference_config
        
        # Make request
        response = client.converse(**request_params)
        
        # Parse response
        content = ""
        if response.get("output", {}).get("message", {}).get("content"):
            content = response["output"]["message"]["content"][0].get("text", "")
        
        usage = response.get("usage", {})
        
        return ChatResponse(
            id=response.get("ResponseMetadata", {}).get("RequestId", ""),
            model=full_model_id,
            content=content,
            finish_reason=response.get("stopReason", "end_turn"),
            usage={
                "prompt_tokens": usage.get("inputTokens", 0),
                "completion_tokens": usage.get("outputTokens", 0),
                "total_tokens": usage.get("inputTokens", 0) + usage.get("outputTokens", 0),
            }
        )
    
    async def chat_stream(
        self,
        model_id: str,
        messages: List[ChatMessage],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """Send streaming chat completion request to Bedrock"""
        import json
        
        client = self._get_client()
        
        # Add region prefix if needed
        prefix = self._get_region_prefix(model_id)
        full_model_id = f"{prefix}{model_id}" if prefix else model_id
        
        # Convert messages to Bedrock format
        bedrock_messages = []
        system_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_messages.append({"text": msg.content})
            else:
                bedrock_messages.append({
                    "role": msg.role,
                    "content": [{"text": msg.content}]
                })
        
        # Build request
        request_params = {
            "modelId": full_model_id,
            "messages": bedrock_messages,
        }
        
        if system_messages:
            request_params["system"] = system_messages
        
        # Build inference config
        inference_config = {
            "temperature": kwargs.get("temperature", 0.7),
        }
        if kwargs.get("max_tokens"):
            inference_config["maxTokens"] = kwargs["max_tokens"]
        
        # Add reasoning config for Anthropic models on Bedrock
        if kwargs.get("reasoningConfig"):
            reasoning_config = kwargs["reasoningConfig"]
            if "anthropic" in model_id:
                inference_config["reasoningConfig"] = reasoning_config
        
        if inference_config:
            request_params["inferenceConfig"] = inference_config
        
        # Make streaming request
        response = client.converse_stream(**request_params)
        
        # Process stream
        for event in response.get("stream", []):
            if "contentBlockDelta" in event:
                delta = event["contentBlockDelta"].get("delta", {})
                text = delta.get("text", "")
                if text:
                    yield StreamChunk(delta=text, finish_reason=None)
            elif "messageStop" in event:
                yield StreamChunk(
                    delta="",
                    finish_reason=event["messageStop"].get("stopReason", "end_turn")
                )
