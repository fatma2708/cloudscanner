"""LLM package: abstract provider layer + hybrid narrative engine.

CloudPilot supports OpenAI, Anthropic and Google Gemini through one interface.
If no API key is configured the ``HybridEngine`` falls back to a deterministic
narrative generator so the product works out of the box.
"""
