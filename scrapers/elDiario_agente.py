"""
Scraper eldiario.es opinión — versión para agente.

Función `scrape_opinion_articles_hoy()` que obtiene hasta N artículos de
opinión publicados el día actual (filtrando por `lastmod` del sitemap)
y los devuelve como pandas.DataFrame.
"""

from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass, asdict
from datetime import date
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

BASE_URL = "https://www.eldiario.es"
PERIODICO = "eldiario.es"
SITEMAP_URL_TPL = "https://www.eldiario.es/sitemap_contents_{year}_{month:02d}_25b87_001.xml"

REQUEST_TIMEOUT = 30
SLEEP_BETWEEN_REQS = (0.8, 1.6)
RETRIES = 3

# Prefijos de URL que consideramos "opinión".
OPINION_PATH_PATTERNS = [
    re.compile(r"^/opinion/"),
    re.compile(r"^/contracorriente/"),
    re.compile(r"^/piedrasdepapel/"),
    re.compile(r"^/contrapoder/"),
    re.compile(r"^/cienciacritica/"),
    re.compile(r"^/caballodenietzsche/"),
    re.compile(r"^/ultima-llamada/"),
    re.compile(r"^/arsenioescolar/"),
    re.compile(r"^/retrones/"),
    re.compile(r"^/[^/]+/desdeelsur/"),
    re.compile(r"^/[^/]+/blog/opinion/"),
    re.compile(r"^/[^/]+/lacontradejaen/"),
    re.compile(r"^/[^/]+/canarias-opina/"),
    re.compile(r"^/[^/]+/murcia-y-aparte/"),
    re.compile(r"^/[^/]+/blogs/piedra-de-toque/"),
    re.compile(r"^/madrid/somos/.*opinion"),
    re.compile(r"^/aragon/el-prismatico/"),
]

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# Logging y sesión HTTP
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("eldiario")

