# Radar de Intenção — MVP v2

Versão experimental com integração à API oficial do YouTube.

## Novidades
- Busca vídeos por tema.
- Lê comentários públicos de vídeos.
- Calcula score automaticamente.
- Importa apenas comentários acima do score mínimo.
- Permite analisar um vídeo específico.
- Mantém entrada manual e exportação CSV.

## Streamlit Secret
No Streamlit Community Cloud, configure:

```toml
YOUTUBE_API_KEY = "SUA_CHAVE_AQUI"
```

Nunca coloque a chave diretamente no código público do GitHub.
