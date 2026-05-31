import time
import random
import re
import pandas as pd
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# FUNCIONES AUXILIARES


def scroll_humano(driver):
    """Hace scroll hacia abajo poco a poco simulando el comportamiento de un usuario."""
    altura_total = driver.execute_script("return document.body.scrollHeight")
    posicion_actual = 0
    while posicion_actual < altura_total / 1.5: 
        salto = random.randint(400, 800)
        posicion_actual += salto
        driver.execute_script(f"window.scrollTo(0, {posicion_actual});")
        time.sleep(random.uniform(0.5, 1.2))

def limpiar_texto(texto):
    """Limpia el texto de la noticia de cabeceras, pies y saltos de línea extra."""
    texto = str(texto)
    
    # Detectar al autor desde el propio texto
    match_autor = re.search(r'Por\s*(.*?)\n', texto)
    autor_extraido = match_autor.group(1).strip() if match_autor else None

    # Limpiar la cabecera
    patron_fecha = r'\d{2}/\d{2}/\d{4}\s*\d{2}:\d{2}.*?\n+'
    partes = re.split(patron_fecha, texto, maxsplit=1)
    
    if len(partes) > 1:
        texto = partes[1]
    else:
        texto = re.sub(r'^Opinión\n+Por.*?\n+.*?\n+', '', texto, flags=re.DOTALL)

    # Limpiar el pie de página
    patron_pie = r'(Vídeos de \'Público\'|Te puede interesar|Comentarios de nuestros socias/os).*$'
    texto = re.sub(patron_pie, '', texto, flags=re.DOTALL | re.IGNORECASE)

    # Quitar la biografía del autor
    if autor_extraido:
        patron_bio = rf'\n+{re.escape(autor_extraido)}\n+.*$'
        texto = re.sub(patron_bio, '', texto, flags=re.DOTALL)

    # 5. Quitar saltos de línea y espacios en blanco extra
    texto = re.sub(r'(?<!\n)\n(?!\n)', ' ', texto)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    
    return texto.strip()



# FUNCIÓN PRINCIPAL DEL SCRAPER


