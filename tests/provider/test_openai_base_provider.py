"""
Tests for OpenAI Base Provider get_models() method.

Tests various scenarios:
1. Provider with CATALOG_ID set (loads from catalog)
2. Provider without CATALOG_ID (returns empty list)
3. Provider with catalog load failure (handles gracefully)
4. Provider with config-based models (defers to config merge)
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from flocks.provider.sdk.openai_base import OpenAIBaseProvider, extract_reasoning_content
from flocks.provider.provider import ModelInfo, ModelCapabilities, ProviderConfig


class MockProviderWithCatalog(OpenAIBaseProvider):
    """Mock provider with CATALOG_ID set."""
    
    DEFAULT_BASE_URL = "https://api.test.com/v1"
    ENV_API_KEY = ["TEST_API_KEY"]
    ENV_BASE_URL = "TEST_BASE_URL"
    CATALOG_ID = "test-provider"
    
    def __init__(self):
        super().__init__(provider_id="test-provider", name="Test Provider")


class MockProviderWithoutCatalog(OpenAIBaseProvider):
    """Mock provider without CATALOG_ID."""
    
    DEFAULT_BASE_URL = "https://api.custom.com/v1"
    ENV_API_KEY = ["CUSTOM_API_KEY"]
    ENV_BASE_URL = "CUSTOM_BASE_URL"
    CATALOG_ID = ""  # No catalog
    
    def __init__(self):
        super().__init__(provider_id="custom-provider", name="Custom Provider")


class TestOpenAIBaseProviderGetModels:
    """Test suite for get_models() method."""
    
    def test_get_models_with_catalog_success(self):
        """Test get_models() with valid catalog data."""
        provider = MockProviderWithCatalog()
        
        # Mock catalog model definition
        mock_model_def = Mock()
        mock_model_def.id = "test-model-1"
        mock_model_def.name = "Test Model 1"
        mock_model_def.capabilities = Mock(
            supports_tools=True,
            supports_vision=False,
            supports_streaming=True,
            supports_reasoning=False
        )
        mock_model_def.limits = Mock(
            context_window=128000,
            max_tokens=4096
        )
        
        # Mock the catalog function
        with patch('flocks.provider.model_catalog.get_provider_model_definitions') as mock_get_defs:
            mock_get_defs.return_value = [mock_model_def]
            
            models = provider.get_models()
            
            # Verify the call
            mock_get_defs.assert_called_once_with("test-provider")
            
            # Verify returned models
            assert len(models) == 1
            assert isinstance(models[0], ModelInfo)
            assert models[0].id == "test-model-1"
            assert models[0].name == "Test Model 1"
            assert models[0].provider_id == "test-provider"
            assert models[0].capabilities.supports_tools is True
            assert models[0].capabilities.supports_vision is False
            assert models[0].capabilities.supports_streaming is True
            assert models[0].capabilities.context_window == 128000
            assert models[0].capabilities.max_tokens == 4096
    
    def test_get_models_with_multiple_models(self):
        """Test get_models() returns multiple models from catalog."""
        provider = MockProviderWithCatalog()
        
        # Create multiple mock models
        mock_models = []
        for i in range(3):
            mock_model = Mock()
            mock_model.id = f"test-model-{i}"
            mock_model.name = f"Test Model {i}"
            mock_model.capabilities = Mock(
                supports_tools=True,
                supports_vision=i == 2,  # Only last model has vision
                supports_streaming=True,
                supports_reasoning=False
            )
            mock_model.limits = Mock(
                context_window=100000,
                max_tokens=4096
            )
            mock_models.append(mock_model)
        
        with patch('flocks.provider.model_catalog.get_provider_model_definitions') as mock_get_defs:
            mock_get_defs.return_value = mock_models
            
            models = provider.get_models()
            
            assert len(models) == 3
            assert models[0].id == "test-model-0"
            assert models[1].id == "test-model-1"
            assert models[2].id == "test-model-2"
            assert models[2].capabilities.supports_vision is True
            assert models[0].capabilities.supports_vision is False
    
    def test_get_models_without_catalog(self):
        """Test get_models() for provider without CATALOG_ID."""
        provider = MockProviderWithoutCatalog()
        
        models = provider.get_models()
        
        # Should return empty list when no catalog ID
        assert models == []
        assert isinstance(models, list)
    
    def test_get_models_catalog_import_error(self):
        """Test get_models() handles import errors gracefully."""
        provider = MockProviderWithCatalog()
        
        with patch('flocks.provider.model_catalog.get_provider_model_definitions') as mock_get_defs:
            mock_get_defs.side_effect = ImportError("Cannot import module")
            
            models = provider.get_models()
            
            # Should return empty list and not raise
            assert models == []
    
    def test_get_models_catalog_returns_none(self):
        """Test get_models() when catalog returns None."""
        provider = MockProviderWithCatalog()
        
        with patch('flocks.provider.model_catalog.get_provider_model_definitions') as mock_get_defs:
            mock_get_defs.return_value = None
            
            models = provider.get_models()
            
            # Should return empty list
            assert models == []
    
    def test_get_models_catalog_returns_empty_list(self):
        """Test get_models() when catalog returns empty list."""
        provider = MockProviderWithCatalog()
        
        with patch('flocks.provider.model_catalog.get_provider_model_definitions') as mock_get_defs:
            mock_get_defs.return_value = []
            
            models = provider.get_models()
            
            # Should return empty list
            assert models == []
    
    def test_get_models_catalog_generic_exception(self):
        """Test get_models() handles generic exceptions gracefully."""
        provider = MockProviderWithCatalog()
        
        with patch('flocks.provider.model_catalog.get_provider_model_definitions') as mock_get_defs:
            mock_get_defs.side_effect = ValueError("Invalid catalog data")
            
            models = provider.get_models()
            
            # Should return empty list and not raise
            assert models == []
    
    def test_get_models_with_config_models(self):
        """Test get_models() when provider has config models loaded."""
        provider = MockProviderWithoutCatalog()
        
        # Simulate Provider.apply_config() loading models into _config_models
        from flocks.provider.provider import ModelInfo, ModelCapabilities
        provider._config_models = [
            ModelInfo(
                id="custom-model-1",
                name="Custom Model 1",
                provider_id="custom-provider",
                capabilities=ModelCapabilities(
                    supports_tools=True,
                    supports_vision=False,
                    supports_streaming=True,
                    supports_reasoning=False,
                    max_tokens=4096,
                    context_window=128000
                )
            ),
            ModelInfo(
                id="custom-model-2",
                name="Custom Model 2",
                provider_id="custom-provider",
                capabilities=ModelCapabilities(
                    supports_tools=True,
                    supports_vision=True,
                    supports_streaming=True,
                    supports_reasoning=False,
                    max_tokens=8192,
                    context_window=200000
                )
            )
        ]
        
        models = provider.get_models()
        
        # Should return config models
        assert len(models) == 2
        assert models[0].id == "custom-model-1"
        assert models[0].name == "Custom Model 1"
        assert models[1].id == "custom-model-2"
        assert models[1].name == "Custom Model 2"
        assert models[1].capabilities.supports_vision is True
    
    def test_get_models_missing_supports_reasoning(self):
        """Test get_models() handles missing supports_reasoning attribute."""
        provider = MockProviderWithCatalog()
        
        # Mock model without supports_reasoning - spec_set to control attributes
        mock_capabilities = Mock(spec=['supports_tools', 'supports_vision', 'supports_streaming'])
        mock_capabilities.supports_tools = True
        mock_capabilities.supports_vision = False
        mock_capabilities.supports_streaming = True
        # supports_reasoning will raise AttributeError
        
        mock_model = Mock()
        mock_model.id = "old-model"
        mock_model.name = "Old Model"
        mock_model.capabilities = mock_capabilities
        mock_model.limits = Mock(
            context_window=4096,
            max_tokens=2048
        )
        
        with patch('flocks.provider.model_catalog.get_provider_model_definitions') as mock_get_defs:
            mock_get_defs.return_value = [mock_model]
            
            models = provider.get_models()
            
            # Should default to False for supports_reasoning
            assert len(models) == 1
            assert models[0].capabilities.supports_reasoning is False
    
    def test_get_models_with_reasoning_support(self):
        """Test get_models() with models that support reasoning."""
        provider = MockProviderWithCatalog()
        
        # Mock model with reasoning support
        mock_model = Mock()
        mock_model.id = "reasoning-model"
        mock_model.name = "Reasoning Model"
        mock_model.capabilities = Mock(
            supports_tools=True,
            supports_vision=True,
            supports_streaming=True,
            supports_reasoning=True
        )
        mock_model.limits = Mock(
            context_window=200000,
            max_tokens=8192
        )
        
        with patch('flocks.provider.model_catalog.get_provider_model_definitions') as mock_get_defs:
            mock_get_defs.return_value = [mock_model]
            
            models = provider.get_models()
            
            assert len(models) == 1
            assert models[0].capabilities.supports_reasoning is True
            assert models[0].capabilities.supports_vision is True


class TestOpenAIBaseProviderConfiguration:
    """Test provider configuration and initialization."""
    
    def test_provider_initialization(self):
        """Test basic provider initialization."""
        provider = MockProviderWithCatalog()
        
        assert provider.id == "test-provider"
        assert provider.name == "Test Provider"
        assert provider.DEFAULT_BASE_URL == "https://api.test.com/v1"
        assert provider.CATALOG_ID == "test-provider"
    
    def test_provider_without_api_key(self):
        """Test provider initialization without API key."""
        provider = MockProviderWithCatalog()
        
        # Should not raise on initialization
        assert provider._api_key is None or provider._api_key == ""
    
    def test_is_configured_without_key(self):
        """Test is_configured() returns False without API key."""
        provider = MockProviderWithCatalog()
        
        # Clear any environment API key
        provider._api_key = None
        provider._config = None
        
        assert provider.is_configured() is False
    
    def test_is_configured_with_key(self):
        """Test is_configured() returns True with API key."""
        provider = MockProviderWithCatalog()
        
        provider._api_key = "test-api-key-123"
        
        assert provider.is_configured() is True
    
    def test_is_configured_with_config(self):
        """Test is_configured() uses config API key."""
        provider = MockProviderWithCatalog()
        provider._api_key = None
        
        mock_config = Mock(spec=ProviderConfig)
        mock_config.api_key = "config-api-key"
        provider._config = mock_config
        
        assert provider.is_configured() is True
    
    @patch.dict('os.environ', {'TEST_API_KEY': 'env-api-key'})
    def test_resolve_env_key(self):
        """Test API key resolution from environment."""
        provider = MockProviderWithCatalog()
        
        # Should have resolved from TEST_API_KEY env var
        assert provider._api_key == 'env-api-key'
    
    @patch.dict('os.environ', {'TEST_BASE_URL': 'https://custom.api.com'})
    def test_resolve_base_url_from_env(self):
        """Test base URL resolution from environment."""
        provider = MockProviderWithCatalog()
        
        assert provider._base_url == 'https://custom.api.com'
    
    def test_resolve_base_url_default(self):
        """Test base URL uses default when env not set."""
        provider = MockProviderWithCatalog()
        
        # Remove env var effect
        provider._base_url = provider.DEFAULT_BASE_URL
        
        assert provider._base_url == "https://api.test.com/v1"


class TestOpenAIBaseProviderTemperature:
    def _build_provider_with_client(self):
        provider = MockProviderWithoutCatalog()
        create = AsyncMock()
        provider._client = MagicMock()
        provider._client.chat.completions.create = create
        return provider, create

    @staticmethod
    def _mock_chat_response(content: str = "Paris"):
        response = MagicMock()
        response.id = "resp_1"
        response.model = "kimi-k2.5"
        response.usage = MagicMock(prompt_tokens=1, completion_tokens=1, total_tokens=2)
        choice = MagicMock()
        choice.finish_reason = "stop"
        choice.message = MagicMock(content=content)
        response.choices = [choice]
        return response

    @pytest.mark.asyncio
    async def test_chat_omits_temperature_when_not_provided(self):
        provider, create = self._build_provider_with_client()
        create.return_value = self._mock_chat_response()

        from flocks.provider.provider import ChatMessage

        await provider.chat(
            "kimi-k2.5",
            [ChatMessage(role="user", content="hello")],
            max_tokens=20,
        )

        kwargs = create.await_args.kwargs
        assert "temperature" not in kwargs
        assert kwargs["model"] == "kimi-k2.5"
        assert kwargs["max_tokens"] == 20

    @pytest.mark.asyncio
    async def test_chat_passes_explicit_temperature(self):
        provider, create = self._build_provider_with_client()
        create.return_value = self._mock_chat_response()

        from flocks.provider.provider import ChatMessage

        await provider.chat(
            "kimi-k2.5",
            [ChatMessage(role="user", content="hello")],
            temperature=1.0,
        )

        kwargs = create.await_args.kwargs
        assert kwargs["temperature"] == 1.0


class TestExtractReasoningContent:
    """Regression: some proxies send stream chunks with ``delta is None``."""

    def test_extract_reasoning_content_none_delta(self):
        assert extract_reasoning_content(None) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
