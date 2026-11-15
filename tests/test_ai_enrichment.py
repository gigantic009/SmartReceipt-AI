from backend.app.ai_enrichment import enrich_with_local_model


def test_ai_enrichment_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SMARTRECEIPT_AI_PROVIDER", raising=False)
    document = {"amounts": {}, "taxes": [], "extraction_warnings": []}
    result = enrich_with_local_model(document, "Store Total 10.00")
    assert result["ai_enrichment"]["enabled"] is False


def test_ai_enrichment_blocks_nonlocal_ollama_endpoint(monkeypatch):
    monkeypatch.setenv("SMARTRECEIPT_AI_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://example.com")
    document = {"amounts": {}, "taxes": [], "extraction_warnings": []}
    result = enrich_with_local_model(document, "Store Total 10.00")
    assert result["ai_enrichment"]["status"] == "blocked_nonlocal_endpoint"