def extraer_noticias_publico(max_noticias=10):
    """
    Ejecuta el flujo completo: 
    1. Extrae enlaces con Selenium.
    2. Descarga el texto con Requests/BS4.
    3. Limpia y estructura los datos con Pandas.
    """
    URL_BASE = "https://www.publico.es/opinion"

    # EXTRACCIÓN DE ENLACES CON SELENIUM
    opciones = webdriver.ChromeOptions()
    
    # 🚨 1. Banderas obligatorias para el servidor sin pantalla de Render
    opciones.add_argument("--headless=new")
    opciones.add_argument("--no-sandbox")
    opciones.add_argument("--disable-dev-shm-usage")
    opciones.add_argument("--disable-gpu")
    
    # 🚨 2. Ruta vital del ejecutable de Chrome en la nube
    opciones.binary_location = "/opt/render/project/.render/chrome/opt/google/chrome/google-chrome"

    # 3. Tus configuraciones Anti-Bot originales (Intactas)
    opciones.add_experimental_option("excludeSwitches", ["enable-automation"])
    opciones.add_experimental_option('useAutomationExtension', False)
    opciones.add_argument('--disable-blink-features=AutomationControlled')
    opciones.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

    print("🤖 Iniciando el robot para extraer enlaces...")
    
    # 🚨 4. Usamos ChromeDriverManager para enlazar la versión correcta automáticamente
    servicio = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=servicio, options=opciones)
    
    # Tu script para ocultar el rastro de webdriver en JavaScript
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    noticias_extraidas = 0
    pagina_actual = 1
    noticias_lista = []

    try:
        driver.maximize_window()
        
        while noticias_extraidas < max_noticias:
            url_pagina = URL_BASE if pagina_actual == 1 else f"{URL_BASE}/{pagina_actual}"
            print(f"\n📄 Navegando a la página {pagina_actual}: {url_pagina}")
            driver.get(url_pagina)
            
            time.sleep(random.uniform(2.0, 3.5)) 
            scroll_humano(driver)
            
            try:
                articulos = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article.listing-item"))
                )
                print(f"✅ Encontrados {len(articulos)} artículos en esta página.")
            except Exception:
                print("⚠️ No se encontraron más artículos.")
                break 
                
            for articulo in articulos:
                if noticias_extraidas >= max_noticias:
                    break
                    
                try:
                    h2_titulo = articulo.find_element(By.CSS_SELECTOR, "h2.title")
                    autor_elemento = articulo.find_element(By.CSS_SELECTOR, "span.font-bold")
                    enlace_elemento = h2_titulo.find_element(By.TAG_NAME, "a")

                    titulo = h2_titulo.get_attribute("textContent").strip()
                    autor = autor_elemento.get_attribute("textContent").strip()
                    enlace = enlace_elemento.get_attribute("href")
                    
                    if not titulo:
                        continue
                    
                    noticias_lista.append({
                        "titulo": titulo,
                        "autor": autor,
                        "enlace": enlace
                    })
                    
                    noticias_extraidas += 1
                    print(f"[{noticias_extraidas}/{max_noticias}] Extraído: {titulo[:40]}...")
                    
                except Exception:
                    pass 
                    
            if noticias_extraidas >= max_noticias:
                print("\n🎯 ¡Límite máximo de noticias alcanzado!")
                break
                
            pagina_actual += 1

    finally:
        driver.quit()
        print("Navegador cerrado.\n")

    if not noticias_lista:
        print("No se logró extraer ningún enlace. Finalizando proceso.")
        return pd.DataFrame()

    #  EXTRACCIÓN DEL CUERPO CON REQUESTS
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    datos_completos = []

    print(f"🚀 Iniciando la extracción de texto para {len(noticias_lista)} noticias...\n")
    for i, noticia in enumerate(noticias_lista, 1):
        url_noticia = noticia["enlace"]
        print(f"[{i}/{len(noticias_lista)}] Extrayendo: {url_noticia}")
        
        try:
            respuesta = requests.get(url_noticia, headers=headers)
            respuesta.raise_for_status()
            soup = BeautifulSoup(respuesta.text, "html.parser")
            
            cuerpo_noticia = ""
            contenedor_texto = soup.find("div", class_="article-text")
            
            if not contenedor_texto:
                contenedor_texto = soup.find("article")
                
            if contenedor_texto:
                parrafos = contenedor_texto.find_all("p")
                textos_parrafos = [p.get_text(strip=True) for p in parrafos if p.get_text(strip=True)]
                cuerpo_noticia = "\n\n".join(textos_parrafos)
            else:
                cuerpo_noticia = "No se pudo encontrar el contenedor del texto."

            datos_completos.append({
                "Título": noticia["titulo"],
                "Texto": cuerpo_noticia,
                "URL": url_noticia
            })
            
            time.sleep(random.uniform(0.5, 1.5))
            
        except Exception as e:
            print(f"⚠️ Error al extraer {url_noticia}: {e}")
            datos_completos.append({
                "Título": noticia["titulo"],
                "Texto": "ERROR AL EXTRAER",
                "URL": url_noticia
            })

    # LIMPIEZA Y FORMATEO CON PANDAS
    print("\n✅ Extracción finalizada. Creando DataFrame y limpiando textos...")
    df = pd.DataFrame(datos_completos)

    # Limpiamos los textos
    df['Texto'] = df['Texto'].apply(limpiar_texto)

    # Renombramos columnas
    df = df.rename(columns={
        'Título': 'titulo',
        'Texto': 'texto',
        'URL': 'url'
    })
    
    # Añadimos la columna del periódico y reordenamos
    df["periodico"] = "Público"
    df = df[['periodico', 'titulo', 'texto', 'url']]

    return df