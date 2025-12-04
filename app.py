import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import uuid 
from urllib.parse import quote # Para codificar o e-mail na URL do Graph

# --- Configurações da Aplicação ---
st.set_page_config(
    page_title="FECD SmartFlow: Captura e Gerenciamento de Demandas",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Constantes para a Microsoft Graph API
MS_GRAPH_URL_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = ["https://graph.microsoft.com/.default"] 

# --- Funções de Autenticação e API ---

@st.cache_resource(ttl=3600)  
def get_access_token(client_id, tenant_id, client_secret):
    """Obtém um token de acesso usando Client Credentials Flow."""
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    
    payload = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': SCOPES[0]
    }
    
    try:
        response = requests.post(token_url, data=payload)
        response.raise_for_status() 
        return response.json().get('access_token')
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao obter o token de acesso do Microsoft Graph: {e}")
        return None

def fetch_emails(access_token, user_email, days_ago=7):
    """Busca e-mails recentes de um usuário específico."""
    if not access_token:
        return []

    date_limit = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%dT%H:%M:%SZ')
    filter_query = f"isRead eq false and receivedDateTime ge {date_limit}"
    
    url = f"{MS_GRAPH_URL_BASE}/users/{user_email}/mailFolders/inbox/messages"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    params = {
        '$select': 'subject,sender,receivedDateTime,bodyPreview,id', 
        '$filter': filter_query,
        '$orderby': 'receivedDateTime desc' 
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get('value', [])
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao buscar e-mails do Microsoft Graph: {e}")
        st.warning("Verifique se o 'Consentimento de Administrador' foi concedido no Azure AD para esta aplicação.")
        return []

def extract_email_data(message):
    """Extrai os dados relevantes de uma mensagem de e-mail."""
    return {
        'ID_Email': message.get('id'),
        'Assunto': message.get('subject'),
        'Remetente': message.get('sender', {}).get('emailAddress', {}).get('address', 'N/A'),
        'Data/Hora': pd.to_datetime(message.get('receivedDateTime')).tz_convert('America/Sao_Paulo').strftime('%d/%m/%Y %H:%M'),
        'Pré-visualização do Corpo': message.get('bodyPreview', 'Sem pré-visualização'),
        'Selecionar': False # Coluna auxiliar para o checkbox
    }

# --- Funções de Gerenciamento de Demandas ---

def create_demands(df_selected_emails):
    """Cria novas demandas a partir dos e-mails selecionados e as adiciona ao estado."""
    
    # Se a lista de demandas no estado não existe, inicializa
    if 'demands' not in st.session_state:
        st.session_state.demands = []
        
    emails_to_process = df_selected_emails.to_dict('records')
    new_demands_count = 0
    selected_ids = []

    for email in emails_to_process:
        # Apenas cria a demanda se o checkbox 'Selecionar' for True
        if email['Selecionar']:
            new_demand = {
                'ID_Demanda': str(uuid.uuid4())[:8],
                'Assunto': email['Assunto'],
                'Remetente': email['Remetente'],
                'Data_Criacao': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'Status': 'A Fazer',
                'Prioridade': 'Média'
            }
            st.session_state.demands.append(new_demand)
            selected_ids.append(email['ID_Email'])
            new_demands_count += 1

    st.success(f"Foram criadas **{new_demands_count}** novas demandas.")
    
    # Remove os e-mails processados da lista de captura
    st.session_state.emails_data = [
        email for email in st.session_state.emails_data 
        if email['ID_Email'] not in selected_ids
    ]
    # Limpa o DataFrame editável para garantir que ele seja reconstruído corretamente
    if 'emails_data_df_edited' in st.session_state:
        del st.session_state['emails_data_df_edited']
        
    st.rerun()

# --- Layout e Processamento do Streamlit ---

def main():
    st.title("📧 FECD SmartFlow: Captura e Gerenciamento de Demandas")
    
    # 1. Carregar Configurações
    try:
        client_id = st.secrets["graph_api"]["client_id"]
        tenant_id = st.secrets["graph_api"]["tenant_id"]
        client_secret = st.secrets["graph_api"]["client_secret"]
        user_email = st.secrets["graph_api"]["email_user"]
    except KeyError as e:
        st.error(f"Erro: Chave de segredo não encontrada no .streamlit/secrets.toml: {e}")
        st.stop()

    # Inicializa o estado da sessão para armazenar os e-mails e as demandas
    if 'emails_data' not in st.session_state:
        st.session_state.emails_data = [] 
    if 'demands' not in st.session_state:
        st.session_state.demands = [] 
    
    # Inicializa o DataFrame editado no estado para uso posterior
    if 'emails_data_df_edited' not in st.session_state:
        st.session_state.emails_data_df_edited = pd.DataFrame()


    st.sidebar.header("⚙️ Configurações da Busca")
    period_days = st.sidebar.slider(
        "Buscar e-mails dos últimos (dias):",
        min_value=1, max_value=30, value=7, step=1, key="period_slider"
    )

    if st.sidebar.button("🔄 Buscar Novos E-mails"):
        with st.spinner(f"Conectando ao Microsoft Graph e buscando mensagens de {user_email}..."):
            access_token = get_access_token(client_id, tenant_id, client_secret)

            if access_token:
                email_messages = fetch_emails(access_token, user_email, period_days)
                
                if email_messages:
                    st.session_state.emails_data = [extract_email_data(msg) for msg in email_messages]
                    st.success(f"Encontrados **{len(st.session_state.emails_data)}** novos e-mails na sua caixa de entrada.")
                    # Reinicializa o DF editado após uma nova busca
                    st.session_state.emails_data_df_edited = pd.DataFrame(st.session_state.emails_data)
                else:
                    st.info("Nenhum e-mail não lido encontrado no período selecionado.")
                    st.session_state.emails_data = [] 
                    st.session_state.emails_data_df_edited = pd.DataFrame()
            else:
                st.error("Falha ao buscar e-mails: Não foi possível obter o token de acesso.")
    
    # --- Linha de separação ---
    st.markdown("---")

    # --- Seção 1: Captura e Seleção de E-mails ---
    
    if st.session_state.emails_data:
        st.header("1. E-mails Capturados: Selecione para Criar Demandas")
        
        # Cria um DataFrame a partir da lista de dados para ser editado
        df_emails_capture = pd.DataFrame(st.session_state.emails_data)
        
        # Mapeamento do DataFrame para a chave de estado que será editada
        # Este é o ponto chave: o DataFrame editável deve ser inicializado, mas não no form
        
        # Usamos o st.data_editor fora do st.form para evitar o erro de estado.
        df_editavel = st.data_editor(
            df_emails_capture.drop(columns=['ID_Email']), 
            use_container_width=True,
            column_config={
                "Selecionar": st.column_config.CheckboxColumn(
                    "Selecionar",
                    help="Marque os e-mails que devem virar uma demanda.",
                    default=False,
                    width="small"
                ),
                "Pré-visualização do Corpo": None 
            },
            key="emails_data_df_edited", # A chave onde o estado editado será salvo
            hide_index=True
        )
        
        # O botão de processamento agora está dentro de um formulário simples para uma ação de clique
        with st.form("process_demands_form"):
            process_button = st.form_submit_button("✅ Criar Demandas Selecionadas")

        if process_button:
            # Pega o DataFrame editado salvo pelo st.data_editor no estado da sessão
            df_final_com_selecao = st.session_state['emails_data_df_edited']
            
            # Filtra as linhas onde 'Selecionar' é True
            selected_rows = df_final_com_selecao.loc[df_final_com_selecao['Selecionar'] == True]
            
            if not selected_rows.empty:
                # Chama a função de criação de demandas com as linhas filtradas
                create_demands(selected_rows)
                
                # O st.rerun() já é chamado dentro da create_demands, mas mantemos a chamada aqui para clareza
                st.rerun()
            else:
                st.warning("Selecione pelo menos um e-mail para criar uma demanda.")

    st.markdown("---")

    # --- Seção 2: Gerenciamento de Demandas Criadas ---
    
    st.header("2. Demandas Ativas")
    
    if st.session_state.demands:
        # Converte a lista de demandas em DataFrame para exibição
        df_demandas = pd.DataFrame(st.session_state.demands)
        
        # O DataFrame de demandas é editável para que o usuário possa atualizar Status e Prioridade
        st.data_editor(
            df_demandas,
            use_container_width=True,
            column_config={
                "Status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["A Fazer", "Em Andamento", "Concluída", "Cancelada"],
                    required=True,
                ),
                "Prioridade": st.column_config.SelectboxColumn(
                    "Prioridade",
                    options=["Baixa", "Média", "Alta", "Urgente"],
                    required=True,
                ),
                # Campos não editáveis e removidos da visualização principal
                "ID_Demanda": None, 
                "Remetente": "Remetente Original" 
            },
            key="active_demands_table", 
            hide_index=True,
        )

        st.caption("Você pode editar o **Status** e a **Prioridade** diretamente na tabela acima.")
        
        # Botão para salvar alterações (processa a edição feita acima)
        if st.button("💾 Salvar Alterações nas Demandas"):
            # Atualizamos a lista de demandas com os novos valores do data_editor
            st.session_state.demands = st.session_state.active_demands_table.to_dict('records')
            st.success("Demandas atualizadas com sucesso!")

        # Exportação das demandas ativas
        @st.cache_data
        def convert_df_to_csv(df):
            return df.to_csv(index=False, encoding='utf-8-sig')

        csv_demandas = convert_df_to_csv(df_demandas)
        st.download_button(
            label="📥 Exportar Demandas Ativas (CSV)",
            data=csv_demandas,
            file_name=f'demandas_ativas_fecd_{datetime.now().strftime("%Y%m%d_%H%M")}.csv',
            mime='text/csv',
            help="Baixa a lista atual de todas as demandas ativas."
        )

    else:
        st.info("Nenhuma demanda ativa no momento. Busque novos e-mails para começar!")


if __name__ == "__main__":
    main()
