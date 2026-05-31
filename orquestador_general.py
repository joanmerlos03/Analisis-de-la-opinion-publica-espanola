"""
Orquestador centralizado de noticias con LangChain y OpenRouter (Llama 3.3 70B).
Adaptado nativamente para consumir funciones de scraping que devuelven DataFrames de Pandas.
"""

from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import os
import smtplib
from typing import Literal
from datetime import datetime

from dotenv import load_dotenv
import gspread
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import pandas as pd
from pydantic import BaseModel, Field

# IMPORTACIÓN DE TUS SCRAPERS REALES
from scrapers.elDiario_agente import*
from scrapers.elespanol_diario import*
from scrapers.scraper_larazon import *
from scrapers.scraper_publico import *
from scrapers.tercera_informacion_agente import *

load_dotenv(override=True)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODELO_POR_DEFECTO = "meta-llama/llama-3.3-70b-instruct"
TEMPERATURA_POR_DEFECTO = 0.3
NOMBRE_HOJA_NOTICIAS = "noticias"

# =====================================================================
# ALMACÉN GLOBAL EN MEMORIA (Para que el agente consulte textos largos)
# =====================================================================
POOL_NOTICIAS_COMPLETAS = {}


# =====================================================================
# 1. HERRAMIENTAS DEL AGENTE
# =====================================================================
class LeerNoticiaArgs(BaseModel):
    id_noticia: str = Field(
        description="Identificador único de la noticia (ej. 'n1', 'n2') que decides consultar a fondo."
    )


@tool("leer_texto_noticia", args_schema=LeerNoticiaArgs)
def leer_texto_noticia(id_noticia: str) -> str:
    """Tool que el agente DECIDE usar para obtener el texto completo de una noticia en memoria RAM."""
    return POOL_NOTICIAS_COMPLETAS.get(
        id_noticia, "Error: ID de noticia no encontrado."
    )


class EnviarEmailArgs(BaseModel):
    destinatario: str = Field(description="Email del usuario.")
    asunto: Literal["Noticias relevantes diarias"] = Field(
        description="Debe ser estrictamente 'Noticias relevantes diarias'."
    )
    cuerpo: str = Field(
        description="Código HTML final con las noticias curadas o el aviso de vacío."
    )


@tool("enviar_email", args_schema=EnviarEmailArgs)
def enviar_email(destinatario: str, asunto: str, cuerpo: str) -> str:
    """Tool para ejecutar el envío del correo final vía SMTP."""
    remitente = os.getenv("EMAIL_REMITENTE")
    password = os.getenv("EMAIL_PASSWORD")
    if not remitente or not password:
        return "Error: Credenciales SMTP no configuradas."

    msg = MIMEMultipart()
    msg["From"] = remitente
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo, "html"))
    try:
        servidor = smtplib.SMTP("smtp.gmail.com", 587)
        servidor.starttls()
        servidor.login(remitente, password)
        servidor.sendmail(remitente, destinatario, msg.as_string())
        servidor.quit()
        return f"Éxito: Correo enviado a {destinatario}."
    except Exception as exc:
        return f"Error SMTP: {exc}"


# =====================================================================
# 2. INICIALIZACIÓN DEL LLM Y AGENTE
# =====================================================================
def crear_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=MODELO_POR_DEFECTO,
        temperature=TEMPERATURA_POR_DEFECTO,
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=OPENROUTER_BASE_URL,
    )


