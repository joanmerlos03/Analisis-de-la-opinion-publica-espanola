# Análisis de la Opinión Española

## Resumen
El presente proyecto tiene como objetivo aplicar técnicas de Procesamiento del Lenguaje Natural (NLP) al análisis de la prensa digital española. Partiendo de la hipótesis de que distintos medios de comunicación cubren los mismos hechos noticiosos desde marcos ideológicos diferenciados, el trabajo busca analizar cómo esto se refleja en el lenguaje empleado, los temas priorizados y el tono adoptado. A través del modelado de temas, análisis de polaridad y clasificadores, el proyecto demuestra el potencial del NLP para estudiar cómo los medios construyen y enmarcan la realidad. El proyecto culmina con el desarrollo de un sistema basado en agentes que transforma el corpus de noticias recopilado en un servicio automatizado de recomendación personalizada de noticias. Cabe destacar que este proyecto es un ejercicio estrictamente educativo de web scraping, por lo que los datos crudos no se incluyen en este repositorio para respetar los derechos de propiedad intelectual de las fuentes originales.

## Autores
* Álvaro Nieva Valenzuela
* Azahara Martinez Moraño
* Axel Valton Juan
* Iyán Álvarez Rodríguez
* Jeremy Joel Aguilar Marin
* Joan Merlos Cremades

## Técnicas utilizadas
* **Web Scraping:** Uso de requests, BeautifulSoup y Selenium.
* **Procesado de datos:** Eliminación de stopwords, signos de puntuación y lematización.
* **Topic Modeling:** Transformación UMAP, algoritmo HDBSCAN y modelo BERTopic.
* **Análisis de Polaridad:** Uso de TextBlob y modelo RoBERTa mediante pysentimiento.
* **Clasificación Supervisada:** Modelos Random Forest y XGBoost.
* **Agente LLM:** Uso de LangChain y el modelo Llama 3.3 70B Instruct.

## Archivos principales
* `scrapers/`: Carpeta con los códigos para la extracción automatizada de noticias.
* `limpieza_datos.ipynb`: Notebook dedicado a la depuración y preparación de los textos.
* `analisis_datos.ipynb`: Notebook principal con el topic modeling, análisis de sentimiento y entrenamiento de modelos predictivos.
* `orquestador.py` y `orquestador_general.py`: Scripts encargados de ejecutar y unificar todo el flujo del agente.
* `app_orquestador.py` e `interfaz_preferencias.py`: Interfaces visuales para interactuar con el agente de forma sencilla.
