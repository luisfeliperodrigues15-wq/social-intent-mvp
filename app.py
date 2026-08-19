import streamlit as st
import pandas as pd
import requests
import re

st.set_page_config(page_title='Radar de Intenção', page_icon='🎯', layout='wide')

DEFAULT_TERMS = {
    'acidente': 20,
    'acidente de moto': 35,
    'acidente de trabalho': 35,
    'bati a moto': 35,
    'sequela': 40,
    'afastado': 20,
    'perdi movimento': 45,
    'não consigo trabalhar': 35,
    'auxílio': 15,
    'indenização': 20,
    'invalidez': 30,
    'fiquei sem trabalhar': 30,
}

if 'terms' not in st.session_state:
    st.session_state.terms = DEFAULT_TERMS.copy()
if "items" not in st.session_state:
    st.session_state["items"] = []
elif not isinstance(st.session_state["items"], list):
    # Evita conflito com dados de sessão deixados por versões anteriores.
    st.session_state["items"] = []
else:
    # Mantém apenas registros compatíveis com a V3.
    st.session_state["items"] = [
        x for x in st.session_state["items"]
        if isinstance(x, dict)
    ]

def secret(name):
    try:
        return str(st.secrets.get(name, '')).strip()
    except Exception:
        return ''

def score_text(text):
    t = (text or '').lower()
    score = 0
    hits = []
    for term, weight in st.session_state.terms.items():
        if term.lower() in t:
            score += weight
            hits.append(term)
    score = min(100, max(0, score))
    if score >= 70:
        priority = 'Alta'
    elif score >= 40:
        priority = 'Média'
    elif score >= 15:
        priority = 'Baixa'
    else:
        priority = 'Irrelevante'
    return score, priority, ', '.join(hits) if hits else '-'

def add_item(source, author, text, url, origin='-', date='-'):
    key = (source, url, text)
    existing = {(x['fonte'], x['link'], x['texto']) for x in st.session_state["items"]}
    if key in existing:
        return False
    sc, pr, hits = score_text(text)
    st.session_state["items"].append({
        'fonte': source,
        'autor': author or 'Não informado',
        'texto': text,
        'score': sc,
        'prioridade': pr,
        'sinais': hits,
        'origem': origin,
        'link': url,
        'data': date,
    })
    return True

def api_get(url, params=None, headers=None):
    r = requests.get(url, params=params, headers=headers, timeout=25)
    if not r.ok:
        try:
            payload = r.json()
            msg = payload.get('error', {}).get('message') or payload.get('detail') or r.text
        except Exception:
            msg = r.text
        raise RuntimeError(f'Erro {r.status_code}: {msg}')
    return r.json()

def yt_search(query, max_videos, api_key):
    data = api_get('https://www.googleapis.com/youtube/v3/search', params={
        'part': 'snippet', 'q': query, 'type': 'video', 'maxResults': max_videos,
        'order': 'relevance', 'key': api_key
    })
    out = []
    for i in data.get('items', []):
        vid = i.get('id', {}).get('videoId')
        sn = i.get('snippet', {})
        if vid:
            out.append((vid, sn.get('title', ''), sn.get('channelTitle', '')))
    return out

def yt_comments(video_id, limit, api_key):
    out = []
    token = None
    while len(out) < limit:
        params = {
            'part': 'snippet', 'videoId': video_id,
            'maxResults': min(100, limit-len(out)),
            'textFormat': 'plainText', 'order': 'relevance', 'key': api_key
        }
        if token:
            params['pageToken'] = token
        data = api_get('https://www.googleapis.com/youtube/v3/commentThreads', params=params)
        for item in data.get('items', []):
            top = item.get('snippet', {}).get('topLevelComment', {})
            sn = top.get('snippet', {})
            txt = sn.get('textDisplay', '')
            if txt:
                cid = top.get('id', '')
                link = f'https://www.youtube.com/watch?v={video_id}'
                if cid:
                    link += f'&lc={cid}'
                out.append((sn.get('authorDisplayName', ''), txt, link, sn.get('publishedAt', '')))
            if len(out) >= limit:
                break
        token = data.get('nextPageToken')
        if not token:
            break
    return out


def mastodon_hashtag(instance, hashtag, limit=40):
    instance = (instance or "").strip().rstrip("/")
    if not instance.startswith("http://") and not instance.startswith("https://"):
        instance = "https://" + instance

    tag = (hashtag or "").strip().lstrip("#")
    if not tag:
        return []

    data = api_get(
        f"{instance}/api/v1/timelines/tag/{tag}",
        params={"limit": min(40, max(1, int(limit)))}
    )

    out = []
    for status in data:
        account = status.get("account", {}) or {}
        acct = account.get("acct", "")
        author = f"@{acct}" if acct else account.get("display_name", "Não informado")
        html = status.get("content", "") or ""
        txt = re.sub(r"<[^>]+>", " ", html)
        txt = re.sub(r"\s+", " ", txt).strip()
        link = status.get("url") or status.get("uri") or "-"
        date = status.get("created_at", "-")
        if txt:
            out.append((author, txt, link, date))
    return out

st.title('🎯 Radar de Intenção — V4 YouTube + Mastodon')
st.caption('Busca sinais públicos de intenção em fontes com acesso oficial. Resultados exigem revisão humana.')

with st.sidebar:
    st.header('Status das fontes')
    st.write('▶️ YouTube:', '✅ conectado' if secret('YOUTUBE_API_KEY') else '⚠️ falta chave')
    st.write('🐘 Mastodon:', '✅ sem chave necessária')
    st.divider()
    st.subheader('Score')
    for k, v in st.session_state.terms.items():
        st.write(f'{k}: {v}')

