import streamlit as st
import pandas as pd
import re
import requests
from datetime import datetime
from urllib.parse import urlparse, parse_qs

st.set_page_config(page_title="Radar de Intenção", page_icon="🎯", layout="wide")

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"

DEFAULT_TERMS = {
    "acidente": 25,
    "acidente de moto": 35,
    "bati a moto": 35,
    "sequela": 40,
    "afastado": 20,
    "quebrei": 15,
    "perdi movimento": 45,
    "não consigo trabalhar": 35,
    "auxílio": 15,
    "indenização": 20,
    "invalidez": 30,
    "fiquei sem trabalhar": 30,
}

NEGATIVE_PATTERNS = [
    r"\bnunca\b.*\bacidente",
    r"\bnão sofri\b",
    r"\bsem acidente\b",
    r"\bfoi só um susto\b",
]

def init_state():
    if "terms" not in st.session_state:
        st.session_state.terms = DEFAULT_TERMS.copy()
    if "comments" not in st.session_state:
        st.session_state.comments = []

init_state()

def score_comment(text: str):
    normalized = text.lower().strip()
    score = 0
    hits = []
    for term, weight in st.session_state.terms.items():
        if term.lower() in normalized:
            score += weight
            hits.append(term)

    for patt in NEGATIVE_PATTERNS:
        if re.search(patt, normalized):
            score -= 40

    score = max(0, min(100, score))
    if score >= 70:
        label = "Alta"
    elif score >= 40:
        label = "Média"
    elif score >= 15:
        label = "Baixa"
    else:
        label = "Irrelevante"

    return score, label, ", ".join(hits) if hits else "-"

def get_api_key():
    try:
        key = st.secrets.get("YOUTUBE_API_KEY", "")
        if key:
            return str(key).strip()
    except Exception:
        pass
    return st.session_state.get("youtube_api_key", "").strip()

def extract_video_id(value: str):
    value = value.strip()
    if not value:
        return ""
    if re.fullmatch(r"[\w-]{11}", value):
        return value
    try:
        parsed = urlparse(value)
        if parsed.hostname in {"youtu.be", "www.youtu.be"}:
            return parsed.path.strip("/").split("/")[0]
        if parsed.hostname and "youtube.com" in parsed.hostname:
            if parsed.path == "/watch":
                return parse_qs(parsed.query).get("v", [""])[0]
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] in {"shorts", "live", "embed"}:
                return parts[1]
    except Exception:
        pass
    return ""

def yt_get(url, params):
    response = requests.get(url, params=params, timeout=20)
    if response.ok:
        return response.json()
    try:
        detail = response.json().get("error", {}).get("message", response.text)
    except Exception:
        detail = response.text
    raise RuntimeError(f"YouTube API {response.status_code}: {detail}")

def search_youtube_videos(api_key, query, max_videos=3):
    data = yt_get(YOUTUBE_SEARCH_URL, {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_videos,
        "order": "relevance",
        "key": api_key,
    })
    videos = []
    for item in data.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        if video_id:
            videos.append({
                "video_id": video_id,
                "titulo": snippet.get("title", ""),
                "canal": snippet.get("channelTitle", ""),
            })
    return videos

def fetch_video_comments(api_key, video_id, max_comments=50):
    collected = []
    page_token = None

    while len(collected) < max_comments:
        batch_size = min(100, max_comments - len(collected))
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": batch_size,
            "textFormat": "plainText",
            "order": "relevance",
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token

        data = yt_get(YOUTUBE_COMMENTS_URL, params)
        for item in data.get("items", []):
            top = item.get("snippet", {}).get("topLevelComment", {})
            snippet = top.get("snippet", {})
            comment_id = top.get("id", "")
            text = snippet.get("textDisplay", "")
            author = snippet.get("authorDisplayName", "Não informado")
            published = snippet.get("publishedAt", "")
            if text:
                link = f"https://www.youtube.com/watch?v={video_id}"
                if comment_id:
                    link += f"&lc={comment_id}"
                collected.append({
                    "nome": author,
                    "plataforma": "YouTube",
                    "comentario": text,
                    "link": link,
                    "data": published,
                    "video_id": video_id,
                })
            if len(collected) >= max_comments:
                break

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return collected

def add_unique_comments(items):
    existing = {(x.get("plataforma"), x.get("link"), x.get("comentario")) for x in st.session_state.comments}
    added = 0
    for item in items:
        key = (item.get("plataforma"), item.get("link"), item.get("comentario"))
        if key not in existing:
            st.session_state.comments.append(item)
            existing.add(key)
            added += 1
    return added

