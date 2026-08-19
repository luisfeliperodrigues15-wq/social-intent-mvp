import streamlit as st
import pandas as pd
import requests

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
if 'items' not in st.session_state:
    st.session_state.items = []

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
    existing = {(x['fonte'], x['link'], x['texto']) for x in st.session_state.items}
    if key in existing:
        return False
    sc, pr, hits = score_text(text)
    st.session_state.items.append({
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

def x_recent_search(query, max_posts, bearer):
    headers = {'Authorization': f'Bearer {bearer}'}
    params = {
        'query': query,
        'max_results': min(100, max(10, max_posts)),
        'tweet.fields': 'created_at,author_id,lang',
        'expansions': 'author_id',
        'user.fields': 'username,name'
    }
    data = api_get('https://api.x.com/2/tweets/search/recent', params=params, headers=headers)
    users = {u['id']: u for u in data.get('includes', {}).get('users', [])}
    out = []
    for p in data.get('data', [])[:max_posts]:
        u = users.get(p.get('author_id'), {})
        username = u.get('username', '')
        author = ('@' + username) if username else u.get('name', 'Não informado')
        link = f'https://x.com/{username}/status/{p["id"]}' if username else f'https://x.com/i/web/status/{p["id"]}'
        out.append((author, p.get('text', ''), link, p.get('created_at', '')))
    return out

st.title('🎯 Radar de Intenção — V3 Multirrede')
st.caption('Busca sinais públicos de intenção em fontes com acesso oficial. Resultados exigem revisão humana.')

with st.sidebar:
    st.header('Status das fontes')
    st.write('▶️ YouTube:', '✅ conectado' if secret('YOUTUBE_API_KEY') else '⚠️ falta chave')
    st.write('𝕏 X:', '✅ conectado' if secret('X_BEARER_TOKEN') else '⚠️ falta Bearer Token')
    st.write('📸 Instagram:', '🟡 limitado pela API Meta')
    st.write('📘 Facebook:', '🟡 limitado pela API Meta')
    st.write('👽 Reddit:', '🟡 exige validação de uso comercial')
    st.divider()
    st.subheader('Score')
    for k, v in st.session_state.terms.items():
        st.write(f'{k}: {v}')

tabs = st.tabs(['🌐 Busca multirrede', '▶️ YouTube', '𝕏 X', '📸 Meta', '👽 Reddit', '📊 Radar'])

with tabs[0]:
    st.subheader('Busca multirrede')
    q = st.text_input('O que procurar?', value='acidente de moto sequela', key='multiq')
    sources = st.multiselect('Fontes', ['YouTube', 'X'], default=['YouTube'])
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
        if 'X' in sources:
            token = secret('X_BEARER_TOKEN')
            if not token:
                st.error('Falta X_BEARER_TOKEN.')
            else:
                try:
                    for author, text, link, date in x_recent_search(q, 50, token):
                        sc, _, _ = score_text(text)
                        if sc >= min_score:
                            added += add_item('X', author, text, link, 'Busca recente', date)
                except Exception as e:
                    st.error(f'X: {e}')
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
    st.subheader('X — posts recentes')
    st.info('Precisa de um Bearer Token da X Developer Platform salvo como X_BEARER_TOKEN.')
    q = st.text_input('Consulta do X', value='"sofri um acidente" OR "fiquei com sequela"', key='xq')
    n = st.slider('Posts para analisar', 10, 100, 50, 10)
    minimum = st.slider('Score mínimo', 0, 100, 20, 5, key='xs')
    if st.button('Buscar no X'):
        token = secret('X_BEARER_TOKEN')
        if not token:
            st.error('Configure X_BEARER_TOKEN no Streamlit Secrets.')
        else:
            added = 0
            try:
                for author, text, link, date in x_recent_search(q, n, token):
                    sc, _, _ = score_text(text)
                    if sc >= minimum:
                        added += add_item('X', author, text, link, 'Busca recente', date)
                st.success(f'{added} novos resultados.')
            except Exception as e:
                st.error(str(e))

with tabs[3]:
    st.subheader('Instagram e Facebook')
    st.warning('A Meta não oferece uma busca global aberta de comentários de toda a rede para este tipo de captação.')
    st.write('A integração oficial é útil principalmente para contas profissionais conectadas: ler/gerenciar comentários da própria mídia, menções e interações permitidas.')

with tabs[4]:
    st.subheader('Reddit')
    st.warning('O Reddit exige OAuth e possui termos específicos para acesso comercial à Data API.')
    st.write('Antes de habilitar esta fonte num SaaS vendido a terceiros, precisamos validar/aprovar o uso comercial.')

with tabs[5]:
    st.subheader('Resultados')
    if not st.session_state.items:
        st.info('Nenhum resultado ainda.')
    else:
        df = pd.DataFrame(st.session_state.items)
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
            st.session_state.items = []
            st.rerun()

st.divider()
st.caption('Use apenas dados acessados por meios oficiais, evite coleta de dados privados e respeite LGPD, termos das plataformas e regras profissionais aplicáveis.')