def crear_agente() -> AgentExecutor:
    llm = crear_llm()
    herramientas = [leer_texto_noticia, enviar_email]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Eres un agente curador con capacidad de investigación. "
                "Recibes un listado de titulares. Sigue este razonamiento estricto:\n"
                "1. Analiza los titulares frente al perfil del usuario.\n"
                "2. Si un titular te parece potencialmente relevante pero necesitas verificar los detalles, DECIDES llamar a la herramienta 'leer_texto_noticia' pasándole su ID para leer el cuerpo completo.\n"
                "3. Puedes consultar tantas noticias como consideres necesario.\n"
                "4. Una vez tengas absoluta certeza de cuáles encajan, DEBES ejecutar 'enviar_email' para mandar el boletín HTML final.\n"
                "5. En el correo final NO debes enviar solo los títulos. Para cada noticia seleccionada debes incluir: título, resumen breve de 3-5 líneas y URL/enlace de la noticia.\n"
                "6. El cuerpo del email debe estar en HTML claro y legible. Usa encabezados, párrafos y enlaces clicables con <a href='URL'>Leer noticia completa</a>.\n"
                "7. Si no hay noticias relevantes para el usuario, envía igualmente un email indicando que hoy no se han encontrado noticias alineadas con sus intereses.",
            ),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    agente = create_tool_calling_agent(llm, herramientas, prompt)
    return AgentExecutor(
        agent=agente,
        tools=herramientas,
        verbose=True,
        handle_parsing_errors=True,
    )


# =====================================================================
# 3. FUNCIONES AUXILIARES Y DE CONEXIÓN
# =====================================================================

def ejecutar_scraper_seguro(
    nombre_fuente: str, funcion_scraper, **kwargs
) -> pd.DataFrame:
    """Ejecuta una función de scraping asegurando que siempre devuelva un DataFrame."""
    print(f"\n🔎 Consultando fuente: {nombre_fuente}")
    print(f"   Parámetros usados: {kwargs}")

    try:
        df = funcion_scraper(**kwargs)

        if not isinstance(df, pd.DataFrame):
            print(f"⚠️ {nombre_fuente} no devolvió un DataFrame. Intentando convertir...")
            df = pd.DataFrame(df)

        print(f"✅ {nombre_fuente}: scraper ejecutado correctamente.")
        print(f"   Noticias obtenidas: {len(df)}")
        print(f"   Columnas devueltas: {list(df.columns)}")

        if df.empty:
            print(f"⚠️ {nombre_fuente}: el DataFrame está vacío.")

        return df

    except Exception as e:
        print(f"❌ Fallo crítico en {nombre_fuente}: {type(e).__name__}: {e}")
        return pd.DataFrame() # Devuelve un DataFrame vacío si colapsa


def obtener_dataframe_usuarios() -> pd.DataFrame:
    creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
    gc = gspread.service_account_from_dict(creds_dict)
    hoja = gc.open_by_key(os.getenv("ID_SPREADSHEET")).sheet1
    return pd.DataFrame(hoja.get_all_records(), dtype=str)