st.title("🎯 Radar de Intenção — MVP v2")
st.caption("Radar experimental de sinais públicos de intenção. Use somente conteúdo acessível pela API oficial e faça revisão humana antes de qualquer abordagem.")

with st.sidebar:
    st.header("Configuração")
    st.write("Cadastre termos e pesos. Quanto maior o peso, maior o impacto no score.")

    with st.form("term_form"):
        new_term = st.text_input("Novo termo")
        new_weight = st.slider("Peso", 5, 50, 20, 5)
        add_term = st.form_submit_button("Adicionar termo")
        if add_term and new_term.strip():
            st.session_state.terms[new_term.strip().lower()] = new_weight
            st.success("Termo adicionado.")

    st.divider()
    st.subheader("Termos ativos")
    for term, weight in list(st.session_state.terms.items()):
        col1, col2 = st.columns([3, 1])
        col1.write(f"{term} — {weight}")
        if col2.button("✕", key=f"del_{term}"):
            del st.session_state.terms[term]
            st.rerun()

    if st.button("Restaurar padrão"):
        st.session_state.terms = DEFAULT_TERMS.copy()
        st.rerun()

    st.divider()
    st.subheader("YouTube API")
    if get_api_key():
        st.success("Chave da API configurada.")
    else:
        temp_key = st.text_input("Chave temporária", type="password", help="Para teste. O ideal é salvar em Streamlit Secrets.")
        if temp_key:
            st.session_state.youtube_api_key = temp_key
        st.caption("A chave digitada aqui fica apenas na sessão atual do app.")

tab1, tab2 = st.tabs(["🔎 Buscar no YouTube", "✍️ Inserção manual"])

with tab1:
    st.subheader("1. Buscar oportunidades automaticamente")
    st.write("Pesquise vídeos por assunto e analise os comentários públicos desses vídeos.")

    with st.form("youtube_search_form"):
        query = st.text_input(
            "Tema da busca",
            value="acidente de moto sequela",
            help="Ex.: acidente de moto, auxílio acidente, acidente trabalho."
        )
        c1, c2 = st.columns(2)
        max_videos = c1.slider("Vídeos para analisar", 1, 5, 2)
        comments_per_video = c2.slider("Comentários por vídeo", 10, 100, 40, 10)
        min_score_import = st.slider("Importar apenas score mínimo", 0, 100, 15, 5)
        run_search = st.form_submit_button("🔎 Buscar e analisar")

    if run_search:
        api_key = get_api_key()
        if not api_key:
            st.error("Configure a chave YOUTUBE_API_KEY no Streamlit Secrets ou digite uma chave temporária na barra lateral.")
        elif not query.strip():
            st.warning("Digite um tema de busca.")
        else:
            try:
                with st.spinner("Buscando vídeos e lendo comentários públicos..."):
                    videos = search_youtube_videos(api_key, query.strip(), max_videos=max_videos)
                    all_found = []
                    progress = st.progress(0)
                    for idx, video in enumerate(videos):
                        try:
                            comments = fetch_video_comments(
                                api_key,
                                video["video_id"],
                                max_comments=comments_per_video
                            )
                            for c in comments:
                                c["origem_video"] = video["titulo"]
                                c["origem_canal"] = video["canal"]
                                score, label, hits = score_comment(c["comentario"])
                                c["_score"] = score
                                c["_prioridade"] = label
                                c["_sinais"] = hits
                                if score >= min_score_import:
                                    all_found.append(c)
                        except RuntimeError as exc:
                            st.warning(f"Não foi possível ler comentários de “{video['titulo']}”: {exc}")
                        progress.progress((idx + 1) / max(1, len(videos)))

                    added = add_unique_comments(all_found)
                    st.success(f"Busca concluída: {len(all_found)} comentários relevantes encontrados; {added} novos adicionados ao Radar.")
                    if not videos:
                        st.info("Nenhum vídeo encontrado para essa busca.")
                    elif not all_found:
                        st.info("Os vídeos foram encontrados, mas nenhum comentário atingiu o score mínimo.")

            except RuntimeError as exc:
                st.error(str(exc))
            except requests.RequestException as exc:
                st.error(f"Falha de conexão com a API do YouTube: {exc}")

    st.divider()
    st.subheader("Buscar comentários de um vídeo específico")
    with st.form("specific_video_form"):
        video_input = st.text_input("URL ou ID do vídeo do YouTube")
        specific_limit = st.slider("Quantidade de comentários", 10, 100, 50, 10, key="specific_limit")
        specific_min = st.slider("Score mínimo", 0, 100, 15, 5, key="specific_min")
        fetch_specific = st.form_submit_button("Ler comentários deste vídeo")

    if fetch_specific:
        api_key = get_api_key()
        video_id = extract_video_id(video_input)
        if not api_key:
            st.error("Configure a chave da API do YouTube primeiro.")
        elif not video_id:
            st.error("Não consegui identificar o ID desse vídeo.")
        else:
            try:
                with st.spinner("Lendo comentários..."):
                    comments = fetch_video_comments(api_key, video_id, specific_limit)
                    filtered = []
                    for c in comments:
                        score, label, hits = score_comment(c["comentario"])
                        c["_score"] = score
                        c["_prioridade"] = label
                        c["_sinais"] = hits
                        if score >= specific_min:
                            filtered.append(c)
                    added = add_unique_comments(filtered)
                st.success(f"{len(filtered)} comentários atingiram o score mínimo; {added} novos foram adicionados.")
            except RuntimeError as exc:
                st.error(str(exc))
            except requests.RequestException as exc:
                st.error(f"Falha de conexão com a API do YouTube: {exc}")

