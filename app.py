import streamlit as st
import pandas as pd
from datetime import date, timedelta

# --- Configurações Iniciais da Página ---
st.set_page_config(layout="wide", page_title="FECD SmartFlow - GTD")
st.title("FECD SmartFlow 🚦 | Gestão GTD para Gerente Financeiro")

# --- 1. Definições e Constantes (Alinhamento GTD) ---

# Contextos GTD adaptados à sua função (Gerente Financeiro FECD)
CONTEXTOS_GTD = [
    "@Computador",
    "@Escritório",
    "@Telefonemas",
    "@Assuntos Diretoria",
    "Aguardando Resposta",
    "Algum Dia/Talvez",
    "Referência" # Não é uma ação, mas é útil para classificar
]

# Projetos (Placeholder inicial - Deveria ser uma lista dinâmica)
PROJETOS_INICIAIS = [
    "Finalizar Relatório Contábil Mensal",
    "Proposta de Home Office (KPIs)",
    "Auditoria Interna de NFs Imobilizado"
]

# --- 2. Funções de Suporte ---

def calcular_semaforo(data_limite):
    """
    Implementa a lógica do 'Antecipação Semáforo'.
    VERMELHO: 0 a 1 dia (prazo estourando).
    AMARELO: 2 a 5 dias.
    VERDE: Mais de 5 dias.
    """
    hoje = date.today()
    if pd.isna(data_limite):
        return "AZUL" # Sem data limite (ações não urgentes)

    dias_restantes = (data_limite - hoje).days

    if dias_restantes <= 1:
        return "VERMELHO"  # Urgente / Praticamente esgotado
    elif dias_restantes <= 5:
        return "AMARELO"   # Atenção / Necessário começar
    else:
        return "VERDE"    # Antecipação / Tranquilo

def adicionar_tarefa(acao, projeto, contexto, data_limite, prioridade):
    """Adiciona uma nova tarefa ao DataFrame no Session State."""
    if acao:
        nova_tarefa = {
            "Ação": acao,
            "Projeto": projeto,
            "Contexto": contexto,
            "Data Limite": data_limite,
            "Prioridade": prioridade,
            "Concluída": False,
            "Semáforo": calcular_semaforo(data_limite)
        }
        # Adiciona a nova tarefa ao início da lista
        st.session_state.tarefas.insert(0, nova_tarefa)
    
def atualizar_status_conclusao(index, status):
    """Atualiza o status de conclusão de uma tarefa."""
    st.session_state.tarefas[index]["Concluída"] = status

# --- 3. Inicialização do Session State (Simulação de Banco de Dados) ---

if "tarefas" not in st.session_state:
    # Cria algumas tarefas iniciais de exemplo (simulando dados persistentes)
    st.session_state.tarefas = [
        {"Ação": "Concluir reconciliação do mês anterior", "Projeto": PROJETOS_INICIAIS[0], "Contexto": "@Computador", "Data Limite": date.today() + timedelta(days=2), "Prioridade": 3, "Concluída": False, "Semáforo": calcular_semaforo(date.today() + timedelta(days=2))},
        {"Ação": "Ligar para fornecedor X sobre NF pendente", "Projeto": None, "Contexto": "@Telefonemas", "Data Limite": date.today() + timedelta(days=6), "Prioridade": 2, "Concluída": False, "Semáforo": calcular_semaforo(date.today() + timedelta(days=6))},
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

with st.form("form_nova_tarefa", clear_on_submit=True):
    col1, col2, col3 = st.columns([3, 1, 1.5])
    
    with col1:
        nova_acao = st.text_input("📝 Próxima Ação (Qual é o resultado desejado?)")
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
        # A Regra dos 2 Minutos é aplicada mentalmente pelo usuário
        st.write(" ") # Espaçamento
        st.form_submit_button("✅ Adicionar Ação", on_click=adicionar_tarefa, 
                              args=(nova_acao, novo_projeto, novo_contexto, nova_data_limite, nova_prioridade))

st.markdown("---")

# --- 6. Exibição da Lista de Próximas Ações (Pilar: Organizar & Engajar) ---

st.header("🎯 Próximas Ações & Semáforo")

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

# Reorganiza a exibição: primeiro as mais urgentes/prioritárias (Semáforo -> Prioridade -> Data)
df_pendentes = df_pendentes.sort_values(by=["Semáforo", "Prioridade", "Data Limite"], 
                                        ascending=[False, True, True]) # Vermelho > Amarelo > Verde

# Mapeamento de cor do Semáforo para estilo CSS (para melhor visualização no Streamlit)
def color_semaforo(val):
    if val == "VERMELHO":
        return 'background-color: #ffcccc; color: black; font-weight: bold;' # Vermelho claro
    elif val == "AMARELO":
        return 'background-color: #ffe4b2; color: black;' # Laranja claro
    elif val == "VERDE":
        return 'background-color: #ccffcc; color: black;' # Verde claro
    else: # AZUL (Sem Data Limite)
        return 'background-color: #e0f7fa; color: black;' # Azul claro

# Colunas para exibir
colunas_exibir = ["Concluída", "Ação", "Contexto", "Projeto", "Data Limite", "Semáforo"]
df_exibicao = df_pendentes[colunas_exibir].reset_index(drop=True)

st.caption(f"Total de {len(df_pendentes)} Ações Pendentes.")

# Adiciona o seletor de conclusão em cada linha
for i, row in df_pendentes.iterrows():
    # Calcula o índice correto dentro do st.session_state.tarefas
    # Nota: Este é um hack necessário devido à forma como o Streamlit lida com o estado.
    original_index = st.session_state.tarefas.index(row.to_dict()) 
    
    col_c, col_a, col_t, col_p, col_d, col_s = st.columns([0.5, 4, 1.5, 1.5, 1.5, 1])
    
    with col_c:
        # Checkbox para marcar como concluída
        concluida = st.checkbox("", value=row["Concluída"], key=f"check_{i}", 
                                on_change=atualizar_status_conclusao, args=(original_index, not row["Concluída"]))
    
    # Aplica o estilo do Semáforo na Ação para maior visibilidade
    # Como não temos acesso a CSS inline direto no st.markdown, 
    # simulamos o destaque com emoji e BOLD, e usamos a coluna Semáforo para o visual principal
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
        st.markdown(f"**{row['Semáforo']}**") # A cor deve ser aplicada visualmente na célula, mas aqui fica só o texto
        
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
st.caption("💡 Lembrete GTD: Faça a **Revisão Semanal** usando este painel para garantir que todos os Projetos tenham a sua Próxima Ação definida!")