session = requests.Session()
session.headers.update(
    {
        "User-Agent": USER_AGENT,
        "Accept-Language": "es-ES,es;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
)


def polite_sleep() -> None:
    time.sleep(random.uniform(*SLEEP_BETWEEN_REQS))


def fetch(url: str) -> str | None:
    for attempt in range(1, RETRIES + 1):
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                return r.text
            if r.status_code in (404, 410):
                return None
            log.warning("HTTP %s en %s (intento %d)", r.status_code, url, attempt)
        except requests.RequestException as e:
            log.warning("Error de red en %s: %s (intento %d)", url, e, attempt)
        time.sleep(2 ** attempt)
    return None


# ---------------------------------------------------------------------------
# Sitemaps
# ---------------------------------------------------------------------------

URL_BLOCK_RE = re.compile(r"<url\b[^>]*>(.*?)</url>", re.DOTALL)
LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
LASTMOD_RE = re.compile(r"<lastmod>([^<]+)</lastmod>")


def is_opinion_url(url: str) -> bool:
    path = urlparse(url).path
    return any(p.search(path) for p in OPINION_PATH_PATTERNS)


def parse_sitemap_for_opinion(xml: str) -> list[tuple[str, str]]:
    """Devuelve [(url, lastmod), ...] solo para URLs de opinión."""
    out: list[tuple[str, str]] = []
    for m in URL_BLOCK_RE.finditer(xml):
        block = m.group(1)
        loc_m = LOC_RE.search(block)
        if not loc_m:
            continue
        url = loc_m.group(1).strip()
        if not is_opinion_url(url):
            continue
        lastmod_m = LASTMOD_RE.search(block)
        lastmod = lastmod_m.group(1).strip() if lastmod_m else ""
        out.append((url, lastmod))
    return out


# ---------------------------------------------------------------------------
# Detección paywall y extracción de artículo
# ---------------------------------------------------------------------------

PAYWALL_HTML_SELECTORS = [
    '[class*="paywall" i]',
    '[class*="premium" i]',
    '[id*="paywall" i]',
]
PAYWALL_TEXT_MARKERS = (
    "exclusivo para socios",
    "contenido exclusivo para socios",
    "este artículo es exclusivo",
    "para seguir leyendo, hazte socio",
    "para seguir leyendo, hazte socia",
)


def is_paywalled(soup: BeautifulSoup) -> bool:
    for sel in PAYWALL_HTML_SELECTORS:
        if soup.select_one(sel):
            return True
    article = soup.find("article") or soup.find("main") or soup
    text_low = article.get_text(" ", strip=True).lower()[:6000]
    return any(m in text_low for m in PAYWALL_TEXT_MARKERS)


@dataclass
class Article:
    periodico: str
    titulo: str
    texto: str
    url: str


def extract_article(url: str, html: str) -> Article | None:
    soup = BeautifulSoup(html, "lxml")
    if is_paywalled(soup):
        return None

    h1 = soup.find("h1")
    if not h1:
        return None
    titulo = h1.get_text(" ", strip=True)
    if not titulo:
        return None

    container = soup.find("article") or soup.find("main") or soup
    for sel in [
        "header", "footer", "nav", "aside",
        ".related", ".relacionadas", ".newsletter",
        ".tags", ".share", ".comments", "[class*='comment']",
        "script", "style", "noscript",
    ]:
        for tag in container.select(sel):
            tag.decompose()

    paragraphs: list[str] = []
    for p in container.find_all("p"):
        txt = p.get_text(" ", strip=True)
        if not txt or len(txt) < 25:
            continue
        low = txt.lower()
        if any(k in low for k in ("hazte socio", "hazte socia", "suscríbete a la newsletter")):
            continue
        paragraphs.append(txt)

    texto = "\n\n".join(paragraphs).strip()
    if len(texto) < 150:
        return None

    return Article(periodico=PERIODICO, titulo=titulo, texto=texto, url=url)


# ---------------------------------------------------------------------------
# Función principal para el agente
# ---------------------------------------------------------------------------

DF_COLUMNS = ["periodico", "titulo", "texto", "url"]


def scrape_opinion_articles_hoy(
    limit: int = 10,
    target_date: date | None = None,
) -> pd.DataFrame:
    """
    Obtiene hasta `limit` artículos de opinión de eldiario.es publicados
    el día indicado (por defecto, hoy) y los devuelve como DataFrame.

    Args:
        limit: número máximo de artículos a recoger (por defecto 10).
        target_date: fecha objetivo. Si es None, se usa la fecha actual.

    Returns:
        pandas.DataFrame con columnas: periodico, titulo, texto, url.
        Si no hay artículos, devuelve un DataFrame vacío con esas columnas.
    """
    if target_date is None:
        target_date = date.today()

    log.info("Buscando hasta %d artículos de opinión del %s", limit, target_date.isoformat())

    # 1. Descargar el sitemap del mes en curso
    sm_url = SITEMAP_URL_TPL.format(year=target_date.year, month=target_date.month)
    log.info("Descargando sitemap %s", sm_url)
    xml = fetch(sm_url)
    polite_sleep()

    if not xml:
        log.error("No se pudo obtener el sitemap del mes %04d-%02d",
                  target_date.year, target_date.month)
        return pd.DataFrame(columns=DF_COLUMNS)

    # 2. Parsear y filtrar por fecha de hoy
    entries = parse_sitemap_for_opinion(xml)
    log.info("URLs de opinión en el sitemap del mes: %d", len(entries))

    target_iso = target_date.isoformat()  # 'YYYY-MM-DD'
    todays_entries = [
        (url, lastmod) for url, lastmod in entries
        if lastmod.startswith(target_iso)
    ]
    log.info("URLs de opinión publicadas/modificadas el %s: %d",
             target_iso, len(todays_entries))

    if not todays_entries:
        log.warning("No hay artículos de opinión para la fecha %s", target_iso)
        return pd.DataFrame(columns=DF_COLUMNS)

    # Más recientes primero
    todays_entries.sort(key=lambda e: e[1], reverse=True)

    # 3. Recorrer URLs y extraer artículos hasta llegar al límite
    articles: list[Article] = []
    skipped_paywall = 0
    skipped_error = 0

    for url, lastmod in todays_entries:
        if len(articles) >= limit:
            break

        html = fetch(url)
        polite_sleep()

        if not html:
            skipped_error += 1
            continue

        art = extract_article(url, html)
        if art is None:
            skipped_paywall += 1
            continue

        articles.append(art)
        log.info("[%d/%d] %s", len(articles), limit, art.titulo[:80])

    log.info("FIN. Recogidos: %d. Paywall: %d. Errores: %d.",
             len(articles), skipped_paywall, skipped_error)

    # 4. Construir DataFrame
    df = pd.DataFrame([asdict(a) for a in articles], columns=DF_COLUMNS)
    return df


def main() -> int:
    """Punto de entrada: ejecuta el scraping y devuelve un código de salida."""
    df = scrape_opinion_articles_hoy(limit=10)
    print(f"\nSe han obtenido {len(df)} artículos.")
    print(df)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())