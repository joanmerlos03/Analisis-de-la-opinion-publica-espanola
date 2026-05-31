import streamlit as st
import pandas as pd
import os
import hashlib
from datetime import datetime, timedelta, date
import json
import gspread
import requests
from dotenv import load_dotenv
import html
import re
import unicodedata

load_dotenv(override=True)

# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================

TOPICS_DISPONIBLES = [
    "Economía",
    "Medioambiente",
    "Política",
    "Tecnología",
    "Ciencia",
    "Salud",
    "Deportes",
    "Cultura",
    "Educación",
    "Internacional",
    "Sociedad",
    "Opinión"
]

COLUMNAS_USUARIOS = [
    "nombre",
    "email",
    "password_hash",
    "topics",
    "topics_personalizados",
    "recibir_email",
    "fecha_actualizacion"
]

COLUMNAS_NOTICIAS = [
    "fecha_ejecucion",
    "periodico",
    "titulo",
    "enlace",
    "texto_completo"
]

AZUL = "#1f4e79"
AZUL_CLARO = "#2b7bbb"
AZUL_FONDO = "#f3f8ff"
AZUL_BORDE = "#d8e8f7"
TEXTO = "#1f2937"
BLANCO = "#ffffff"


# =========================================================
# CONFIGURACIÓN DE PÁGINA
# =========================================================

