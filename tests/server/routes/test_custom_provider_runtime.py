from flocks.provider.provider import ModelCapabilities, ModelInfo, Provider
from flocks.server.routes.custom_provider import CreateModelReq, _add_model_to_runtime


def test_model_info_pricing_accepts_currency_string():
    model = ModelInfo(
        id="demo-model",
        name="Demo Model",
        provider_id="custom-demo",
        capabilities=ModelCapabilities(),
        pricing={"input": 0.1, "output": 0.2, "currency": "USD"},
    )

    assert model.pricing == {"input": 0.1, "output": 0.2, "currency": "USD"}


def test_add_model_to_runtime_preserves_reasoning_and_currency(monkeypatch):
    class DummyProvider:
        _custom_models = []
        _config_models = []

    provider = DummyProvider()
    body = CreateModelReq(
        model_id="minimax:MiniMax-M2.7",
        name="minimax:MiniMax-M2.7",
        context_window=200000,
        max_output_tokens=200000,
        supports_vision=False,
        supports_tools=True,
        supports_streaming=True,
        supports_reasoning=True,
        input_price=0.0,
        output_price=0.0,
        currency="USD",
    )

    original_models = Provider._models
    Provider._models = {}
    monkeypatch.setattr(Provider, "get", classmethod(lambda cls, provider_id: provider))

    try:
        _add_model_to_runtime("custom-demo", body)
        saved = Provider._models[body.model_id]

        assert saved.capabilities.supports_reasoning is True
        assert saved.pricing == {"input": 0.0, "output": 0.0, "currency": "USD"}
        assert provider._custom_models[0].pricing["currency"] == "USD"
        assert provider._config_models[0].capabilities.supports_reasoning is True
    finally:
        Provider._models = original_models
