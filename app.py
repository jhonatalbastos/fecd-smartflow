import streamlit as st
import pandas as pd
import requests
import json
from datetime import date, timedelta
from urllib.parse import quote

# --- Configurações Iniciais da Página ---
st.set_page_config(layout="wide", page_title="FECD SmartFlow - GTD")
st.title("FECD SmartFlow 🚦 | Gestão GTD para Gerente Financeiro")

# --- 1. Definições e Constantes GTD ---

# Contextos GTD adaptados à sua função (Gerente Financeiro FECD)
CONTEXTOS_GTD = [
    "@Computador",
    "@Escritório",
    "@Telefonemas",
    "@Assuntos Diretoria",
    "Aguardando Resposta",
    "Algum Dia/Talvez",
    "Referência"
]
PROJETOS_INICIAIS = [
    "Finalizar Relatório Contábil Mensal",
    "Proposta de Home Office (KPIs)",
    "Auditoria Interna de NFs Imobilizado"
]

# --- 2. Funções de Suporte (GTD e Métricas) ---

def calcular_semaforo(data_limite):
    """Implementa a lógica do 'Antecipação Semáforo'."""
    hoje = date.today()
    if pd.isna(data_limite) or data_limite is None:
        return "AZUL" 

    dias_restantes = (data_limite - hoje).days

    if dias_restantes <= 1:
        return "VERMELHO"
    elif dias_restantes <= 5:
        return "AMARELO"
    else:
        return "VERDE"

def adicionar_tarefa(acao, projeto, contexto, data_limite, prioridade):
    """Adiciona uma nova tarefa ao DataFrame no Session State."""
    if acao:
        # Garante que a data_limite é um objeto date
        if isinstance(data_limite, str):
            data_limite = pd.to_datetime(data_limite).date()

        nova_tarefa = {
            "Ação": acao,
            "Projeto": projeto,
            "Contexto": contexto,
            "Data Limite": data_limite,
            "Prioridade": prioridade,
            "Concluída": False,
            "Semáforo": calcular_semaforo(data_limite)
        }
        st.session_state.tarefas.insert(0, nova_tarefa)
    
def atualizar_status_conclusao(index, status):
    """Atualiza o status de conclusão de uma tarefa."""
    st.session_state.tarefas[index]["Concluída"] = status

def carregar_credenciais_graph():
    """Carrega credenciais da Graph API do secrets.toml."""
    secrets = st.secrets.get("graph_api", {})
    if not all(key in secrets for key in ["tenant_id", "client_id", "client_secret", "email_user"]):
        st.error("Erro: Credenciais da Graph API incompletas na seção [graph_api] do secrets.toml.")
        return None
    return secrets

def obter_token_acesso(credenciais):
    """Obtém um token de acesso usando o fluxo Client Credentials."""
    url_token = f"https://login.microsoftonline.com/{credenciais['tenant_id']}/oauth2/v2.0/token"
    
    # As permissões de Aplicação (Application Permissions) usam o escopo .default
    payload = {
        'client_id': credenciais['client_id'],
        'scope': 'https://graph.microsoft.com/.default',
        'client_secret': credenciais['client_secret'],
        'grant_type': 'client_credentials'
    }
    
    try:
        response = requests.post(url_token, data=payload)
        response.raise_for_status()
        return response.json().get('access_token')
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao obter o token de acesso: {e}")
        st.caption("Verifique se o Tenant ID, Client ID e Client Secret estão corretos e se o Consentimento de Administrador foi concedido.")
        return None

