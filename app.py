import streamlit as st
import pandas as pd
import re
from datetime import datetime

st.set_page_config(page_title='Radar de Intenção', page_icon='🎯', layout='wide')

DEFAULT_TERMS = {
    'acidente': 25,
    'acidente de moto': 35,
    'bati a moto': 35,
    'sequela': 40,
    'afastado': 20,
    'quebrei': 15,
    'perdi movimento': 45,
    'não consigo trabalhar': 35,
    'auxílio': 15,
    'indenização': 20,
}

NEGATIVE_PATTERNS = [
    r'\bnunca\b.*\bacidente',
    r'\bnão sofri\b',
    r'\bsem acidente\b',
    r'\bfoi só um susto\b',
]

if 'terms' not in st.session_state:
    st.session_state.terms = DEFAULT_TERMS.copy()

if 'comments' not in st.session_state:
    st.session_state.comments = [
        {
            'nome': 'Carlos M.',
            'plataforma': 'YouTube',
            'comentario': 'Sofri um acidente de moto e perdi parte do movimento da mão. Estou afastado do trabalho.',
            'link': 'https://example.com/post/1',
            'data': '2026-08-19 08:10'
        },
        {
            'nome': 'Ana P.',
            'plataforma': 'X',
            'comentario': 'Minha conta de luz veio absurda esse mês.',
            'link': 'https://example.com/post/2',
            'data': '2026-08-19 08:15'
        },
        {
            'nome': 'Rafael S.',
            'plataforma': 'YouTube',
            'comentario': 'Quebrei a perna num acidente e ainda não consigo trabalhar direito.',
            'link': 'https://example.com/post/3',
            'data': '2026-08-19 08:20'
        },
    ]


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
        label = 'Alta'
    elif score >= 40:
        label = 'Média'
    elif score >= 15:
        label = 'Baixa'
    else:
        label = 'Irrelevante'

    return score, label, ', '.join(hits) if hits else '-'


st.title('🎯 Radar de Intenção — MVP')
st.caption('Protótipo para detectar comentários públicos que indicam um problema compatível com o serviço da empresa.')

with st.sidebar:
    st.header('Configuração')
    st.write('Cadastre termos e pesos. Quanto maior o peso, maior o impacto no score.')

    with st.form('term_form'):
        new_term = st.text_input('Novo termo')
        new_weight = st.slider('Peso', 5, 50, 20, 5)
        add_term = st.form_submit_button('Adicionar termo')
        if add_term and new_term.strip():
            st.session_state.terms[new_term.strip().lower()] = new_weight
            st.success('Termo adicionado.')

    st.divider()
    st.subheader('Termos ativos')
    for term, weight in list(st.session_state.terms.items()):
        col1, col2 = st.columns([3,1])
        col1.write(f'{term} — {weight}')
        if col2.button('✕', key=f'del_{term}'):
            del st.session_state.terms[term]
            st.rerun()

    if st.button('Restaurar padrão'):
        st.session_state.terms = DEFAULT_TERMS.copy()
        st.rerun()


st.subheader('1. Inserir comentário')
with st.form('comment_form', clear_on_submit=True):
    c1, c2 = st.columns(2)
    nome = c1.text_input('Nome / identificador público')
    plataforma = c2.selectbox('Plataforma', ['YouTube', 'X', 'Instagram', 'Facebook', 'Outra'])
    comentario = st.text_area('Comentário público')
    link = st.text_input('Link da publicação')
    submitted = st.form_submit_button('Analisar comentário')

    if submitted and comentario.strip():
        st.session_state.comments.append({
            'nome': nome.strip() or 'Não informado',
            'plataforma': plataforma,
            'comentario': comentario.strip(),
            'link': link.strip() or '-',
            'data': datetime.now().strftime('%Y-%m-%d %H:%M')
        })
        st.success('Comentário analisado e incluído no radar.')


rows = []
for item in st.session_state.comments:
    score, label, hits = score_comment(item['comentario'])
    rows.append({**item, 'score': score, 'prioridade': label, 'sinais_detectados': hits})

df = pd.DataFrame(rows)

st.subheader('2. Radar de oportunidades')
if df.empty:
    st.info('Nenhum comentário analisado ainda.')
else:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric('Comentários', len(df))
    col2.metric('Alta prioridade', int((df['prioridade'] == 'Alta').sum()))
    col3.metric('Média prioridade', int((df['prioridade'] == 'Média').sum()))
    col4.metric('Score médio', round(df['score'].mean(), 1))

    filtro = st.multiselect(
        'Filtrar prioridade',
        ['Alta', 'Média', 'Baixa', 'Irrelevante'],
        default=['Alta', 'Média', 'Baixa']
    )
    view = df[df['prioridade'].isin(filtro)].sort_values('score', ascending=False)

    st.dataframe(
        view[['score', 'prioridade', 'nome', 'plataforma', 'comentario', 'sinais_detectados', 'link', 'data']],
        use_container_width=True,
        hide_index=True,
        column_config={
            'score': st.column_config.ProgressColumn('Score', min_value=0, max_value=100),
            'link': st.column_config.LinkColumn('Link'),
        }
    )

    st.download_button(
        'Baixar oportunidades em CSV',
        data=view.to_csv(index=False).encode('utf-8-sig'),
        file_name='oportunidades.csv',
        mime='text/csv'
    )

st.divider()
st.subheader('3. Como transformar isso em produto real')
st.write('''
Este protótipo usa entrada manual para validar a lógica. A versão real teria um conector por plataforma permitida, coleta apenas de conteúdo acessível por APIs oficiais ou fontes autorizadas, classificação por regras/IA, deduplicação, score de intenção, painel e envio ao CRM.
''')
st.info('Importante: este MVP não acessa Instagram, X ou YouTube diretamente e não coleta dados privados. A integração real depende das permissões e APIs oficiais de cada plataforma.')