tabs = st.tabs(['🌐 Busca multirrede', '▶️ YouTube', '🐘 Mastodon', '📊 Radar'])

with tabs[0]:
    st.subheader('Busca multirrede')
    q = st.text_input('O que procurar?', value='acidente de moto sequela', key='multiq')
    sources = st.multiselect('Fontes', ['YouTube', 'Mastodon'], default=['YouTube', 'Mastodon'])
    min_score = st.slider('Score mínimo', 0, 100, 30, 5, key='multiscore')
    if st.button('🚀 Buscar em todas as fontes selecionadas'):
        added = 0
        if 'YouTube' in sources:
            key = secret('YOUTUBE_API_KEY')
            if not key:
                st.error('Falta YOUTUBE_API_KEY.')
            else:
                try:
                    for vid, title, channel in yt_search(q, 3, key):
                        for author, text, link, date in yt_comments(vid, 50, key):
                            sc, _, _ = score_text(text)
                            if sc >= min_score:
                                added += add_item('YouTube', author, text, link, f'{title} — {channel}', date)
                except Exception as e:
                    st.error(f'YouTube: {e}')
        if 'Mastodon' in sources:
            try:
                tags = []
                for word in q.split():
                    clean = re.sub(r'[^0-9A-Za-zÀ-ÿ_]', '', word)
                    if len(clean) >= 4 and clean.lower() not in [t.lower() for t in tags]:
                        tags.append(clean)
                for tag in tags[:4]:
                    for author, text_post, link, date in mastodon_hashtag('mastodon.social', tag, 40):
                        sc, _, _ = score_text(text_post)
                        if sc >= min_score:
                            added += add_item('Mastodon', author, text_post, link, f'#{tag} em mastodon.social', date)
            except Exception as e:
                st.error(f'Mastodon: {e}')
        st.success(f'Busca concluída. {added} novos resultados adicionados ao Radar.')

with tabs[1]:
    st.subheader('YouTube')
    q = st.text_input('Tema', value='acidente de moto sequela', key='ytq')
    c1, c2 = st.columns(2)
    nvid = c1.slider('Vídeos', 1, 20, 3)
    ncom = c2.slider('Comentários por vídeo', 10, 200, 50, 10)
    minimum = st.slider('Score mínimo', 0, 100, 30, 5, key='yts')
    if st.button('Buscar no YouTube'):
        key = secret('YOUTUBE_API_KEY')
        if not key:
            st.error('Configure YOUTUBE_API_KEY.')
        else:
            added = 0
            try:
                for vid, title, channel in yt_search(q, nvid, key):
                    for author, text, link, date in yt_comments(vid, ncom, key):
                        sc, _, _ = score_text(text)
                        if sc >= minimum:
                            added += add_item('YouTube', author, text, link, f'{title} — {channel}', date)
                st.success(f'{added} novos resultados.')
            except Exception as e:
                st.error(str(e))

with tabs[2]:
    st.subheader('🐘 Mastodon — posts públicos por hashtag')
    st.info('Nesta versão de teste, não precisa de chave. A disponibilidade depende da instância.')

    instance = st.text_input('Instância Mastodon', value='mastodon.social')
    hashtag = st.text_input('Hashtag', value='acidente', help='Digite sem #')
    c1, c2 = st.columns(2)
    n = c1.slider('Posts para analisar', 10, 40, 40, 10, key='mast_n')
    minimum = c2.slider('Score mínimo', 0, 100, 15, 5, key='mast_score')

    if st.button('Buscar no Mastodon'):
        added = 0
        try:
            results = mastodon_hashtag(instance, hashtag, n)
            for author, text_post, link, date in results:
                sc, _, _ = score_text(text_post)
                if sc >= minimum:
                    added += add_item('Mastodon', author, text_post, link, f'#{hashtag} em {instance}', date)
            st.success(f'Busca concluída: {len(results)} posts lidos; {added} novos resultados relevantes.')
            if not results:
                st.info('Nenhum post público encontrado para essa hashtag nessa instância.')
        except Exception as e:
            st.error(f'Mastodon: {e}')

with tabs[3]:
    st.subheader('Resultados')
    if not st.session_state["items"]:
        st.info('Nenhum resultado ainda.')
    else:
        try:
            df = pd.DataFrame.from_records(st.session_state["items"])
        except Exception:
            st.session_state["items"] = []
            st.warning('A sessão antiga era incompatível com a V3 e foi limpa. Faça a busca novamente.')
            st.stop()
        priority = st.multiselect('Prioridade', ['Alta', 'Média', 'Baixa', 'Irrelevante'], default=['Alta', 'Média', 'Baixa'])
        view = df[df['prioridade'].isin(priority)].sort_values('score', ascending=False)
        st.metric('Resultados no Radar', len(view))
        st.dataframe(view, use_container_width=True, hide_index=True,
                     column_config={
                         'score': st.column_config.ProgressColumn('Score', min_value=0, max_value=100),
                         'link': st.column_config.LinkColumn('Abrir')
                     })
        st.download_button('Baixar CSV', view.to_csv(index=False).encode('utf-8-sig'), 'radar_resultados.csv', 'text/csv')
        if st.button('Limpar Radar'):
            st.session_state["items"] = []
            st.rerun()

st.divider()
st.caption('Use apenas dados acessados por meios oficiais, evite coleta de dados privados e respeite LGPD, termos das plataformas e regras profissionais aplicáveis.')
