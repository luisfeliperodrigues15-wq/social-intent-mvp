import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="Radar de Intenção",page_icon="🎯",layout="wide")
st.markdown("""<style>.block-container{max-width:1250px;padding-top:1.5rem}.hero,.card{border:1px solid rgba(128,128,128,.22);border-radius:18px;padding:1.2rem;margin-bottom:1rem}.hero h1{margin:0}.muted{opacity:.68}.card{border-radius:14px}</style>""",unsafe_allow_html=True)
TERMS={"acidente":20,"acidente de moto":35,"acidente de trabalho":35,"sequela":40,"afastado":20,"perdi movimento":45,"não consigo trabalhar":35,"auxílio":15,"indenização":20,"invalidez":30,"fiquei sem trabalhar":30}
if "items" not in st.session_state: st.session_state["items"]=[]
def secret(n):
    try:return str(st.secrets.get(n,"")).strip()
    except:return ""
def score(t):
    t=t.lower();s=0;h=[]
    for k,v in TERMS.items():
        if k in t:s+=v;h.append(k)
    s=min(100,s);p="Alta" if s>=70 else "Média" if s>=40 else "Baixa" if s>=15 else "Irrelevante"
    return s,p,", ".join(h) if h else "-"
def api(url,p):
    r=requests.get(url,params=p,timeout=25)
    if not r.ok:raise RuntimeError(f"Erro {r.status_code}: {r.text[:250]}")
    return r.json()
def videos(q,n,key,after,order):
    p={"part":"snippet","q":q,"type":"video","maxResults":n,"order":order,"key":key}
    if after:p["publishedAfter"]=after
    d=api("https://www.googleapis.com/youtube/v3/search",p)
    return [(x["id"]["videoId"],x["snippet"].get("title",""),x["snippet"].get("channelTitle","")) for x in d.get("items",[]) if x.get("id",{}).get("videoId")]
def comments(vid,n,key):
    out=[];token=None
    while len(out)<n:
        p={"part":"snippet","videoId":vid,"maxResults":min(100,n-len(out)),"textFormat":"plainText","order":"time","key":key}
        if token:p["pageToken"]=token
        d=api("https://www.googleapis.com/youtube/v3/commentThreads",p)
        for i in d.get("items",[]):
            top=i.get("snippet",{}).get("topLevelComment",{});sn=top.get("snippet",{});txt=sn.get("textDisplay","")
            if txt:
                link=f"https://www.youtube.com/watch?v={vid}";cid=top.get("id","")
                if cid:link+=f"&lc={cid}"
                out.append((sn.get("authorDisplayName",""),txt,link,sn.get("publishedAt","")))
        token=d.get("nextPageToken")
        if not token:break
    return out[:n]
def todt(x):
    try:return datetime.fromisoformat(x.replace("Z","+00:00"))
    except:return None
def cut(label):
    d={"24 horas":1,"7 dias":7,"30 dias":30,"90 dias":90,"1 ano":365}.get(label)
    return datetime.now(timezone.utc)-timedelta(days=d) if d else None
def fmt(x):
    d=todt(x);return d.astimezone().strftime("%d/%m/%Y às %H:%M") if d else "-"
st.markdown(f"""<div class="hero"><div class="muted">INTELIGÊNCIA COMERCIAL</div><h1>🎯 Radar de Intenção</h1><div class="muted">Sinais públicos de necessidade • {datetime.now().strftime("%d/%m/%Y")}</div></div>""",unsafe_allow_html=True)
with st.sidebar:
    st.header("Radar");st.write("▶️ YouTube","✅ conectado" if secret("YOUTUBE_API_KEY") else "⚠️ falta chave")
    st.divider();st.write("🔥 Alta: 70–100");st.write("🟡 Média: 40–69");st.write("🔵 Baixa: 15–39")