def guardar_noticias_en_google_sheets(df_nuevas: pd.DataFrame) -> pd.DataFrame:
    """
    Guarda las noticias en un Google Sheets separado usando ID_SPREADSHEET_CHAT.
    Acumula histórico en la hoja, pone las noticias nuevas arriba,
    elimina duplicados y devuelve SOLO las noticias nuevas no duplicadas
    para que el agente trabaje únicamente con las noticias de esta ejecución.
    """
    print("\n💾 Iniciando guardado de noticias en Google Sheets...")

    id_spreadsheet_chat = os.getenv("ID_SPREADSHEET_CHAT")

    if not id_spreadsheet_chat:
        raise ValueError("No se encontró ID_SPREADSHEET_CHAT en las variables de entorno.")

    print("✅ ID_SPREADSHEET_CHAT encontrado.")

    creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
    gc = gspread.service_account_from_dict(creds_dict)
    spreadsheet = gc.open_by_key(id_spreadsheet_chat)

    print("✅ Conexión con Google Sheets realizada correctamente.")

    try:
        hoja_noticias = spreadsheet.worksheet(NOMBRE_HOJA_NOTICIAS)
        print(f"✅ Hoja '{NOMBRE_HOJA_NOTICIAS}' encontrada.")
    except gspread.WorksheetNotFound:
        print(f"⚠️ Hoja '{NOMBRE_HOJA_NOTICIAS}' no encontrada. Creándola...")
        hoja_noticias = spreadsheet.add_worksheet(
            title=NOMBRE_HOJA_NOTICIAS,
            rows=1000,
            cols=30
        )
        print(f"✅ Hoja '{NOMBRE_HOJA_NOTICIAS}' creada correctamente.")

    df_nuevas = df_nuevas.copy()

    fecha_ejecucion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df_nuevas["fecha_ejecucion"] = fecha_ejecucion

    print(f"🗓️ Fecha de ejecución añadida: {fecha_ejecucion}")
    print(f"📰 Noticias scrapeadas en esta ejecución: {len(df_nuevas)}")

    df_nuevas = df_nuevas.fillna("").astype(str)

    # Google Sheets no permite más de 50.000 caracteres por celda.
    # Recortamos textos largos para evitar errores al subir.
    MAX_CARACTERES_TEXTO = 30000

    if "texto_completo" in df_nuevas.columns:
        textos_largos = df_nuevas["texto_completo"].str.len() > MAX_CARACTERES_TEXTO
        print(f"✂️ Noticias con texto_completo recortado: {textos_largos.sum()}")

        df_nuevas.loc[textos_largos, "texto_completo"] = (
            df_nuevas.loc[textos_largos, "texto_completo"]
            .str.slice(0, MAX_CARACTERES_TEXTO)
            + "\n\n[Texto recortado por superar el límite de Google Sheets]"
        )
    
    if "enlace" in df_nuevas.columns:
        columna_duplicados = "enlace"
    elif "url" in df_nuevas.columns:
        columna_duplicados = "url"
    elif "titulo" in df_nuevas.columns:
        columna_duplicados = "titulo"
    else:
        columna_duplicados = None

    print(f"🔁 Columna usada para detectar duplicados: {columna_duplicados}")

    antes_dedup_interno = len(df_nuevas)

    if columna_duplicados:
        df_nuevas = df_nuevas.drop_duplicates(
            subset=[columna_duplicados],
            keep="first"
        )
    else:
        df_nuevas = df_nuevas.drop_duplicates(keep="first")

    print(f"🔁 Duplicados internos eliminados: {antes_dedup_interno - len(df_nuevas)}")

    print("📥 Leyendo histórico existente en Google Sheets...")
    registros_historicos = hoja_noticias.get_all_records()

    if registros_historicos:
        df_historico = pd.DataFrame(registros_historicos, dtype=str)
        df_historico = df_historico.fillna("").astype(str)
        print(f"📚 Noticias ya existentes en histórico: {len(df_historico)}")
    else:
        df_historico = pd.DataFrame()
        print("📚 Histórico vacío. Es la primera carga de noticias.")

    if not df_historico.empty and columna_duplicados and columna_duplicados in df_historico.columns:
        valores_historicos = set(df_historico[columna_duplicados].astype(str))
        df_nuevas_no_duplicadas = df_nuevas[
            ~df_nuevas[columna_duplicados].astype(str).isin(valores_historicos)
        ].copy()
    else:
        df_nuevas_no_duplicadas = df_nuevas.copy()

    print(f"🆕 Noticias realmente nuevas: {len(df_nuevas_no_duplicadas)}")
    print(f"🚫 Noticias descartadas por estar ya en histórico: {len(df_nuevas) - len(df_nuevas_no_duplicadas)}")

    if not df_historico.empty:
        df_total = pd.concat(
            [df_nuevas_no_duplicadas, df_historico],
            ignore_index=True
        )
    else:
        df_total = df_nuevas_no_duplicadas.copy()

