import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# --- Configurações da Aplicação ---
st.set_page_config(
    page_title="FECD SmartFlow - Captura de Demandas",
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
    # O filtro 'isRead eq false' é crucial para focar nas demandas novas
    # Filtro 'receivedDateTime ge {date_limit}' garante que só trazemos e-mails recentes
    filter_query = f"isRead eq false and receivedDateTime ge {date_limit}"
    
    # Endpoint para buscar mensagens na caixa de correio do usuário
    url = f"{MS_GRAPH_URL_BASE}/users/{user_email}/mailFolders/inbox/messages"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    params = {
        '$select': 'subject,sender,receivedDateTime,bodyPreview', # Campos que queremos
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
        'ID': message.get('id'),
        'Assunto': message.get('subject'),
        'Remetente': message.get('sender', {}).get('emailAddress', {}).get('address', 'N/A'),
        'Data/Hora': pd.to_datetime(message.get('receivedDateTime')).tz_convert('America/Sao_Paulo').strftime('%d/%m/%Y %H:%M'),
        'Pré-visualização do Corpo': message.get('bodyPreview', 'Sem pré-visualização'),
        'Status': 'Pendente' # Status inicial para a demanda
    }

# --- Layout e Processamento do Streamlit ---

def main():
    st.title("📧 FECD SmartFlow: Captura de Demandas (Outlook/Graph API)")
    
    # 1. Carregar Configurações
    try:
        client_id = st.secrets["graph_api"]["client_id"]
        tenant_id = st.secrets["graph_api"]["tenant_id"]
        client_secret = st.secrets["graph_api"]["client_secret"]
        user_email = st.secrets["graph_api"]["email_user"]
    except KeyError as e:
        st.error(f"Erro: Chave de segredo não encontrada no .streamlit/secrets.toml: {e}")
        st.stop()

    st.sidebar.header("⚙️ Configurações da Busca")
    
    # Seletor de período
    period_days = st.sidebar.slider(
        "Buscar e-mails dos últimos (dias):",
        min_value=1, max_value=30, value=7, step=1
    )

    if st.sidebar.button("🔄 Buscar E-mails Não Lidos"):
        with st.spinner(f"Conectando ao Microsoft Graph e buscando mensagens de {user_email}..."):
            # 2. Obter Token
            access_token = get_access_token(client_id, tenant_id, client_secret)

            if access_token:
                st.success("Token de Acesso obtido com sucesso.")

                # 3. Buscar E-mails
                email_messages = fetch_emails(access_token, user_email, period_days)
                
                if email_messages:
                    st.success(f"Encontrados {len(email_messages)} novos e-mails na sua caixa de entrada.")
                    
                    # 4. Processar e Exibir
                    data = [extract_email_data(msg) for msg in email_messages]
                    df_emails = pd.DataFrame(data)
                    
                    st.subheader("Novas Demandas Capturadas")
                    st.dataframe(df_emails, height=600)
                    
                    # 5. Exportação
                    @st.cache_data
                    def convert_df_to_csv(df):
                        # Converte o DataFrame para CSV e codifica em UTF-8
                        return df.to_csv(index=False, encoding='utf-8-sig')

                    csv = convert_df_to_csv(df_emails)
                    st.download_button(
                        label="📥 Exportar para CSV",
                        data=csv,
                        file_name=f'demandas_fecd_{datetime.now().strftime("%Y%m%d_%H%M")}.csv',
                        mime='text/csv',
                        help="Baixa a tabela de demandas exibida."
                    )
                else:
                    st.info("Nenhum e-mail não lido encontrado no período selecionado.")
            else:
                st.error("Falha ao buscar e-mails: Não foi possível obter o token de acesso.")

if __name__ == "__main__":
    main()
