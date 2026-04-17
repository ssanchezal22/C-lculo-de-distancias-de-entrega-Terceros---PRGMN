# Despliegue de la app de calculo de distancia de PRGMN en Streamlit

Este proyecto contiene un app Streamlit en `ruta.py` para cargar un archivo `.csv` o `.xlsx`, calcular distancias desde una dirección fija y exportar el resultado.

## Objetivo

El propósito es que diferentes usuarios de la compañía puedan acceder al app mediante una URL y subir su archivo.

## Archivos necesarios

- `ruta.py` — código principal del app.
- `requirements.txt` — dependencias de Python necesarias.
- `logo.avif` o `logo.jpg` — imagen del logo que se muestra en la app.

## Nota importante

- Si corre `streamlit run ruta.py` localmente, dependerá de su computadora y su terminal.

## Uso

- Los usuario de PRGMN abre la URL del app.
- Carga su archivo `.csv` o `.xlsx`.
- Hace clic en `Calcular distancias`.
- Descarga el archivo resultante con la columna `Distance (km)`.
- Evalúan la viabilidad de tercerizar aquellas ubicaciones que estén a menos de 3km de distancia desde el COP.

  
## Por:

- Sebastián Sánchez Álvarez, Mejora Continua, CAFÉ PERGAMINO
