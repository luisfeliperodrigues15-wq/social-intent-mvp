# Radar de Intenção V3 — Multirrede

## Fontes
- YouTube: funcional via YouTube Data API v3.
- X: funcional via X API v2 Recent Search.
- Instagram/Facebook: limitado pela API oficial da Meta.
- Reddit: reservado até validação do uso comercial/API.

## Secrets
```toml
YOUTUBE_API_KEY = "..."
X_BEARER_TOKEN = "..."
```

Nunca publique tokens no GitHub.


## V3.1
Correção de compatibilidade com sessão das versões anteriores.


## V3.2
Corrige conflito com `SessionState.items`, que causava o erro `'method' object is not iterable`.
