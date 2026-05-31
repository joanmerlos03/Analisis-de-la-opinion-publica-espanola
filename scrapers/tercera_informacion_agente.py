"""
Scraper de la sección de Opinión de Tercera Información.

Este archivo está basado en el notebook original que funcionaba, pero adaptado
para poder importarlo desde otro archivo, un notebook o un agente.

Uso desde otro archivo/notebook:
    from tercera_informacion_agente import scrape_tercerainformacion
    df = scrape_tercerainformacion(max_items=10)

Uso desde terminal:
    python tercera_informacion_agente.py
"""

from __future__ import annotations

import json
import random
import time
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


# ---------------------------------------------------------------------------
# Configuración base
# ---------------------------------------------------------------------------

START_URL = "https://www.tercerainformacion.es/opinion/"

MAX_ITEMS = 10
MAX_PAGES = 300
MIN_DELAY = 1.5
MAX_DELAY = 3.0
TIMEOUT = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:150.0) "
        "Gecko/20100101 Firefox/150.0"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Connection": "keep-alive",
}


# ---------------------------------------------------------------------------
# Utilidades generales
# ---------------------------------------------------------------------------

def limpiar_texto(txt: str | None) -> str:
    if not txt:
        return ""
    return " ".join(txt.replace("\n", " ").replace("\t", " ").split())


def dormir(min_delay: float = MIN_DELAY, max_delay: float = MAX_DELAY) -> None:
    time.sleep(random.uniform(min_delay, max_delay))


def pedir_sopa(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = TIMEOUT,
) -> BeautifulSoup:
    headers = headers or HEADERS

    r = requests.get(url, headers=headers, timeout=timeout)

    if r.status_code in [403, 429]:
        raise RuntimeError(
            f"El sitio devolvió {r.status_code}. "
            "Se detiene para evitar forzar el acceso."
        )

    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def es_url_tercera(url: str) -> bool:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc.endswith("tercerainformacion.es")
    except Exception:
        return False


def parece_articulo_opinion(url: str) -> bool:
    path = urlparse(url).path.lower()

    if not es_url_tercera(url):
        return False

    # Los artículos de opinión suelen ir dentro de /opinion/
    if not path.startswith("/opinion/"):
        return False

    # Evita páginas de paginación/listado
    if "/page/" in path:
        return False

    if any(x in path for x in [
        "/tag/",
        "/tags/",
        "/author/",
        "/autor/",
        "/autores/",
        "/category/",
        "/wp-content/",
        "/feed/",
        "/rss",
        "/xml",
        "/comentarios",
        "/contacto",
        "/colabora",
        "/anunciate",
        "/informacion-legal",
        "/politica-privacidad",
        "/cookies",
    ]):
        return False

    # Evita la portada /opinion/
    partes = [p for p in path.split("/") if p]
    if len(partes) < 2:
        return False

    return True


def es_basura(txt: str) -> bool:
    txt_lower = txt.lower()

    basura = [
        "whatsapp",
        "facebook",
        "twitter",
        "x.com",
        "linkedin",
        "telegram",
        "newsletter",
        "suscríbete",
        "suscribete",
        "iniciar sesión",
        "inicia sesión",
        "regístrate",
        "mostrar comentarios",
        "lee también",
        "lo más leído",
        "última hora",
        "publicidad",
        "aviso legal",
        "política de privacidad",
        "política de cookies",
        "copyright",
        "recibe las noticias",
        "todas las noticias publicadas",
        "compartir",
        "comparte",
        "síguenos",
        "seguir leyendo",
        "te puede interesar",
        "otras noticias",
        "newsletter diaria",
        "boletín",
        "comentarios",
        "normas de participación",
        "personaliza tus cookies",
        "una publicación de",
        "queda prohibida toda reproducción",
        "tercera información",
        "margenblanco",
        "estudio nexos",
    ]

    return any(b in txt_lower for b in basura)


