# Spanish Opinion Analysis

## Overview
This project aims to apply Natural Language Processing (NLP) techniques to the analysis of the Spanish digital press. Based on the hypothesis that different media outlets cover the same news events from distinct ideological frameworks, this work seeks to analyze how this is reflected in the language used, the prioritized topics, and the tone adopted. Through topic modeling, polarity analysis, and classifiers, the project demonstrates the potential of NLP to study how the media constructs and frames reality. The project culminates with the development of an agent-based system that transforms the collected news corpus into an automated, personalized news recommendation service. It is worth noting that this project is a strictly educational web scraping exercise. As such, the raw data is not included in this repository to respect the intellectual property rights of the original sources.

## Authors
* Álvaro Nieva Valenzuela
* Azahara Martinez Moraño
* Axel Valton Juan
* Iyán Álvarez Rodríguez
* Jeremy Joel Aguilar Marin
* Joan Merlos Cremades

## Techniques Used
* **Web Scraping:** Use of requests, BeautifulSoup, and Selenium.
* **Data Processing:** Stopword and punctuation removal, and lemmatization.
* **Topic Modeling:** UMAP transformation, HDBSCAN algorithm, and BERTopic model.
* **Polarity Analysis:** Use of TextBlob and the RoBERTa model via pysentimiento.
* **Supervised Classification:** Random Forest and XGBoost models.
* **LLM Agent:** Use of LangChain and the Llama 3.3 70B Instruct model.

## Main Files
* `scrapers/`: Folder containing the code for the automated extraction of news.
* `limpieza_datos.ipynb`: Notebook dedicated to text cleaning and preparation.
* `analisis_datos.ipynb`: Main notebook featuring topic modeling, sentiment analysis, and predictive model training.
* `orquestador.py` and `orquestador_general.py`: Scripts responsible for executing and unifying the entire agent workflow.
* `app_orquestador.py` and `interfaz_preferencias.py`: Visual interfaces to easily interact with the agent.