st.set_page_config(
    page_title="Preferencias de noticias",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# =========================================================
# CSS
# =========================================================

st.markdown(
    f"""
    <style>
    html, body, .stApp, [data-testid="stAppViewContainer"] {{
        background-color: {BLANCO} !important;
        color: {TEXTO} !important;
    }}

    [data-testid="stHeader"] {{
        background-color: transparent !important;
    }}

    .block-container {{
        max-width: 1180px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }}

    h1, h2, h3, h4, h5, h6, p, label, span, li {{
        color: {TEXTO} !important;
    }}

    .hero {{
        background: linear-gradient(135deg, {AZUL}, {AZUL_CLARO});
        padding: 2.3rem 2.7rem;
        border-radius: 26px;
        margin-bottom: 1.6rem;
        box-shadow: 0 12px 34px rgba(31, 78, 121, 0.22);
    }}

    .hero-title {{
        color: white !important;
        font-size: 2.4rem;
        font-weight: 850;
        margin-bottom: 0.8rem;
    }}

    .hero-text {{
        color: white !important;
        font-size: 1.08rem;
        line-height: 1.7;
        max-width: 900px;
    }}

    .info-card {{
        background-color: {AZUL_FONDO};
        border: 1px solid {AZUL_BORDE};
        border-radius: 18px;
        padding: 1rem 1.2rem;
        margin-bottom: 1.2rem;
        color: {AZUL} !important;
        font-weight: 700;
    }}

    .topic-badge {{
        display: inline-block;
        background-color: {AZUL_FONDO};
        color: {AZUL} !important;
        border: 1px solid {AZUL_BORDE};
        border-radius: 999px;
        padding: 0.45rem 0.8rem;
        margin: 0.25rem 0.25rem 0.25rem 0;
        font-weight: 700;
        font-size: 0.92rem;
    }}

    .topic-badge-custom {{
        display: inline-block;
        background-color: #eef6ff;
        color: #245f99 !important;
        border: 1px dashed #8bb8e8;
        border-radius: 999px;
        padding: 0.45rem 0.8rem;
        margin: 0.25rem 0.25rem 0.25rem 0;
        font-weight: 700;
        font-size: 0.92rem;
    }}

    .chat-user {{
        background-color: {AZUL};
        color: white !important;
        padding: 0.9rem 1rem;
        border-radius: 16px 16px 4px 16px;
        margin: 0.6rem 0 0.6rem auto;
        max-width: 78%;
        box-shadow: 0 5px 14px rgba(31, 78, 121, 0.16);
    }}

    .chat-user * {{
        color: white !important;
    }}

    .chat-note {{
        background-color: #ffffff;
        border-left: 4px solid {AZUL};
        padding: 0.7rem 0.9rem;
        margin: 0.8rem 0 1.2rem 0;
        color: #64748b !important;
        font-size: 0.95rem;
    }}

    [data-testid="stForm"] {{
        background-color: #ffffff !important;
        border: 1px solid {AZUL_BORDE} !important;
        border-radius: 22px !important;
        padding: 1.5rem !important;
        box-shadow: 0 8px 24px rgba(31, 78, 121, 0.07) !important;
    }}

    div[data-baseweb="input"] > div,
    div[data-baseweb="textarea"] > div {{
        background-color: #ffffff !important;
        border: 1.5px solid #cbd5e1 !important;
        border-radius: 13px !important;
        box-shadow: none !important;
        outline: none !important;
    }}

    div[data-baseweb="input"] > div:focus-within,
    div[data-baseweb="textarea"] > div:focus-within {{
        border: 2px solid {AZUL_CLARO} !important;
        box-shadow: 0 0 0 3px rgba(43, 123, 187, 0.12) !important;
        outline: none !important;
    }}

    input,
    textarea {{
        background-color: #ffffff !important;
        color: {TEXTO} !important;
        -webkit-text-fill-color: {TEXTO} !important;
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
    }}

    input::placeholder,
    textarea::placeholder {{
        color: #94a3b8 !important;
        -webkit-text-fill-color: #94a3b8 !important;
        opacity: 1 !important;
    }}

    div[data-baseweb="input"] button,
    div[data-baseweb="input"] button:hover,
    div[data-baseweb="input"] button:focus,
    div[data-baseweb="input"] button:active {{
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
    }}

    .stButton > button,
    .stFormSubmitButton > button {{
        background-color: {AZUL} !important;
        color: white !important;
        border: 1px solid {AZUL} !important;
        border-radius: 13px !important;
        padding: 0.7rem 1rem !important;
        font-weight: 800 !important;
        box-shadow: 0 6px 16px rgba(31, 78, 121, 0.20);
    }}

    .stButton > button:hover,
    .stFormSubmitButton > button:hover {{
        background-color: {AZUL_CLARO} !important;
        border-color: {AZUL_CLARO} !important;
        color: white !important;
    }}

    button[data-baseweb="tab"] {{
        color: #64748b !important;
        font-weight: 800 !important;
        font-size: 1rem !important;
    }}

    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {AZUL} !important;
    }}

    [data-baseweb="tab-highlight"] {{
        background-color: {AZUL} !important;
    }}

    [data-baseweb="tab-border"] {{
        background-color: #e5eef7 !important;
    }}

    [data-testid="stVerticalBlockBorderWrapper"] {{
        border: 1px solid {AZUL_BORDE} !important;
        border-radius: 22px !important;
        box-shadow: 0 8px 24px rgba(31, 78, 121, 0.07) !important;
        background-color: #ffffff !important;
    }}

    [data-testid="stAlert"] {{
        border-radius: 15px !important;
    }}
    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# FUNCIONES GOOGLE SHEETS
# =========================================================

def conectar_google_sheets():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")

    if not creds_json:
        raise ValueError("No se ha encontrado GOOGLE_CREDENTIALS_JSON en el archivo .env.")

    creds_dict = json.loads(creds_json)
    gc = gspread.service_account_from_dict(creds_dict)

    return gc


def obtener_hoja_usuarios():
    spreadsheet_id = os.getenv("ID_SPREADSHEET")

    if not spreadsheet_id:
        raise ValueError("No se ha encontrado ID_SPREADSHEET en el archivo .env.")

    gc = conectar_google_sheets()
    spreadsheet = gc.open_by_key(spreadsheet_id)

    hoja = spreadsheet.sheet1

    return hoja


def inicializar_hoja_usuarios_si_vacia(hoja):
    valores = hoja.get_all_values()

    if not valores:
        hoja.update("A1:G1", [COLUMNAS_USUARIOS])
        return

    cabecera = valores[0]

    if cabecera != COLUMNAS_USUARIOS:
        hoja.clear()
        hoja.update("A1:G1", [COLUMNAS_USUARIOS])


def cargar_usuarios():
    hoja = obtener_hoja_usuarios()
    inicializar_hoja_usuarios_si_vacia(hoja)

    registros = hoja.get_all_records()

    df = pd.DataFrame(registros, dtype=str)

    if df.empty:
        df = pd.DataFrame(columns=COLUMNAS_USUARIOS)

    for col in COLUMNAS_USUARIOS:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNAS_USUARIOS]
    df = df.fillna("")
    df = df.astype(str)

    return df


def guardar_usuarios(df):
    hoja = obtener_hoja_usuarios()

    df = df.copy()
    df = df.astype(str).fillna("")

    for col in COLUMNAS_USUARIOS:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNAS_USUARIOS]

    datos = [COLUMNAS_USUARIOS] + df.values.tolist()

    hoja.clear()
    hoja.update("A1", datos)


# =========================================================
# FUNCIONES AUXILIARES USUARIOS
# =========================================================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def usuario_existe(df, email):
    if df.empty:
        return False

    return email in df["email"].values


def verificar_password(df, email, password):
    password_hash = hash_password(password)
    usuario = df[df["email"] == email]

    if usuario.empty:
        return False

    password_guardada = usuario.iloc[0]["password_hash"]

    return password_hash == password_guardada


def obtener_usuario(df, email):
    usuario = df[df["email"] == email]

    if usuario.empty:
        return None

    return usuario.iloc[0]


def convertir_texto_a_lista(texto):
    if not isinstance(texto, str) or not texto.strip():
        return []

    return [
        topic.strip()
        for topic in texto.split(",")
        if topic.strip()
    ]


def convertir_lista_a_texto(lista):
    if not lista:
        return ""

    return ", ".join(lista)


def render_badges(topics, tipo="normal"):
    if not topics:
        st.write("No hay topics seleccionados.")
        return

    clase = "topic-badge" if tipo == "normal" else "topic-badge-custom"

    html_topics = ""

    for topic in topics:
        topic_seguro = html.escape(str(topic))
        html_topics += f"<span class='{clase}'>{topic_seguro}</span>"

    st.markdown(html_topics, unsafe_allow_html=True)


def guardar_o_actualizar_usuario(
    df,
    nombre,
    email,
    password,
    topics,
    topics_personalizados,
    recibir_email=True
):
    df = df.astype(str).fillna("")

    password_hash = hash_password(password)

    topics_str = convertir_lista_a_texto(topics)
    topics_personalizados_str = convertir_lista_a_texto(topics_personalizados)

    fecha_actualizacion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    nueva_fila = {
        "nombre": str(nombre),
        "email": str(email),
        "password_hash": str(password_hash),
        "topics": str(topics_str),
        "topics_personalizados": str(topics_personalizados_str),
        "recibir_email": str(recibir_email),
        "fecha_actualizacion": str(fecha_actualizacion)
    }

    if usuario_existe(df, email):
        for columna, valor in nueva_fila.items():
            df.loc[df["email"] == email, columna] = valor
    else:
        df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)

    guardar_usuarios(df)

    return df


# =========================================================
# FUNCIONES DEL CHAT DE NOTICIAS
# =========================================================

@st.cache_data(ttl=300)
def cargar_noticias_historicas():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    spreadsheet_id = os.getenv("ID_SPREADSHEET_CHAT")

    if not creds_json:
        raise ValueError("No se ha encontrado GOOGLE_CREDENTIALS_JSON en el archivo .env.")

    if not spreadsheet_id:
        raise ValueError("No se ha encontrado ID_SPREADSHEET_CHAT en el archivo .env.")

    creds_dict = json.loads(creds_json)
    gc = gspread.service_account_from_dict(creds_dict)

    spreadsheet = gc.open_by_key(spreadsheet_id)

    try:
        hoja = spreadsheet.worksheet("noticias")
    except Exception:
        hoja = spreadsheet.sheet1

    df = pd.DataFrame(hoja.get_all_records(), dtype=str)
    df = df.fillna("")
    df = df.astype(str)

    for col in COLUMNAS_NOTICIAS:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNAS_NOTICIAS]

    df["fecha_ejecucion_dt"] = pd.to_datetime(
        df["fecha_ejecucion"],
        errors="coerce",
        dayfirst=False
    )

    df = df.sort_values("fecha_ejecucion_dt", ascending=False, na_position="last")

    return df


def normalizar_texto(texto):
    texto = str(texto).lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9áéíóúñü\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def detectar_rango_temporal(pregunta):
    """
    Devuelve:
    - nombre_filtro
    - fecha_inicio
    - fecha_fin

    fecha_fin se usa como límite superior inclusivo.
    """
    pregunta_norm = normalizar_texto(pregunta)
    hoy = date.today()

    if any(exp in pregunta_norm for exp in ["hoy", "actualidad", "actuales", "ultimas noticias", "noticias recientes"]):
        return "hoy o ayer", hoy - timedelta(days=1), hoy

    if "ayer" in pregunta_norm:
        ayer = hoy - timedelta(days=1)
        return "ayer", ayer, ayer

    if any(exp in pregunta_norm for exp in ["esta semana", "semana", "ultimos 7 dias", "ultimas 7 dias"]):
        return "últimos 7 días", hoy - timedelta(days=7), hoy

    if any(exp in pregunta_norm for exp in ["este mes", "mes", "ultimos 30 dias", "ultimas 30 dias"]):
        return "últimos 30 días", hoy - timedelta(days=30), hoy

    patron = re.search(r"ultim[oa]s?\s+(\d+)\s+dias", pregunta_norm)
    if patron:
        n_dias = int(patron.group(1))
        return f"últimos {n_dias} días", hoy - timedelta(days=n_dias), hoy

    return "histórico completo", None, None


def filtrar_por_fecha(df_noticias, pregunta):
    nombre_filtro, fecha_inicio, fecha_fin = detectar_rango_temporal(pregunta)

    if fecha_inicio is None or fecha_fin is None:
        return df_noticias.copy(), nombre_filtro

    df = df_noticias.copy()

    df = df[df["fecha_ejecucion_dt"].notna()].copy()

    if df.empty:
        return df, nombre_filtro

    df["fecha_solo_dia"] = df["fecha_ejecucion_dt"].dt.date

    df = df[
        (df["fecha_solo_dia"] >= fecha_inicio) &
        (df["fecha_solo_dia"] <= fecha_fin)
    ].copy()

    return df, nombre_filtro


def extraer_keywords_pregunta(pregunta):
    pregunta_norm = normalizar_texto(pregunta)

    stopwords = {
        "que", "qué", "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas",
        "hay", "sobre", "noticias", "noticia", "cuentame", "cuéntame", "dime", "explica",
        "explicame", "explícame", "hoy", "ayer", "semana", "esta", "este", "mes",
        "ultimos", "ultimas", "dias", "dia", "por", "para", "con", "sin", "en", "y", "o",
        "a", "se", "lo", "me", "al", "ha", "han", "es", "son", "ha pasado", "pasado",
        "resumen", "resumeme", "hazme", "dame", "informacion", "información"
    }

    palabras = pregunta_norm.split()

    keywords = [
        p for p in palabras
        if len(p) >= 4 and p not in stopwords
    ]

    seen = set()
    keywords_unicas = []

    for k in keywords:
        if k not in seen:
            keywords_unicas.append(k)
            seen.add(k)

    return keywords_unicas


def calcular_relevancia_noticias(df_noticias, pregunta):
    df = df_noticias.copy()

    if df.empty:
        return df

    keywords = extraer_keywords_pregunta(pregunta)

    if not keywords:
        df["relevancia"] = 1
        return df

    def score_fila(fila):
        titulo = normalizar_texto(fila.get("titulo", ""))
        texto = normalizar_texto(fila.get("texto_completo", ""))
        periodico = normalizar_texto(fila.get("periodico", ""))

        score = 0

        for kw in keywords:
            if kw in titulo:
                score += 4
            if kw in texto:
                score += 1
            if kw in periodico:
                score += 2

        return score

    df["relevancia"] = df.apply(score_fila, axis=1)

    relevantes = df[df["relevancia"] > 0].copy()

    if relevantes.empty:
        return df.head(20).copy()

    relevantes = relevantes.sort_values(
        ["relevancia", "fecha_ejecucion_dt"],
        ascending=[False, False],
        na_position="last"
    )

    return relevantes


def recortar_texto(texto, max_caracteres=2500):
    texto = str(texto).strip()

    if len(texto) <= max_caracteres:
        return texto

    return texto[:max_caracteres].rsplit(" ", 1)[0] + "..."


def preparar_contexto_noticias(df_noticias, pregunta, max_noticias=25, max_caracteres_por_noticia=2500):
    if df_noticias.empty:
        return "No hay noticias disponibles en el histórico.", 0, "sin datos"

    df_filtrado_fecha, nombre_filtro = filtrar_por_fecha(df_noticias, pregunta)

    if df_filtrado_fecha.empty:
        return (
            f"No hay noticias disponibles para el filtro temporal solicitado: {nombre_filtro}.",
            0,
            nombre_filtro
        )

    df_relevante = calcular_relevancia_noticias(df_filtrado_fecha, pregunta)

    df_contexto = df_relevante.head(max_noticias).copy()

    if df_contexto.empty:
        return (
            f"No se han encontrado noticias relevantes para la pregunta dentro del filtro temporal: {nombre_filtro}.",
            0,
            nombre_filtro
        )

    bloques = []

    for i, (_, fila) in enumerate(df_contexto.iterrows(), start=1):
        fecha = str(fila.get("fecha_ejecucion", "")).strip()
        periodico = str(fila.get("periodico", "")).strip()
        titulo = str(fila.get("titulo", "")).strip()
        enlace = str(fila.get("enlace", "")).strip()
        texto_completo = recortar_texto(
            fila.get("texto_completo", ""),
            max_caracteres=max_caracteres_por_noticia
        )

        bloque = f"""
NOTICIA {i}
Fecha de ejecución: {fecha}
Periódico: {periodico}
Título: {titulo}
Enlace: {enlace}
Texto completo:
{texto_completo}
""".strip()

        bloques.append(bloque)

    contexto = "\n\n---\n\n".join(bloques)

    return contexto, len(df_contexto), nombre_filtro


def llamar_llama(mensajes):
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise ValueError("No se ha encontrado OPENROUTER_API_KEY en el archivo .env.")

    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "meta-llama/llama-3.3-70b-instruct",
        "messages": mensajes,
        "temperature": 0.0,
        "top_p": 0.2,
        "max_tokens": 1200
    }

    response = requests.post(url, headers=headers, json=data, timeout=90)

    if response.status_code != 200:
        raise RuntimeError(f"Error en OpenRouter: {response.status_code} - {response.text}")

    respuesta_json = response.json()

    return respuesta_json["choices"][0]["message"]["content"]


def pintar_mensaje_chat(role, content):
    if role == "user":
        contenido_seguro = html.escape(str(content)).replace("\n", "<br>")

        st.markdown(
            f"""
            <div class="chat-user">
                <strong>Tú</strong><br>
                {contenido_seguro}
            </div>
            """,
            unsafe_allow_html=True
        )

    else:
        with st.container(border=True):
            st.markdown("**Asistente**")
            st.markdown(content)


# =========================================================
# ESTADO DE SESIÓN
# =========================================================

if "logueado" not in st.session_state:
    st.session_state.logueado = False

if "email_usuario" not in st.session_state:
    st.session_state.email_usuario = None

if "nombre_usuario" not in st.session_state:
    st.session_state.nombre_usuario = None

if "password_usuario" not in st.session_state:
    st.session_state.password_usuario = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# =========================================================
# CABECERA
# =========================================================

st.markdown(
    f"""
    <div class="hero">
        <div class="hero-title">⚡FlashNews</div>
        <div class="hero-text">
            Configura tus intereses informativos, consulta tu perfil y conversa con un asistente
            basado únicamente en el histórico de noticias recopiladas.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# =========================================================
# CARGA DE USUARIOS DESDE GOOGLE SHEETS
# =========================================================

try:
    df_usuarios = cargar_usuarios()
except Exception as e:
    st.error("No se ha podido cargar la hoja de usuarios desde Google Sheets.")
    st.exception(e)
    st.stop()


# =========================================================
# LOGIN / REGISTRO
# =========================================================

if not st.session_state.logueado:

    col_login, col_info = st.columns([1.35, 0.75], gap="large")

    with col_login:
        with st.container(border=True):
            st.subheader("🔐 Inicio de sesión o registro")
            st.write(
                "Introduce tu nombre, email y contraseña. Si el email ya existe, se usará "
                "como inicio de sesión. Si no existe, se creará un nuevo perfil."
            )

            with st.form("form_login"):
                nombre = st.text_input("Nombre", placeholder="Ejemplo: Iyán")
                email = st.text_input("Email", placeholder="ejemplo@email.com")
                password = st.text_input("Contraseña", type="password")

                boton_login = st.form_submit_button(
                    "Entrar / Crear perfil",
                    use_container_width=True
                )

        if boton_login:
            if not nombre or not email or not password:
                st.error("Por favor, completa nombre, email y contraseña.")

            else:
                email = email.strip().lower()
                nombre = nombre.strip()

                if usuario_existe(df_usuarios, email):
                    if verificar_password(df_usuarios, email, password):
                        usuario = obtener_usuario(df_usuarios, email)

                        st.session_state.logueado = True
                        st.session_state.email_usuario = email
                        st.session_state.nombre_usuario = usuario["nombre"]
                        st.session_state.password_usuario = password

                        st.success("Inicio de sesión correcto.")
                        st.rerun()
                    else:
                        st.error("La contraseña no es correcta.")

                else:
                    st.session_state.logueado = True
                    st.session_state.email_usuario = email
                    st.session_state.nombre_usuario = nombre
                    st.session_state.password_usuario = password

                    st.success("Nuevo perfil iniciado. Ahora puedes configurar tus preferencias.")
                    st.rerun()

    with col_info:
        with st.container(border=True):
            st.subheader("✨ ¿Qué puedes hacer aquí?")
            st.write("✅ Crear un perfil de preferencias.")
            st.write("✅ Elegir temas de interés.")
            st.write("✅ Añadir topics personalizados.")
            st.write("✅ Consultar noticias recopiladas.")
            st.write("✅ Chatear con memoria durante la sesión.")


# =========================================================
# APP PRINCIPAL
# =========================================================

if st.session_state.logueado:

    tab_preferencias, tab_perfil, tab_chat = st.tabs(
        ["⚙️ Preferencias", "👤 Mi perfil", "💬 Chat de noticias"]
    )

    email_actual = st.session_state.email_usuario
    usuario_actual = obtener_usuario(df_usuarios, email_actual)

    if usuario_actual is not None:
        nombre_actual = usuario_actual["nombre"]
        topics_previos = convertir_texto_a_lista(usuario_actual["topics"])
        personalizados_previos = usuario_actual["topics_personalizados"]
        recibir_email_previo = str(usuario_actual["recibir_email"]).lower() == "true"
    else:
        nombre_actual = st.session_state.nombre_usuario
        topics_previos = []
        personalizados_previos = ""
        recibir_email_previo = True

    password_actual = st.session_state.password_usuario

    # =====================================================
    # TAB PREFERENCIAS
    # =====================================================

    with tab_preferencias:

        st.markdown(
            """
            <div class="info-card">
                Configura aquí los temas que más te interesan. Estos datos se guardarán en Google Sheets.
            </div>
            """,
            unsafe_allow_html=True
        )

        col_form, col_help = st.columns([1.35, 0.8], gap="large")

        with col_form:
            with st.container(border=True):
                st.subheader("⚙️ Configura tus intereses")
                st.write(
                    "Selecciona los temas sobre los que quieres recibir información. "
                    "También puedes añadir topics personalizados separados por comas."
                )

                with st.form("form_preferencias"):

                    st.markdown("### Topics disponibles")

                    topics_seleccionados = []

                    filas_topics = [
                        TOPICS_DISPONIBLES[i:i + 3]
                        for i in range(0, len(TOPICS_DISPONIBLES), 3)
                    ]

                    for fila in filas_topics:
                        cols = st.columns(3)

                        for i, topic in enumerate(fila):
                            with cols[i]:
                                seleccionado = st.checkbox(
                                    topic,
                                    value=topic in topics_previos,
                                    key=f"topic_{topic}"
                                )

                                if seleccionado:
                                    topics_seleccionados.append(topic)

                    st.write("")

                    ampliar = st.checkbox(
                        "Añadir otros topics personalizados",
                        value=bool(personalizados_previos)
                    )

                    if ampliar:
                        topics_personalizados_texto = st.text_area(
                            "Topics personalizados",
                            value=personalizados_previos,
                            placeholder="Ejemplo: vivienda, energía nuclear, inteligencia artificial, empleo juvenil"
                        )
                    else:
                        topics_personalizados_texto = ""

                    recibir_email = st.checkbox(
                        "Quiero recibir un resumen diario por email",
                        value=recibir_email_previo
                    )

                    boton_guardar = st.form_submit_button(
                        "💾 Guardar preferencias",
                        use_container_width=True
                    )

            if boton_guardar:
                topics_personalizados = convertir_texto_a_lista(topics_personalizados_texto)

                if not topics_seleccionados and not topics_personalizados:
                    st.error("Selecciona al menos un topic o añade uno personalizado.")

                else:
                    try:
                        df_usuarios = guardar_o_actualizar_usuario(
                            df=df_usuarios,
                            nombre=nombre_actual,
                            email=email_actual,
                            password=password_actual,
                            topics=topics_seleccionados,
                            topics_personalizados=topics_personalizados,
                            recibir_email=recibir_email
                        )

                        if recibir_email:
                            st.success("Preferencias guardadas correctamente en Google Sheets.")
                        else:
                            st.warning(
                                "Preferencias guardadas en Google Sheets. Has indicado que no quieres recibir el resumen diario por email."
                            )

                        st.rerun()

                    except Exception as e:
                        st.error("No se han podido guardar las preferencias en Google Sheets.")
                        st.exception(e)

        with col_help:
            with st.container(border=True):
                st.subheader("💡 Consejo")
                st.write(
                    "Los topics disponibles sirven para clasificar las noticias de forma general. "
                    "Los personalizados permiten afinar mucho más el resumen."
                )

                st.markdown("**Ejemplos de topics personalizados:**")
                st.markdown(
                    """
                    - Inteligencia artificial
                    - Vivienda
                    - Energía nuclear
                    - Empleo juvenil
                    - Mercado laboral
                    - Universidades
                    """
                )

            st.write("")

            with st.container(border=True):
                st.subheader("📌 Recomendación")
                st.write(
                    "Para obtener mejores resultados, combina temas generales con algunos "
                    "temas personalizados más concretos."
                )

    # =====================================================
    # TAB PERFIL
    # =====================================================

    with tab_perfil:

        try:
            df_actualizado = cargar_usuarios()
        except Exception as e:
            st.error("No se ha podido recargar la hoja de usuarios.")
            st.exception(e)
            df_actualizado = df_usuarios

        usuario_perfil = obtener_usuario(df_actualizado, email_actual)

        if usuario_perfil is None:

            with st.container(border=True):
                st.info("Todavía no has guardado tus preferencias.")

        else:
            nombre_perfil = str(usuario_perfil["nombre"])
            email_perfil = str(usuario_perfil["email"])
            estado_email = "Sí" if str(usuario_perfil["recibir_email"]).lower() == "true" else "No"

            topics_usuario = convertir_texto_a_lista(usuario_perfil["topics"])
            topics_personalizados_usuario = convertir_texto_a_lista(
                usuario_perfil["topics_personalizados"]
            )

            fecha_actualizacion = usuario_perfil["fecha_actualizacion"]

            if not fecha_actualizacion:
                fecha_actualizacion = "Todavía no hay fecha de actualización."

            col1, col2, col3 = st.columns(3, gap="medium")

            with col1:
                with st.container(border=True):
                    st.markdown("**Nombre**")
                    st.markdown(f"### {nombre_perfil}")

            with col2:
                with st.container(border=True):
                    st.markdown("**Email**")
                    st.markdown(f"### {email_perfil}")

            with col3:
                with st.container(border=True):
                    st.markdown("**Recibe email**")
                    st.markdown(f"### {estado_email}")

            st.write("")

            with st.container(border=True):
                st.markdown("## 👤 Mi perfil")

                st.markdown("### Topics seleccionados")
                render_badges(topics_usuario, tipo="normal")

                st.markdown("### Topics personalizados")
                render_badges(topics_personalizados_usuario, tipo="custom")

                st.markdown("### Última actualización")
                st.write(fecha_actualizacion)

    # =====================================================
    # TAB CHAT
    # =====================================================

    with tab_chat:

        with st.container(border=True):
            st.subheader("💬 Chat de noticias")
            st.write(
                "Pregunta sobre las noticias recopiladas. El asistente responderá usando únicamente "
                "las columnas reales del histórico: fecha_ejecucion, periodico, titulo, enlace y texto_completo."
            )

        st.markdown(
            """
            <div class="chat-note">
                Nota: el chat no inventa información externa. Solo responde con las noticias cargadas desde Google Sheets.
            </div>
            """,
            unsafe_allow_html=True
        )

        try:
            df_noticias = cargar_noticias_historicas()

            col_info_1, col_info_2 = st.columns(2)

            with col_info_1:
                st.markdown(
                    f"""
                    <div class="info-card">
                        🗞️ Noticias cargadas desde Google Sheets: {len(df_noticias)}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            with col_info_2:
                if not df_noticias.empty and df_noticias["fecha_ejecucion_dt"].notna().any():
                    ultima_fecha = df_noticias["fecha_ejecucion_dt"].max().strftime("%Y-%m-%d %H:%M:%S")
                else:
                    ultima_fecha = "No disponible"

                st.markdown(
                    f"""
                    <div class="info-card">
                        🕒 Última fecha de ejecución: {ultima_fecha}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            for msg in st.session_state.chat_history:
                pintar_mensaje_chat(msg["role"], msg["content"])

            with st.form("form_chat", clear_on_submit=True):
                pregunta = st.text_area(
                    "Escribe tu pregunta",
                    placeholder="Ejemplo: ¿Qué noticias hay hoy sobre tecnología? / ¿Qué ha pasado esta semana con la vivienda?",
                    height=100
                )

                col_enviar, col_limpiar = st.columns([0.75, 0.25])

                with col_enviar:
                    enviar = st.form_submit_button(
                        "Enviar pregunta",
                        use_container_width=True
                    )

                with col_limpiar:
                    limpiar = st.form_submit_button(
                        "Limpiar chat",
                        use_container_width=True
                    )

            if limpiar:
                st.session_state.chat_history = []
                st.rerun()

            if enviar:
                if not pregunta.strip():
                    st.warning("Escribe una pregunta primero.")
                else:
                    pregunta = pregunta.strip()

                    st.session_state.chat_history.append(
                        {"role": "user", "content": pregunta}
                    )

                    contexto, n_contexto, filtro_temporal = preparar_contexto_noticias(
                        df_noticias=df_noticias,
                        pregunta=pregunta,
                        max_noticias=25,
                        max_caracteres_por_noticia=2500
                    )

                    mensajes = [
                        {
                            "role": "system",
                            "content": f"""
Eres un asistente de noticias de FlashNews.

Tu única fuente de información es el HISTÓRICO DE NOTICIAS que aparece más abajo.

REGLAS OBLIGATORIAS:
1. No puedes usar conocimiento externo.
2. No puedes inventar datos, causas, cifras, nombres, fechas ni explicaciones que no estén en las noticias proporcionadas.
3. No puedes completar información con suposiciones.
4. Solo puedes responder usando los campos:
   - fecha_ejecucion
   - periodico
   - titulo
   - enlace
   - texto_completo
5. Si una noticia tiene poco texto, dilo claramente.
6. Si no hay información suficiente para responder, responde exactamente con esta idea:
   "No hay información suficiente en las noticias recopiladas para responder con detalle."
7. Si el usuario pregunta por "hoy", se han seleccionado noticias de hoy o de ayer como máximo.
8. Si el usuario pregunta por "esta semana", se han seleccionado noticias de los últimos 7 días.
9. No digas que has buscado en internet.
10. No menciones conocimiento externo ni fecha de corte.
11. Responde en español.
12. Usa Markdown limpio.
13. Cuando menciones una noticia, incluye:
   - título
   - periódico
   - fecha de ejecución
   - enlace si está disponible
14. Si el usuario pregunta "de qué trata", explica solo lo que se pueda deducir del texto_completo, no solo del título.
15. Si hay varias noticias relevantes, agrúpalas por tema.
16. Si el contexto dice que no hay noticias para ese filtro temporal, dilo claramente.

Filtro temporal aplicado: {filtro_temporal}
Número de noticias usadas como contexto: {n_contexto}

HISTÓRICO DE NOTICIAS:
{contexto}
"""
                        }
                    ] + st.session_state.chat_history[-8:]

                    with st.spinner("Analizando noticias..."):
                        respuesta = llamar_llama(mensajes)

                    st.session_state.chat_history.append(
                        {"role": "assistant", "content": respuesta}
                    )

                    st.rerun()

        except Exception as e:
            st.error("No se ha podido cargar el chat de noticias.")
            st.exception(e)