# ---------------------------------------------------------------------------
# Extracción de URLs desde listados
# ---------------------------------------------------------------------------

def extraer_urls_listado(
    soup: BeautifulSoup,
    page_url: str,
) -> list[dict[str, str]]:
    articulos = []
    vistos = set()

    for a in soup.find_all("a", href=True):
        url = urljoin(page_url, a["href"])
        titulo = limpiar_texto(a.get_text(" ", strip=True))

        if len(titulo) < 8:
            continue

        if not parece_articulo_opinion(url):
            continue

        if url in vistos:
            continue

        vistos.add(url)

        articulos.append({
            "titulo_listado": titulo,
            "url": url,
        })

    return articulos


# ---------------------------------------------------------------------------
# Extracción de texto de artículos
# ---------------------------------------------------------------------------

def extraer_texto_jsonld(soup: BeautifulSoup) -> str:
    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts:
        contenido = script.string

        if not contenido:
            continue

        try:
            data = json.loads(contenido)
        except Exception:
            continue

        candidatos = []

        if isinstance(data, dict):
            candidatos.append(data)

            if "@graph" in data and isinstance(data["@graph"], list):
                candidatos.extend(data["@graph"])

        elif isinstance(data, list):
            candidatos.extend(data)

        for item in candidatos:
            if not isinstance(item, dict):
                continue

            body = item.get("articleBody") or item.get("description")

            if body:
                body = limpiar_texto(body)

                if len(body) >= 200:
                    return body

    return ""


def extraer_parrafos_html(soup: BeautifulSoup) -> str:
    selectores = [
        "article p",
        "main article p",
        "main p",
        ".entry-content p",
        ".post-content p",
        ".article-content p",
        ".article-body p",
        ".content p",
        ".texto p",
        ".noticia p",
        ".noticia-texto p",
        ".contenido p",
        "#content p",
        "#main p",
    ]

    for selector in selectores:
        encontrados = soup.select(selector)

        if len(encontrados) < 2:
            continue

        textos = []

        for p in encontrados:
            txt = limpiar_texto(p.get_text(" ", strip=True))

            if len(txt) < 35:
                continue

            if es_basura(txt):
                continue

            textos.append(txt)

        texto = " ".join(textos).strip()

        if len(texto) >= 200:
            return texto

    return ""


def extraer_todos_los_parrafos(soup: BeautifulSoup) -> str:
    parrafos = []

    for p in soup.find_all("p"):
        txt = limpiar_texto(p.get_text(" ", strip=True))

        if len(txt) < 35:
            continue

        if es_basura(txt):
            continue

        parrafos.append(txt)

    return " ".join(parrafos).strip()


def extraer_articulo(
    url: str,
    titulo_listado: str = "",
    headers: dict[str, str] | None = None,
    timeout: int = TIMEOUT,
) -> dict[str, str] | None:
    soup = pedir_sopa(url, headers=headers, timeout=timeout)

    h1 = soup.find("h1")
    titulo = limpiar_texto(h1.get_text(" ", strip=True)) if h1 else titulo_listado

    texto_completo = extraer_texto_jsonld(soup)

    if len(texto_completo) < 200:
        texto_completo = extraer_parrafos_html(soup)

    if len(texto_completo) < 200:
        texto_completo = extraer_todos_los_parrafos(soup)

    texto_completo = limpiar_texto(texto_completo)

    if len(texto_completo) < 200:
        return None

    if not titulo:
        titulo = "Sin título"

    return {
        "periodico": "Tercera Información",
        "titulo": titulo,
        "texto": texto_completo,
        "url": url,
    }


# ---------------------------------------------------------------------------
# Generación de listados
# ---------------------------------------------------------------------------

def generar_urls_listado(
    start_url: str = START_URL,
    max_pages: int = MAX_PAGES,
) -> list[str]:
    urls = [start_url]

    for page in range(2, max_pages + 1):
        urls.append(f"https://www.tercerainformacion.es/opinion/page/{page}/")

    return urls


