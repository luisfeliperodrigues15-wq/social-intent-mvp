# Radar de Intenção — MVP

Protótipo local de um software que classifica comentários públicos por sinais de intenção e relevância comercial.

## Como rodar

1. Instale Python 3.10+.
2. Abra o terminal nesta pasta.
3. Rode:

```bash
pip install -r requirements.txt
streamlit run app.py
```

O navegador abrirá o painel automaticamente.

## O que já faz

- Cadastra palavras e pesos.
- Recebe comentários manualmente.
- Calcula score de 0 a 100.
- Classifica oportunidade em Alta, Média, Baixa ou Irrelevante.
- Filtra e ordena oportunidades.
- Exporta CSV.

## Próximas integrações

A coleta automática deve usar APIs oficiais ou fontes autorizadas de cada plataforma. O MVP não realiza scraping, não coleta conteúdo privado e não envia mensagens automaticamente.