def guardar_noticias_en_google_sheets(df_nuevas: pd.DataFrame) -> pd.DataFrame:
    """
    Guarda las noticias en un Google Sheets separado usando ID_SPREADSHEET_CHAT.
    Acumula histórico en la hoja, pone las noticias nuevas arriba,
    elimina duplicados y devuelve SOLO las noticias nuevas no duplicadas
    para que el agente trabaje únicamente con las noticias de esta ejecución.
    """
    print("\n💾 Iniciando guardado de noticias en Google Sheets...")

    id_spreadsheet_chat = os.getenv("ID_SPREADSHEET_CHAT")

    if not id_spreadsheet_chat:
        raise ValueError("No se encontró ID_SPREADSHEET_CHAT en las variables de entorno.")

    print("✅ ID_SPREADSHEET_CHAT encontrado.")

    creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
    gc = gspread.service_account_from_dict(creds_dict)
    spreadsheet = gc.open_by_key(id_spreadsheet_chat)

    print("✅ Conexión con Google Sheets realizada correctamente.")

    try:
        hoja_noticias = spreadsheet.worksheet(NOMBRE_HOJA_NOTICIAS)
        print(f"✅ Hoja '{NOMBRE_HOJA_NOTICIAS}' encontrada.")
    except gspread.WorksheetNotFound:
        print(f"⚠️ Hoja '{NOMBRE_HOJA_NOTICIAS}' no encontrada. Creándola...")
        hoja_noticias = spreadsheet.add_worksheet(
            title=NOMBRE_HOJA_NOTICIAS,
            rows=1000,
            cols=10
        )
        print(f"✅ Hoja '{NOMBRE_HOJA_NOTICIAS}' creada correctamente.")

    # =========================
    # 1. Preparar noticias nuevas
    # =========================
    df_nuevas = df_nuevas.copy()

    fecha_ejecucion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df_nuevas["fecha_ejecucion"] = fecha_ejecucion

    print(f"🗓️ Fecha de ejecución añadida: {fecha_ejecucion}")
    print(f"📰 Noticias scrapeadas en esta ejecución: {len(df_nuevas)}")

    df_nuevas = df_nuevas.fillna("").astype(str)

    # =========================
    # 2. Normalizar nombres de columnas
    # =========================

    # Si algún scraper usa url en vez de enlace
    if "enlace" not in df_nuevas.columns and "url" in df_nuevas.columns:
        df_nuevas["enlace"] = df_nuevas["url"]

    # Si algún scraper usa texto en vez de texto_completo
    if "texto_completo" not in df_nuevas.columns and "texto" in df_nuevas.columns:
        df_nuevas["texto_completo"] = df_nuevas["texto"]

    # Si falta alguna columna básica, la creamos vacía
    columnas_finales = [
        "fecha_ejecucion",
        "periodico",
        "titulo",
        "enlace",
        "texto_completo"
    ]

    for col in columnas_finales:
        if col not in df_nuevas.columns:
            df_nuevas[col] = ""

    # Nos quedamos SOLO con las columnas limpias que queremos guardar
    df_nuevas = df_nuevas[columnas_finales]

    print(f"🧱 Columnas finales de noticias nuevas: {list(df_nuevas.columns)}")

    # =========================
    # 3. Recorte inicial del texto completo
    # =========================
    MAX_CARACTERES_TEXTO = 30000

    textos_largos = df_nuevas["texto_completo"].str.len() > MAX_CARACTERES_TEXTO
    print(f"✂️ Noticias con texto_completo recortado: {textos_largos.sum()}")

    df_nuevas.loc[textos_largos, "texto_completo"] = (
        df_nuevas.loc[textos_largos, "texto_completo"]
        .str.slice(0, MAX_CARACTERES_TEXTO)
        + "\n\n[Texto recortado por superar el límite de Google Sheets]"
    )

    # =========================
    # 4. Eliminar duplicados internos
    # =========================
    columna_duplicados = "enlace"

    print(f"🔁 Columna usada para detectar duplicados: {columna_duplicados}")

    antes_dedup_interno = len(df_nuevas)

    # Si hay enlaces vacíos, no queremos que todas esas noticias se consideren duplicadas entre sí.
    # Para esas filas, usamos título como apoyo.
    df_nuevas["_clave_duplicado"] = df_nuevas["enlace"]

    enlaces_vacios = df_nuevas["_clave_duplicado"].str.strip() == ""
    df_nuevas.loc[enlaces_vacios, "_clave_duplicado"] = (
        df_nuevas.loc[enlaces_vacios, "titulo"].astype(str)
    )

    df_nuevas = df_nuevas.drop_duplicates(
        subset=["_clave_duplicado"],
        keep="first"
    )

    print(f"🔁 Duplicados internos eliminados: {antes_dedup_interno - len(df_nuevas)}")

    # =========================
    # 5. Leer histórico existente
    # =========================
    print("📥 Leyendo histórico existente en Google Sheets...")
    registros_historicos = hoja_noticias.get_all_records()

    if registros_historicos:
        df_historico = pd.DataFrame(registros_historicos, dtype=str)
        df_historico = df_historico.fillna("").astype(str)
        print(f"📚 Noticias ya existentes en histórico: {len(df_historico)}")
    else:
        df_historico = pd.DataFrame()
        print("📚 Histórico vacío. Es la primera carga de noticias.")

    # =========================
    # 6. Limpiar estructura del histórico antiguo
    # =========================
    if not df_historico.empty:

        # Si el histórico antiguo tenía url en vez de enlace
        if "enlace" not in df_historico.columns and "url" in df_historico.columns:
            df_historico["enlace"] = df_historico["url"]

        # Si el histórico antiguo tenía texto en vez de texto_completo
        if "texto_completo" not in df_historico.columns and "texto" in df_historico.columns:
            df_historico["texto_completo"] = df_historico["texto"]

        # Si falta alguna columna final, la creamos vacía
        for col in columnas_finales:
            if col not in df_historico.columns:
                df_historico[col] = ""

        # Nos quedamos SOLO con las columnas limpias
        df_historico = df_historico[columnas_finales]

        # Creamos clave de duplicado también para el histórico
        df_historico["_clave_duplicado"] = df_historico["enlace"]

        enlaces_vacios_hist = df_historico["_clave_duplicado"].str.strip() == ""
        df_historico.loc[enlaces_vacios_hist, "_clave_duplicado"] = (
            df_historico.loc[enlaces_vacios_hist, "titulo"].astype(str)
        )

    # =========================
    # 7. Detectar noticias nuevas respecto al histórico
    # =========================
    if not df_historico.empty:
        valores_historicos = set(df_historico["_clave_duplicado"].astype(str))

        df_nuevas_no_duplicadas = df_nuevas[
            ~df_nuevas["_clave_duplicado"].astype(str).isin(valores_historicos)
        ].copy()
    else:
        df_nuevas_no_duplicadas = df_nuevas.copy()

    print(f"🆕 Noticias realmente nuevas: {len(df_nuevas_no_duplicadas)}")
    print(
        f"🚫 Noticias descartadas por estar ya en histórico: "
        f"{len(df_nuevas) - len(df_nuevas_no_duplicadas)}"
    )

    # =========================
    # 8. Construir histórico actualizado
    # =========================
    if not df_historico.empty:
        df_total = pd.concat(
            [df_nuevas_no_duplicadas, df_historico],
            ignore_index=True
        )
    else:
        df_total = df_nuevas_no_duplicadas.copy()

    df_total = df_total.fillna("").astype(str)

    # Eliminamos la columna auxiliar antes de guardar en Google Sheets
    if "_clave_duplicado" in df_total.columns:
        df_total = df_total.drop(columns=["_clave_duplicado"])

    if "_clave_duplicado" in df_nuevas_no_duplicadas.columns:
        df_nuevas_no_duplicadas = df_nuevas_no_duplicadas.drop(columns=["_clave_duplicado"])

    # Volvemos a forzar estructura final limpia
    for col in columnas_finales:
        if col not in df_total.columns:
            df_total[col] = ""

    df_total = df_total[columnas_finales]

    for col in columnas_finales:
        if col not in df_nuevas_no_duplicadas.columns:
            df_nuevas_no_duplicadas[col] = ""

    df_nuevas_no_duplicadas = df_nuevas_no_duplicadas[columnas_finales]

    print(f"🧱 Columnas finales que se guardarán en Sheets: {list(df_total.columns)}")

    # =========================
    # 9. Recorte FINAL de seguridad sobre df_total
    # =========================
    MAX_CARACTERES_CELDA = 30000

    celdas_recortadas = []

    for col in df_total.columns:
        longitudes = df_total[col].astype(str).str.len()
        filas_largas = longitudes[longitudes > MAX_CARACTERES_CELDA]

        if not filas_largas.empty:
            for idx, longitud in filas_largas.items():
                celdas_recortadas.append((idx, col, longitud))

            df_total[col] = df_total[col].astype(str).str.slice(0, MAX_CARACTERES_CELDA)

    print(f"✂️ Celdas recortadas antes de subir a Sheets: {len(celdas_recortadas)}")

    for idx, col, longitud in celdas_recortadas[:10]:
        print(f"   - Fila {idx}, columna '{col}', longitud original: {longitud}")

    if len(celdas_recortadas) > 10:
        print(f"   ... y {len(celdas_recortadas) - 10} celdas largas más.")

    # =========================
    # 10. Guardar histórico actualizado en Google Sheets
    # =========================
    print(f"📦 Total de noticias que quedarán guardadas en Sheets: {len(df_total)}")

    print("🧹 Limpiando hoja anterior...")
    hoja_noticias.clear()

    if not df_total.empty:
        print("⬆️ Subiendo histórico actualizado a Google Sheets...")
        hoja_noticias.update(
            [df_total.columns.tolist()] + df_total.values.tolist()
        )
        print("✅ Histórico actualizado correctamente en Google Sheets.")
    else:
        print("⚠️ No hay noticias para guardar en Google Sheets.")

    # =========================
    # 11. Devolver SOLO noticias nuevas para el agente
    # =========================
    return df_nuevas_no_duplicadas