# ---------------------------------------------------------------------------
# Función principal para importar desde agente/notebook
# ---------------------------------------------------------------------------

def scrape_tercerainformacion(
    max_items: int = MAX_ITEMS,
    max_pages: int = MAX_PAGES,
    min_delay: float = MIN_DELAY,
    max_delay: float = MAX_DELAY,
    timeout: int = TIMEOUT,
    headers: dict[str, str] | None = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Scrapea artículos de opinión de Tercera Información.

    Esta función mantiene la lógica del notebook original, pero permite usarla
    desde otro archivo o desde un agente sin que se ejecute automáticamente.

    Args:
        max_items: número máximo de artículos a recoger.
        max_pages: número máximo de páginas de listado a revisar.
        min_delay: espera mínima entre peticiones.
        max_delay: espera máxima entre peticiones.
        timeout: timeout de requests.
        headers: cabeceras HTTP. Si es None, usa HEADERS.
        verbose: si True, imprime el progreso.

    Returns:
        DataFrame con columnas: periodico, titulo, texto, url.
    """
    datos: list[dict[str, str]] = []
    articulos_vistos: set[str] = set()
    paginas_sin_nuevos = 0
    headers = headers or HEADERS

    urls_listado = generar_urls_listado(max_pages=max_pages)

    for current_url in urls_listado:
        if len(datos) >= max_items:
            break

        if verbose:
            print(f"\nPágina listado: {current_url}")

        try:
            soup = pedir_sopa(current_url, headers=headers, timeout=timeout)

        except Exception as e:
            if verbose:
                print(f"Error al descargar listado: {e}")

            paginas_sin_nuevos += 1

            if paginas_sin_nuevos >= 10:
                if verbose:
                    print("Demasiadas páginas seguidas sin resultados. Se detiene.")
                break

            continue

        articulos = extraer_urls_listado(soup, current_url)

        if verbose:
            print("URLs encontradas:", len(articulos))

        if len(articulos) == 0:
            paginas_sin_nuevos += 1

            if paginas_sin_nuevos >= 10:
                if verbose:
                    print("Demasiadas páginas seguidas sin artículos. Se detiene.")
                break

            continue

        nuevos = 0

        iterator = tqdm(articulos, desc="Entrando en artículos") if verbose else articulos

        for item in iterator:
            url = item["url"]

            if url in articulos_vistos:
                continue

            articulos_vistos.add(url)

            try:
                articulo = extraer_articulo(
                    url=url,
                    titulo_listado=item["titulo_listado"],
                    headers=headers,
                    timeout=timeout,
                )

            except Exception as e:
                if verbose:
                    print(f"Error en artículo {url}: {e}")
                continue

            if articulo is None:
                continue

            datos.append(articulo)
            nuevos += 1

            if len(datos) >= max_items:
                break

            dormir(min_delay=min_delay, max_delay=max_delay)

        if verbose:
            print(f"Añadidos en este listado: {nuevos}")
            print(f"Total acumulado: {len(datos)}")

        if nuevos == 0:
            paginas_sin_nuevos += 1
        else:
            paginas_sin_nuevos = 0

        if paginas_sin_nuevos >= 10:
            if verbose:
                print("Demasiadas páginas seguidas sin nuevos artículos. Se detiene.")
            break

        dormir(min_delay=min_delay, max_delay=max_delay)

    df = pd.DataFrame(datos)

    if not df.empty:
        df = df.drop_duplicates(subset=["url"])
        df = df[["periodico", "titulo", "texto", "url"]]
    else:
        df = pd.DataFrame(columns=["periodico", "titulo", "texto", "url"])

    if verbose:
        print(f"\nFilas finales: {len(df)}")

    return df


# ---------------------------------------------------------------------------
# Ejecución directa opcional
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    df_tercera = scrape_tercerainformacion(
        max_items=MAX_ITEMS,
        max_pages=MAX_PAGES,
    )

    print(df_tercera.head())