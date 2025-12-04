import streamlit as st
import pandas as pd
from imap_tools import MailBox, AND

## Função para carregar credenciais do secrets.toml
def carregar_credenciais():
    # As chaves 'imap_server', 'imap_port', 'username' e 'password'
    # devem estar aninhadas sob a seção [email] no .streamlit/secrets.toml
    secrets = st.secrets.get("email", {})
    
    # Verifica se as chaves necessárias estão presentes
    if not all(key in secrets for key in ["imap_server", "imap_port", "username", "password"]):
        st.error("Erro: Credenciais de e-mail incompletas ou faltando na seção [email] do secrets.toml.")
        return None, None, None, None

    return (
        secrets.imap_server,
        secrets.imap_port,
        secrets.username,
        secrets.password
    )

## Função para buscar e-mails
def buscar_demandas(assunto_filtro="[NOVA DEMANDA TCC]"):
    server, port, user, password = carregar_credenciais()
    
    if not server:
        return pd.DataFrame()

    demandas = []

    try:
        # 1. Conecta-se ao servidor IMAP
        # Usa o 'with MailBox' para garantir que a conexão seja fechada
        with MailBox(server, port).login(user, password) as mailbox:
            st.info(f"Conectado ao servidor IMAP: {server}")

            # 2. Busca por e-mails com o assunto específico, que ainda não foram lidos (seen=False)
            emails = mailbox.fetch(
                criteria=AND(subject=assunto_filtro, seen=False),
                bulk=True,
                reverse=True # Mais recente primeiro
            )
            
            # 3. Processa os e-mails encontrados
            for msg in emails:
                demandas.append({
                    "ID": msg.uid,
                    "Assunto": msg.subject,
                    "Remetente": msg.from_,
                    "Data": msg.date,
                    "Corpo": msg.text if msg.text else msg.html # Prioriza o corpo em texto simples
                })
                # Opcional: Marcar o e-mail como lido após a captura
                # mailbox.mark_seen(msg.uid)

            return pd.DataFrame(demandas)

    except Exception as e:
        # Captura erros comuns como falha de login (senha incorreta, MFA bloqueando)
        st.error(f"❌ Erro ao conectar ou buscar e-mails: {e}")
        st.caption("Verifique se o servidor/porta estão corretos e se você está usando uma Senha de Aplicativo, caso o Outlook exija MFA.")
        return pd.DataFrame()

# --- Interface Streamlit ---

st.set_page_config(page_title="Captura de Demandas", layout="wide")
st.title("Sistema de Captura de Demandas (IMAP)")
st.caption("Busca e-mails não lidos com assunto específico usando as credenciais do Outlook armazenadas em `secrets.toml`.")

# Permite ao usuário alterar o filtro de assunto
filtro_assunto = st.text_input(
    "Filtro de Assunto:", 
    value="[NOVA DEMANDA TCC]",
    help="O aplicativo buscará e-mails não lidos cujo assunto corresponda a este texto."
)

st.subheader("Novas Demandas Capturadas")

if st.button("🔄 Buscar Novas Demandas"):
    with st.spinner("Conectando ao Outlook e buscando e-mails..."):
        df_demandas = buscar_demandas(filtro_assunto)
        
        if not df_demandas.empty:
            st.success(f"✅ Foram encontradas **{len(df_demandas)}** novas demandas com o assunto '{filtro_assunto}'!")
            
            # Exibe os dados capturados
            st.dataframe(df_demandas, use_container_width=True)
            
            # Opcional: Permite exportar para CSV
            csv = df_demandas.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Baixar Demandas em CSV",
                data=csv,
                file_name=f'demandas_{len(df_demandas)}_{pd.Timestamp.now().strftime("%Y%m%d")}.csv',
                mime='text/csv',
            )
            
        else:
            # A função já trata o erro, esta é a mensagem para o caso de não encontrar resultados (sem erro de conexão)
            if carregar_credenciais()[0]:
                 st.warning("⚠️ Nenhuma nova demanda encontrada que corresponda ao filtro.")