with tab2:
    st.subheader("2. Inserir comentário manualmente")
    with st.form("comment_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        nome = c1.text_input("Nome / identificador público")
        plataforma = c2.selectbox("Plataforma", ["YouTube", "X", "Instagram", "Facebook", "Outra"])
        comentario = st.text_area("Comentário público")
        link = st.text_input("Link da publicação")
        submitted = st.form_submit_button("Analisar comentário")

        if submitted and comentario.strip():
            st.session_state.comments.append({
                "nome": nome.strip() or "Não informado",
                "plataforma": plataforma,
                "comentario": comentario.strip(),
                "link": link.strip() or "-",
                "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "origem_video": "-",
                "origem_canal": "-",
            })
            st.success("Comentário analisado e incluído no radar.")

rows = []
for item in st.session_state.comments:
    score, label, hits = score_comment(item["comentario"])
    rows.append({
        **item,
        "score": score,
        "prioridade": label,
        "sinais_detectados": hits,
    })

df = pd.DataFrame(rows)

st.subheader("3. Radar de oportunidades")
if df.empty:
    st.info("Nenhum comentário analisado ainda. Faça uma busca no YouTube ou insira um comentário manualmente.")
else:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Comentários", len(df))
    col2.metric("Alta prioridade", int((df["prioridade"] == "Alta").sum()))
    col3.metric("Média prioridade", int((df["prioridade"] == "Média").sum()))
    col4.metric("Score médio", round(df["score"].mean(), 1))

    filtro = st.multiselect(
        "Filtrar prioridade",
        ["Alta", "Média", "Baixa", "Irrelevante"],
        default=["Alta", "Média", "Baixa"]
    )
    view = df[df["prioridade"].isin(filtro)].sort_values("score", ascending=False)

    display_cols = [
        "score", "prioridade", "nome", "plataforma", "comentario",
        "sinais_detectados", "origem_video", "origem_canal", "link", "data"
    ]
    for col in display_cols:
        if col not in view.columns:
            view[col] = "-"

    st.dataframe(
        view[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
            "link": st.column_config.LinkColumn("Abrir comentário"),
            "origem_video": "Vídeo",
            "origem_canal": "Canal",
        }
    )

    st.download_button(
        "Baixar oportunidades em CSV",
        data=view.to_csv(index=False).encode("utf-8-sig"),
        file_name="oportunidades.csv",
        mime="text/csv"
    )

    if st.button("Limpar Radar"):
        st.session_state.comments = []
        st.rerun()

st.divider()
st.subheader("Como esta versão funciona")
st.write("""
1. O Radar usa a API oficial do YouTube para localizar vídeos ou ler comentários de um vídeo informado.
2. Cada comentário público recebido é analisado pelos termos e pesos configurados.
3. Apenas os comentários que atingem o score definido entram no Radar.
4. O resultado deve ser tratado como **sinal de intenção**, não como confirmação de elegibilidade ou de interesse comercial.
""")
st.warning(
    "Use revisão humana e respeite privacidade, LGPD, regras profissionais e os Termos do YouTube. "
    "Não use o sistema para coletar dados privados, inferir condições sensíveis não declaradas ou fazer abordagem abusiva."
)
