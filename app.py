import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import uuid # Módulo para gerar IDs únicos para as demandas

# --- Configurações da Aplicação ---
st.set_page_config(
    page_title="FECD SmartFlow: Captura e Gerenciamento de Demandas",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Constantes para a Microsoft Graph API
MS_GRAPH_URL_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = ["https://graph.microsoft.com/.default"] # Permissão padrão para Client Credentials Flow

# --- Funções de Autenticação e API ---

@st.cache_resource(ttl=3600)  # Cacheia o token por 1 hora
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
        response.raise_for_status() # Lança exceção para status ruins (4xx ou 5xx)
        return response.json().get('access_token')
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao obter o token de acesso do Microsoft Graph: {e}")
        return None

def fetch_emails(access_token, user_email, days_ago=7):
    """Busca e-mails recentes de um usuário específico."""
    if not access_token:
        return []

    # Calcular a data limite (apenas mensagens dos últimos 'days_ago')
    date_limit = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Query de filtro OData: filtra por data, e-mails não lidos e na pasta Inbox
    filter_query = f"isRead eq false and receivedDateTime ge {date_limit}"
    
    # Endpoint para buscar mensagens na caixa de correio do usuário
    url = f"{MS_GRAPH_URL_BASE}/users/{user_email}/mailFolders/inbox/messages"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    params = {
        '$select': 'subject,sender,receivedDateTime,bodyPreview,id', # Incluindo 'id' para referência
        '$filter': filter_query,
        '$orderby': 'receivedDateTime desc' # Ordena do mais novo para o mais antigo
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
        'ID_Email': message.get('id'), # Renomeado para ID_Email para evitar conflito com ID_Demanda
        'Assunto': message.get('subject'),
        'Remetente': message.get('sender', {}).get('emailAddress', {}).get('address', 'N/A'),
        'Data/Hora': pd.to_datetime(message.get('receivedDateTime')).tz_convert('America/Sao_Paulo').strftime('%d/%m/%Y %H:%M'),
        'Pré-visualização do Corpo': message.get('bodyPreview', 'Sem pré-visualização'),
    }

# --- Funções de Gerenciamento de Demandas ---

def create_demands(selected_emails):
    """Cria novas demandas a partir dos e-mails selecionados e as adiciona ao estado."""
    new_demands = []
    
    # Se a lista de demandas no estado não existe, inicializa
    if 'demands' not in st.session_state:
        st.session_state.demands = []
        
    for email in selected_emails:
        new_demand = {
            'ID_Demanda': str(uuid.uuid4())[:8], # ID único para a demanda
            'Assunto': email['Assunto'],
            'Remetente': email['Remetente'],
            'Data_Criacao': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'Status': 'A Fazer',
            'Prioridade': 'Média' # Pode ser editado depois
        }
        new_demands.append(new_demand)

    # Adiciona as novas demandas à lista de demandas existente
    st.session_state.demands.extend(new_demands)
    st.success(f"Foram criadas **{len(new_demands)}** novas demandas.")

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
        st.session_state.emails_data = [] # E-mails capturados
    if 'demands' not in st.session_state:
        st.session_state.demands = [] # Demandas criadas

    st.sidebar.header("⚙️ Configurações da Busca")
    period_days = st.sidebar.slider(
        "Buscar e-mails dos últimos (dias):",
        min_value=1, max_value=30, value=7, step=1, key="period_slider"
    )

    if st.sidebar.button("🔄 Buscar Novos E-mails"):
        with st.spinner(f"Conectando ao Microsoft Graph e buscando mensagens de {user_email}..."):
            access_token = get_access_token(client_id, tenant_id, client_secret)

            if access_token:
                #st.success("Token de Acesso obtido com sucesso.")
                email_messages = fetch_emails(access_token, user_email, period_days)
                
                if email_messages:
                    # Salva os dados brutos dos e-mails no estado da sessão
                    st.session_state.emails_data = [extract_email_data(msg) for msg in email_messages]
                    st.success(f"Encontrados **{len(st.session_state.emails_data)}** novos e-mails na sua caixa de entrada.")
                else:
                    st.info("Nenhum e-mail não lido encontrado no período selecionado.")
                    st.session_state.emails_data = [] # Limpa a lista se não houver novos
            else:
                st.error("Falha ao buscar e-mails: Não foi possível obter o token de acesso.")
    
    # --- Linha de separação ---
    st.markdown("---")

    # --- Seção 1: Captura e Seleção de E-mails ---
    
    if st.session_state.emails_data:
        st.header("1. E-mails Capturados: Selecione para Criar Demandas")
        
        # Cria um DataFrame para a exibição (adicionando a coluna de seleção)
        df_emails_capture = pd.DataFrame(st.session_state.emails_data)
        
        # Cria um contêiner para o formulário de seleção
        with st.form("email_selection_form"):
            st.caption("Marque os e-mails que devem virar uma demanda na coluna **Selecionar**.")
            
            # DataFrame editável (a chave "emails_to_select" será criada no st.session_state)
            st.dataframe(
                df_emails_capture.drop(columns=['ID_Email']), # Remove a coluna ID_Email da visualização inicial
                use_container_width=True,
                column_config={
                    "Select": st.column_config.CheckboxColumn(
                        "Selecionar",
                        help="Marque os e-mails que devem virar uma demanda.",
                        default=False,
                    ),
                    "Pré-visualização do Corpo": None # Esconde a pré-visualização, focando no assunto
                },
                key="emails_to_select",
                hide_index=True
            )
            
            submitted = st.form_submit_button("✅ Criar Demandas Selecionadas")

        if submitted:
            # FIX APLICADO: Garante que a chave existe antes de tentar acessá-la
            if 'emails_to_select' in st.session_state:
                # O DataFrame no estado da sessão não tem o ID_Email. Usamos o DF original para mapear.
                selected_df_state = pd.DataFrame(st.session_state.emails_to_select)
                
                # Juntamos o DF original com a coluna de seleção do estado
                # O DF no estado não tem todas as colunas, então fazemos um merge (ou reindexamos com cuidado)
                
                # Método mais seguro: Usar o índice do estado para buscar no DF original
                # Criamos um DF temporário com a coluna 'Select' do estado
                df_original_com_select = df_emails_capture.copy()
                df_original_com_select['Select'] = selected_df_state['Select']
                
                selected_rows = df_original_com_select.loc[df_original_com_select['Select'] == True]
                
                if not selected_rows.empty:
                    emails_to_process = selected_rows.to_dict('records')
                    
                    create_demands(emails_to_process)
                    
                    # Remove os e-mails processados da lista de captura
                    selected_ids = selected_rows['ID_Email'].tolist()
                    st.session_state.emails_data = [
                        email for email in st.session_state.emails_data 
                        if email['ID_Email'] not in selected_ids
                    ]
                    # Limpa a chave do DataFrame editável para forçar a atualização da tabela na próxima execução
                    del st.session_state['emails_to_select'] 
                    st.rerun() # Recarrega para atualizar a tabela de seleção
                else:
                    st.warning("Selecione pelo menos um e-mail para criar uma demanda.")
            else:
                st.warning("Erro interno na leitura do estado da seleção. Tente novamente.")

    st.markdown("---")

    # --- Seção 2: Gerenciamento de Demandas Criadas ---
    
    st.header("2. Demandas Ativas")
    
    if st.session_state.demands:
        # Converte a lista de demandas em DataFrame para exibição
        df_demandas = pd.DataFrame(st.session_state.demands)
        
        st.dataframe(
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
                # Remove o ID único da visualização principal
                "ID_Demanda": None, 
                "Remetente": "Remetente Original" # Renomeia para melhor clareza
            },
            key="active_demands_table", # O estado editável será salvo nesta chave
            hide_index=True,
        )

        st.caption("Você pode editar o **Status** e a **Prioridade** diretamente na tabela acima.")
        
        # Botão para salvar alterações (após a edição direta no DataFrame)
        if st.button("💾 Salvar Alterações nas Demandas"):
            # O Streamlit salva o DataFrame editado no st.session_state.active_demands_table
            # Atualizamos a lista de demandas com os novos valores
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
