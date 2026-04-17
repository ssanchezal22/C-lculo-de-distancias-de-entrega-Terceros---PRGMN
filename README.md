# Despliegue del app Streamlit

Este proyecto contiene un app Streamlit en `ruta.py` para cargar un archivo `.csv` o `.xlsx`, calcular distancias desde una dirección fija y exportar el resultado.

## Objetivo

El propósito es que tus usuarios puedan acceder al app mediante una URL y subir su archivo sin depender de tu kernel o terminal local.

## ¿Qué necesitas?

1. Subir el proyecto a un repositorio GitHub.
2. Desplegar el app en un servicio de hosting para aplicaciones web.
3. El servicio ejecutará `streamlit run ruta.py` en un servidor, y tus usuarios accederán por URL.

## Servicios recomendados

### Streamlit Community Cloud

1. Crea una cuenta en [streamlit.io/cloud](https://streamlit.io/cloud).
2. Conecta tu repositorio GitHub.
3. Selecciona el repositorio y el archivo `ruta.py`.
4. Asegúrate de que `requirements.txt` esté en el repositorio.
5. Streamlit generará una URL pública donde tus usuarios podrán usar el app.

### Render / Railway / otros

Para servicios como Render, Railway o Heroku, puedes usar este comando de inicio:

```bash
streamlit run ruta.py --server.port $PORT --server.enableCORS false --server.headless true
```

## Archivos necesarios

- `ruta.py` — código principal del app.
- `requirements.txt` — dependencias de Python necesarias.
- `logo.avif` o `logo.jpg` — imagen del logo que se muestra en la app.

## Pasos concretos

1. Asegúrate de que el repositorio incluya `ruta.py`, `requirements.txt` y el logo.
2. Sube el repositorio a GitHub.
3. Despliega en Streamlit Cloud o un servicio equivalente.
4. Copia la URL pública y compártela con tus usuarios.

## Nota importante

- Si corres `streamlit run ruta.py` localmente, sí depende de tu computadora y tu terminal.
- Para que tus usuarios no dependan de ti, debes usar un servicio de hosting que mantenga el app activo.

## Uso

- Tu usuario abre la URL del app.
- Carga su archivo `.csv` o `.xlsx`.
- Hace clic en `Calcular distancias`.
- Descarga el archivo resultante con la columna `Distance (km)`.