a,b=st.tabs(["🔎 Buscar oportunidades","📊 Oportunidades"])
with a:
    q=st.text_input("O que você procura?",value="acidente de moto sequela")
    c1,c2,c3=st.columns(3)
    pv=c1.selectbox("Data do vídeo",["Qualquer data","24 horas","7 dias","30 dias","90 dias","1 ano"])
    pc=c2.selectbox("Data do comentário",["24 horas","7 dias","30 dias","90 dias","1 ano","Qualquer data"],index=2)
    order=c3.selectbox("Priorizar vídeos",["Mais relevantes","Mais recentes"])
    c4,c5,c6=st.columns(3);nv=c4.slider("Vídeos",1,20,5);nc=c5.slider("Comentários/vídeo",10,300,100,10);minimum=c6.slider("Score mínimo",0,100,30,5)
    st.caption("Vídeo antigo também pode ter comentário recente.")
    if st.button("🚀 Buscar oportunidades",type="primary",use_container_width=True):
        key=secret("YOUTUBE_API_KEY")
        if not key:st.error("Falta YOUTUBE_API_KEY.")
        else:
            added=read=0
            try:
                vc=cut(pv);cc=cut(pc);after=vc.isoformat().replace("+00:00","Z") if vc else None
                with st.spinner("Analisando..."):
                    for vid,title,channel in videos(q,nv,key,after,"date" if order=="Mais recentes" else "relevance"):
                        for author,text,link,date in comments(vid,nc,key):
                            read+=1;d=todt(date)
                            if cc and (not d or d<cc):continue
                            s,pr,h=score(text)
                            if s<minimum:continue
                            k=(link,text);exists={(x.get("link"),x.get("texto")) for x in st.session_state["items"]}
                            if k not in exists:
                                st.session_state["items"].append({"autor":author,"texto":text,"score":s,"prioridade":pr,"sinais":h,"origem":f"{title} — {channel}","link":link,"data":date});added+=1
                st.success(f"{read} comentários analisados • {added} novas oportunidades.")
            except Exception as e:st.error(f"YouTube: {e}")
with b:
    if not st.session_state["items"]:st.info("Nenhuma oportunidade ainda.")
    else:
        df=pd.DataFrame(st.session_state["items"]);df["dt"]=df["data"].apply(todt)
        c1,c2,c3,c4=st.columns(4);c1.metric("🔥 Alta",int((df.prioridade=="Alta").sum()));c2.metric("🟡 Média",int((df.prioridade=="Média").sum()));c3.metric("🔵 Baixa",int((df.prioridade=="Baixa").sum()));c4.metric("🎯 Total",len(df))
        x,y=st.columns(2);ps=x.multiselect("Prioridade",["Alta","Média","Baixa"],default=["Alta","Média","Baixa"]);sort=y.selectbox("Ordenar",["Mais recentes","Maior score"])
        v=df[df.prioridade.isin(ps)].copy();v=v.sort_values(["dt","score"],ascending=[False,False],na_position="last") if sort=="Mais recentes" else v.sort_values(["score","dt"],ascending=[False,False],na_position="last")
        for _,r in v.iterrows():
            icon="🔥" if r.prioridade=="Alta" else "🟡" if r.prioridade=="Média" else "🔵";txt=str(r.texto).replace("<","&lt;").replace(">","&gt;")
            st.markdown(f"""<div class="card"><b>{icon} {r.prioridade} • Score {int(r.score)}/100</b><p>{txt}</p><div class="muted">👤 {r.autor} • 📅 {fmt(r.data)}<br>🎯 {r.sinais}<br>▶️ {r.origem}</div></div>""",unsafe_allow_html=True);st.link_button("Abrir comentário ↗",r.link)
        st.download_button("⬇️ Exportar CSV",v.drop(columns=["dt"],errors="ignore").to_csv(index=False).encode("utf-8-sig"),"radar_oportunidades.csv","text/csv")
        if st.button("🗑️ Limpar Radar"):st.session_state["items"]=[];st.rerun()