def buscar_demandas_graph(token, credenciais, assunto_filtro):
    """Busca e-mails usando a Microsoft Graph API."""
    
    # URL do endpoint para buscar mensagens (assumindo a caixa de correio do usuário)
    # A URL deve ser ajustada se for uma caixa de correio diferente/compartilhada
    user_email_encoded = quote(credenciais['email_user'])
    url_messages = f"https://graph.microsoft.com/v1.0/users/{user_email_encoded}/messages"
    
    # Filtro OData para o assunto
    # O filtro 'isRead eq false' garante que apenas e-mails não lidos sejam capturados (GTD Inbox)
    # O filtro 'subject eq ...' busca a demanda
    odata_filter = f"isRead eq false and contains(subject, '{assunto_filtro}')"

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    params = {
        '$filter': odata_filter,
        '$select': 'subject,sender,receivedDateTime,bodyPreview,body', # Dados que queremos
        '$orderby': 'receivedDateTime desc' # Mais recentes primeiro
    }

    try:
        response = requests.get(url_messages, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json().get('value', [])
        demandas = []
        for msg in data:
            demandas.append({
                "ID": msg.get('id'),
                "Assunto": msg.get('subject'),
                "Remetente": msg.get('sender', {}).get('emailAddress', {}).get('address'),
                "Data": pd.to_datetime(msg.get('receivedDateTime')),
                "Corpo (Prévia)": msg.get('bodyPreview')
            })
            
            # TODO: Adicionar a lógica para marcar o e-mail como lido após o processamento
            
        return pd.DataFrame(demandas)
        
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao buscar mensagens: {e}")
        return pd.DataFrame()

# --- 3. Inicialização do Session State (Simulação de Banco de Dados) ---

if "tarefas" not in st.session_state:
    # Cria algumas tarefas iniciais de exemplo (simulando dados persistentes)
    st.session_state.tarefas = [
        {"Ação": "Concluir reconciliação do mês anterior", "Projeto": PROJETOS_INICIAIS[0], "Contexto": "@Computador", "Data Limite": date.today() + timedelta(days=2), "Prioridade": 3, "Concluída": False, "Semáforo": calcular_semaforo(date.today() + timedelta(days=2))},
        {"Ação": "Revisar status das certidões negativas de débito", "Projeto": None, "Contexto": "@Escritório", "Data Limite": date.today() + timedelta(days=1), "Prioridade": 1, "Concluída": False, "Semáforo": calcular_semaforo(date.today() + timedelta(days=1))},
        {"Ação": "Reunir dados de produtividade para proposta HO", "Projeto": PROJETOS_INICIAIS[1], "Contexto": "@Computador", "Data Limite": date.today() + timedelta(days=15), "Prioridade": 4, "Concluída": False, "Semáforo": calcular_semaforo(date.today() + timedelta(days=15))},
    ]

# --- 4. Sidebar (Filtros GTD e Módulo 3 - Referência Rápida) ---

with st.sidebar:
    st.header("Fluxo GTD & Filtros")
    
    # Filtro por Contexto
    filtro_contexto = st.selectbox(
        "Filtrar por Contexto (Próximas Ações)", 
        ["TODOS"] + CONTEXTOS_GTD
    )
    
    # Filtro por Projeto
    filtro_projeto = st.selectbox(
        "Filtrar por Projeto", 
        ["TODOS"] + PROJETOS_INICIAIS
    )
    
    st.markdown("---")
    
    # Módulo 3: Links de Referência Rápida (GTD - Referência)
    st.subheader("Links Essenciais (Referência)")
    st.markdown("- [Pasta Certidões](link_simulado)")
    st.markdown("- [Planilha Fluxo de Caixa](link_simulado)")
    st.markdown("- [Notas Fiscais Imobilizado](link_simulado)")
    
# --- 5. Formulário de Captura (Pilar: Capturar & Esclarecer) ---

st.header("📥 Capturar & Esclarecer (Inbox)")

# --- NOVO MÓDULO DE CAPTURA DE E-MAIL ---
credenciais = carregar_credenciais_graph()
if credenciais:
    st.subheader("Integração Outlook (Microsoft Graph API)")
    filtro_assunto = st.text_input(
        "Filtro de Assunto para Demandas:", 
        value="[DEMANDA FECD]",
        help="O aplicativo buscará e-mails não lidos cujo assunto contenha este texto."
    )
    if st.button("🔄 Capturar Demandas do Outlook"):
        with st.spinner("Obtendo Token e Buscando e-mails..."):
            token = obter_token_acesso(credenciais)
            if token:
                df_demandas = buscar_demandas_graph(token, credenciais, filtro_assunto)
                
                if not df_demandas.empty:
                    st.success(f"✅ Encontradas **{len(df_demandas)}** novas demandas!")
                    st.dataframe(df_demandas[["Data", "Remetente", "Assunto", "Corpo (Prévia)"]], use_container_width=True)
                    # Adicione aqui a lógica para transformar a demanda em uma tarefa GTD no seu sistema
                    
                else:
                    st.warning("⚠️ Nenhuma nova demanda encontrada ou erro ao buscar.")
                    
st.markdown("---") # Separador visual entre captura de e-mail e manual

with st.form("form_nova_tarefa", clear_on_submit=True):
    st.subheader("Captura Manual de Ações (Inbox)")
    col1, col2, col3 = st.columns([3, 1, 1.5])
    
    with col1:
        nova_acao = st.text_input("📝 Próxima Ação (O que precisa ser feito?)")
    with col2:
        nova_prioridade = st.selectbox("⚡ Prioridade", options=[1, 2, 3, 4], index=2, help="1=Crítico, 4=Baixo")
    with col3:
        novo_projeto = st.selectbox("📚 Projeto", options=[None] + PROJETOS_INICIAIS, index=0, help="Se tiver mais de 1 Ação, é um Projeto.")
        
    col4, col5, col6 = st.columns([1, 1, 1])
    
    with col4:
        novo_contexto = st.selectbox("📌 Contexto (Onde faço?)", options=CONTEXTOS_GTD)
    with col5:
        nova_data_limite = st.date_input("📅 Data Limite", value=None)
    with col6:
        st.write(" ")
        st.form_submit_button("✅ Adicionar Ação Manual", on_click=adicionar_tarefa, 
                              args=(nova_acao, novo_projeto, novo_contexto, nova_data_limite, nova_prioridade))

st.markdown("---")

# --- 6. Exibição da Lista de Próximas Ações (Pilar: Organizar & Engajar) ---

st.header("🎯 Próximas Ações & Semáforo")

# ... (O restante da lógica de exibição do DataFrame permanece a mesma do código anterior) ...

# Cria o DataFrame para facilitar a visualização e filtro
df_tarefas = pd.DataFrame(st.session_state.tarefas)

# Aplica os filtros
df_filtrado = df_tarefas.copy()
if filtro_contexto != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["Contexto"] == filtro_contexto]
if filtro_projeto != "TODOS":
    df_filtrado = df_filtrado[df_filtrado["Projeto"] == filtro_projeto]