# =====================================================================
# 4. FLUJO PRINCIPAL DE EJECUCIÓN
# =====================================================================
def main():
    print(f"\n--- 🚀 INICIANDO ORQUESTADOR CENTRAL ({MODELO_POR_DEFECTO}) ---")
    global POOL_NOTICIAS_COMPLETAS

    # A. Volcado de noticias (Capturando DataFrames con parámetros explícitos)
    dfs_recopilados = []

    # Llamada 1
    dfs_recopilados.append(
        ejecutar_scraper_seguro(
            "Periódico 1", scrape_elespanol_opinion, max_paginas=8, max_articulos=10, espera=0.5
        )
    )

    # Llamada 2
    dfs_recopilados.append(
        ejecutar_scraper_seguro(
            "Periódico 2", scrape_larazon_opinion, objetivo=10, headless=True, paginas_max=30
        )
    )

    # Llamada 3
    dfs_recopilados.append(
        ejecutar_scraper_seguro("Periódico 3", scrape_opinion_articles_hoy, limit = 10, target_date= None)
    )

    # Llamada 4
    dfs_recopilados.append(
        ejecutar_scraper_seguro(
            "Periódico 4", extraer_noticias_publico, max_noticias=10
        )
    )

    # Llamada 5
    dfs_recopilados.append(
        ejecutar_scraper_seguro("Periódico 5", scrape_tercerainformacion, 
                                max_items=10, 
                                max_pages=300, 
                                min_delay=1.5,
                                max_delay = 3.0,
                                timeout = 20,
                                headers = None,
                                verbose= True,))

    # Filtramos DataFrames vacíos por seguridad
    dfs_validos = [df for df in dfs_recopilados if not df.empty]

    print(f"\n📊 DataFrames recopilados: {len(dfs_recopilados)}")
    print(f"📊 DataFrames válidos no vacíos: {len(dfs_validos)}")

    if not dfs_validos:
        print("❌ Todas las fuentes fallaron o devolvieron DataFrames vacíos.")
        return

    # Unificamos todos los DataFrames en un único dataset maestro
    df_pool = pd.concat(dfs_validos, ignore_index=True)
    
    print("\n DataFrames unidos correctamente.")
    print(f"   Total de noticias antes de guardar en Sheets: {len(df_pool)}")
    print(f"   Columnas disponibles en df_pool: {list(df_pool.columns)}")

    # Guardamos/acumulamos noticias en Google Sheets usando ID_SPREADSHEET_CHAT
    try:
        df_pool = guardar_noticias_en_google_sheets(df_pool)
    except Exception as exc:
        print(f"⚠️ Error guardando noticias en Google Sheets: {exc}")
        print("⚠️ El agente continuará solo con las noticias de esta ejecución.")

    print(
        f"📥 Volcado masivo completado: {len(df_pool)} noticias disponibles en el DataFrame."
    )

    if df_pool.empty:
        print("ℹ️ No hay noticias nuevas respecto al histórico guardado en Google Sheets.")

    # Preparamos las estructuras para la memoria del Agente
    menu_ligero_noticias = []
    POOL_NOTICIAS_COMPLETAS.clear()
    print("\n Preparando noticias para el agente...")
    print(f"   Noticias que recibirá el agente: {len(df_pool)}")

    # Asumimos que tus DataFrames tienen columnas llamadas 'titulo', 'enlace' y 'texto_completo'
    for idx, fila in df_pool.iterrows():
        id_noticia = f"n{idx+1}"

        titulo = fila.get("titulo", "Sin título")
        enlace = fila.get("enlace", "")
        texto_completo = fila.get("texto_completo", "Sin contenido disponible.")

        if not enlace:
            print(f"⚠️ Noticia {id_noticia} sin enlace: {titulo}")

        if texto_completo == "Sin contenido disponible.":
            print(f"⚠️ Noticia {id_noticia} sin texto completo: {titulo}")

        menu_ligero_noticias.append(
            {
                "id": id_noticia,
                "titulo": str(titulo),
                "url": str(enlace)
            }
        )

        POOL_NOTICIAS_COMPLETAS[id_noticia] = (
            f"Título: {titulo}\n"
            f"URL: {enlace}\n\n"
            f"Texto completo:\n{texto_completo}"
        )

    # B. Carga de usuarios desde Google Sheets
    try:
        df_usuarios = obtener_dataframe_usuarios()
        print("\n👥 Usuarios cargados desde Google Sheets.")
        print(f"   Total usuarios encontrados: {len(df_usuarios)}")
        print(f"   Columnas usuarios: {list(df_usuarios.columns)}")
    except Exception as exc:
        print(f"❌ Error descargando preferencias: {exc}")
        return

    # C. Ejecución del Agente
    agente_executor = crear_agente()

    for _, usuario in df_usuarios.iterrows():
        nombre = usuario.get("nombre", "Usuario")
        email = usuario.get("email", "")
        topics = usuario.get("topics", "")
        topics_pers = usuario.get("topics_personalizados", "")
        recibir_email = usuario.get("recibir_email", "True")

        if not email:
            print(f"⚠️ Usuario omitido porque no tiene email: {nombre}")
            continue

        if recibir_email.lower() == "false":
            print(f"⏭️ Usuario omitido porque recibir_email=False: {email}")
            continue

        print(f"\n🧠 Agente investigando para: {email}")
        print(f"   Nombre: {nombre}")
        print(f"   Topics generales: {topics}")
        print(f"   Topics personalizados: {topics_pers}")

        instruccion = (
            f"Usuario: {nombre} ({email})\n"
            f"- Temas generales: {topics}\n"
            f"- Intereses específicos: {topics_pers}\n\n"
            f"Titulares de hoy disponibles para consulta:\n{json.dumps(menu_ligero_noticias, ensure_ascii=False, indent=2)}\n\n"
            f"Mando: Revisa los titulares. Si alguno promete pero necesitas confirmar, DECIDES usar 'leer_texto_noticia' con su ID. "
            f"Al finalizar tu investigación, DEBES usar 'enviar_email' para mandar el reporte final. "
            f"El correo debe incluir, para cada noticia relevante: título, resumen breve basado en el texto completo y URL de la noticia. "
            f"No envíes únicamente una lista de titulares."
        )

        try:
            resultado = agente_executor.invoke({"input": instruccion})
            print(f"✅ Agente finalizado correctamente para {email}.")
            print(f"   Resultado agente: {resultado}")
        except Exception as exc:
            print(f"❌ Fallo en agente para {email}: {exc}")

    print("\n--- 🏁 PROCESO FINALIZADO ---")


if __name__ == "__main__":
    main()