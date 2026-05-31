from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException, TimeoutException
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import pandas as pd
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def scrape_larazon_opinion(
    objetivo=10,
    headless=True,
    paginas_max=300
):
    """
    Scrapea artículos de opinión de La Razón y devuelve un DataFrame.

    Parámetros
    ----------
    objetivo : int
        Número de artículos válidos que se quieren obtener.

    headless : bool
        Si True, Chrome se ejecuta en segundo plano.
        Si False, se abre la ventana de Chrome.

    paginas_max : int
        Número máximo de páginas de la sección opinión a revisar.

    Devuelve
    --------
    pd.DataFrame
        DataFrame con las columnas: periodico, titulo, texto, url.
    """

    BASE = "https://www.larazon.es"
    SECCION = "https://www.larazon.es/opinion/"

    # ---------------------------------------------------------
    # CONFIG SELENIUM
    # ---------------------------------------------------------

    options = Options()
    
    # 🚨 LA LÍNEA MÁGICA: Ignora la carga de anuncios e imágenes pesadas
    options.page_load_strategy = 'eager' 
    
    options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--log-level=3")

    options.binary_location = "/opt/render/project/.render/chrome/opt/google/chrome/google-chrome"

    cookies_aceptadas = False

    def crear_driver():
        servicio = Service(ChromeDriverManager().install())
        nuevo_driver = webdriver.Chrome(service=servicio, options=options)
        
        # 🚨 Le damos un poco más de margen al servidor gratuito
        nuevo_driver.set_page_load_timeout(60) 
        return nuevo_driver

    driver = crear_driver()

    # ---------------------------------------------------------
    # FUNCIONES AUXILIARES
    # ---------------------------------------------------------

    def aceptar_cookies():
        nonlocal cookies_aceptadas, driver

        if cookies_aceptadas:
            return

        try:
            botones = driver.find_elements(By.TAG_NAME, "button")

            for b in botones:
                texto = b.text.lower()

                if "acept" in texto or "agree" in texto:
                    print("Aceptando cookies...")
                    b.click()
                    time.sleep(2)
                    cookies_aceptadas = True
                    return

        except Exception:
            pass

    def get_soup(url, wait=4, intentos=3):
        nonlocal driver, cookies_aceptadas

        for intento in range(1, intentos + 1):
            try:
                print(f"\nAbriendo: {url} | intento {intento}")

                driver.get(url)
                time.sleep(wait)
                aceptar_cookies()

                return BeautifulSoup(driver.page_source, "html.parser")

            except (ConnectionResetError, WebDriverException, TimeoutException) as e:
                print(f"Fallo cargando página: {e}")

                try:
                    driver.quit()
                except Exception:
                    pass

                print("Reiniciando navegador...")
                driver = crear_driver()
                cookies_aceptadas = False

                time.sleep(5)

        print("No se pudo cargar la página")
        return None

    def limpiar_texto(texto):
        if not texto:
            return None

        return re.sub(r"\s+", " ", texto).strip()

    # ---------------------------------------------------------
    # EXTRAER LINKS DE OPINIÓN
    # ---------------------------------------------------------

    def extraer_links_opinion():
        links = set()

        for pagina in range(1, paginas_max + 1):

            if pagina == 1:
                url_pagina = SECCION
            else:
                url_pagina = f"{SECCION}{pagina}/"

            soup = get_soup(url_pagina, wait=4)

            if soup is None:
                print(f"Página {pagina} fallida, sigo")
                continue

            encontrados_pagina = set()

            for a in soup.find_all("a", href=True):
                href = a["href"]

                url = urljoin(BASE, href)
                url = url.split("?")[0].split("#")[0]

                if (
                    url.startswith(BASE)
                    and "/opinion/" in url
                    and url.endswith(".html")
                ):
                    encontrados_pagina.add(url)

            antes = len(links)
            links.update(encontrados_pagina)
            nuevos = len(links) - antes

            print(
                f"Página {pagina} | encontrados: {len(encontrados_pagina)} | "
                f"nuevos: {nuevos} | total: {len(links)}"
            )

            if len(links) >= objetivo:
                break

            time.sleep(2)

        return sorted(links)[:objetivo]

    # ---------------------------------------------------------
    # EXTRAER TÍTULO
    # ---------------------------------------------------------

    def extraer_titulo(soup):
        meta = soup.find("meta", attrs={"property": "og:title"})

        if meta:
            return limpiar_texto(meta.get("content"))

        h1 = soup.find("h1")

        if h1:
            return limpiar_texto(h1.get_text())

        return None

    # ---------------------------------------------------------
    # EXTRAER TEXTO
    # ---------------------------------------------------------

    def extraer_texto(soup):
        article = soup.find("article")
        textos = []

        if article:
            for p in article.find_all("p"):
                t = limpiar_texto(p.get_text())

                if t and len(t) > 40:
                    textos.append(t)

        if not textos:
            for p in soup.find_all("p"):
                t = limpiar_texto(p.get_text())

                if t and len(t) > 40:
                    textos.append(t)

        if textos:
            return " ".join(dict.fromkeys(textos))

        return None

    # ---------------------------------------------------------
    # EXTRAER ARTÍCULO
    # ---------------------------------------------------------

    def extraer_articulo(url):
        soup = get_soup(url)

        if soup is None:
            return {
                "periodico": "la razon",
                "titulo": None,
                "texto": None,
                "url": url
            }

        titulo = extraer_titulo(soup)
        texto = extraer_texto(soup)

        return {
            "periodico": "la razon",
            "titulo": titulo,
            "texto": texto,
            "url": url
        }

    # ---------------------------------------------------------
    # MAIN INTERNO DE LA FUNCIÓN
    # ---------------------------------------------------------

    resultados = []
    urls_ya_hechas = set()

    try:
        print("\n--- RECOGIENDO LINKS ---")
        links = extraer_links_opinion()

        print("\nTOTAL LINKS:", len(links))

        print("\n--- PROCESANDO ARTÍCULOS ---")

        for i, link in enumerate(links, 1):

            if link in urls_ya_hechas:
                print(f"\n[{i}/{len(links)}] ya procesado, salto")
                continue

            try:
                print(f"\n[{i}/{len(links)}] {link}")

                data = extraer_articulo(link)

                if data["titulo"] and data["texto"] and len(data["texto"]) > 200:
                    resultados.append(data)
                    urls_ya_hechas.add(link)
                    print("Añadido")
                else:
                    print("Descartado")

                print("Total válidos:", len(resultados))

                if len(resultados) >= objetivo:
                    break

                time.sleep(3)

            except Exception as e:
                print("Error:", e)

                try:
                    driver.quit()
                except Exception:
                    pass

                driver = crear_driver()
                cookies_aceptadas = False
                time.sleep(5)

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    # ---------------------------------------------------------
    # DEVOLVER DATAFRAME
    # ---------------------------------------------------------

    df = pd.DataFrame(resultados)

    if not df.empty:
        df = df.drop_duplicates(subset=["url"])
        df = df[["periodico", "titulo", "texto", "url"]]
        df = df.head(objetivo)

    print("\nTOTAL FINAL:", len(df))

    return df


if __name__ == "__main__":
    df = scrape_larazon_opinion(
        objetivo=10,
        headless=True
    )

    print(df.head())