# Separa concluídas das pendentes
df_pendentes = df_filtrado[df_filtrado["Concluída"] == False]

# Reorganiza a exibição: primeiro as mais urgentes/prioritárias
df_pendentes = df_pendentes.sort_values(by=["Semáforo", "Prioridade", "Data Limite"], 
                                        ascending=[False, True, True]) 

def color_semaforo(val):
    if val == "VERMELHO":
        return 'background-color: #ffcccc; color: black; font-weight: bold;'
    elif val == "AMARELO":
        return 'background-color: #ffe4b2; color: black;'
    elif val == "VERDE":
        return 'background-color: #ccffcc; color: black;'
    else: 
        return 'background-color: #e0f7fa; color: black;'

st.caption(f"Total de {len(df_pendentes)} Ações Pendentes.")

# Adiciona o seletor de conclusão em cada linha
for i, row in df_pendentes.iterrows():
    original_index = st.session_state.tarefas.index(row.to_dict()) 
    
    col_c, col_a, col_t, col_p, col_d, col_s = st.columns([0.5, 4, 1.5, 1.5, 1.5, 1])
    
    with col_c:
        concluida = st.checkbox("", value=row["Concluída"], key=f"check_{i}", 
                                on_change=atualizar_status_conclusao, args=(original_index, not row["Concluída"]))
    
    emoji_semaforo = "🔴" if row["Semáforo"] == "VERMELHO" else ("🟡" if row["Semáforo"] == "AMARELO" else ("🟢" if row["Semáforo"] == "VERDE" else "🔵"))
    
    with col_a:
        st.markdown(f"{emoji_semaforo} **{row['Ação']}**")
    with col_t:
        st.markdown(f"*{row['Contexto']}*")
    with col_p:
        st.markdown(f"_{row['Projeto'] or ''}_")
    with col_d:
        st.markdown(f"{row['Data Limite'].strftime('%d/%m/%Y') if row['Data Limite'] else ''}")
    with col_s:
        st.markdown(f"**{row['Semáforo']}**")
        
st.markdown("---")

# --- 7. Lista de Concluídas (Para Refletir) ---
st.subheader("✅ Concluídas (Refletir)")
df_concluidas = df_filtrado[df_filtrado["Concluída"] == True]

if not df_concluidas.empty:
    st.dataframe(df_concluidas[["Ação", "Contexto", "Data Limite"]].style.applymap(lambda x: 'color: #888888;', subset=["Ação"]),
                 hide_index=True)
else:
    st.info("Nenhuma tarefa concluída neste filtro ainda.")

# --- Dica GTD ---
st.caption("💡 Lembrete GTD: Faça a **Revisão Semanal** usando este painel!")
