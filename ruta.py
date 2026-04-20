import io
import os
import re
import unicodedata
import pandas as pd
import requests
import streamlit as st
import time
from geopy.geocoders import ArcGIS
from geopy.distance import geodesic
from rapidfuzz import process as fuzz_process

# Configuración de la aplicación
# Punto de partida fijo de la empresa desde donde se calculan las distancias
ORIGIN_ADDRESS = 'Calle 17 #43F-235, Medellin, Colombia'
# Sugerencia de ciudad para direcciones incompletas
CITY_HINT = 'Medellín, Colombia'
# Municipios del Valle de Aburrá (normalizados: sin tildes, minúsculas)
VALLE_ABURRA_CITIES = [
    'medellin', 'bello', 'itagui', 'envigado', 'sabaneta',
    'la estrella', 'caldas', 'copacabana', 'girardota', 'barbosa',
]
# Umbral de similitud para fuzzy matching (0-100)
FUZZY_THRESHOLD = 82
# Nombres de display canónicos para construir queries de geocodificación precisas
VALLE_ABURRA_DISPLAY = {
    'medellin': 'Medellín',
    'bello': 'Bello',
    'itagui': 'Itagüí',
    'envigado': 'Envigado',
    'sabaneta': 'Sabaneta',
    'la estrella': 'La Estrella',
    'caldas': 'Caldas',
    'copacabana': 'Copacabana',
    'girardota': 'Girardota',
    'barbosa': 'Barbosa',
}
# Bounding box geográfico del Valle de Aburrá para validar coordenadas geocodificadas
VALLE_LAT_MIN, VALLE_LAT_MAX = 5.9, 6.5
VALLE_LON_MIN, VALLE_LON_MAX = -75.8, -75.3
# Número de reintentos para la API de OSRM antes de caer a distancia geodésica
OSRM_RETRIES = 3
# Inicializar el geocodificador de ArcGIS para convertir direcciones en coordenadas
gen = ArcGIS()


# Función para normalizar texto: minúsculas, sin tildes, sin contenido entre paréntesis
def normalize_text(text):
    text = re.sub(r'\(.*?\)', '', str(text))  # quitar texto entre paréntesis
    text = text.strip().lower()
    # descomponer caracteres Unicode y descartar marcas de acento
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


# Función para determinar si una ciudad pertenece al Valle de Aburrá.
# Capa 1: coincidencia exacta o substring (rápida).
# Capa 2: fuzzy matching con rapidfuzz para errores tipográficos (umbral FUZZY_THRESHOLD).
def is_valle_aburra_city(city_str):
    city_norm = normalize_text(city_str)
    if not city_norm:
        return False
    # Capa 1: algún municipio es substring del texto normalizado
    for city in VALLE_ABURRA_CITIES:
        if city in city_norm:
            return True
    # Capa 2: fuzzy matching contra la lista de municipios
    result = fuzz_process.extractOne(city_norm, VALLE_ABURRA_CITIES)
    if result is not None and result[1] >= FUZZY_THRESHOLD:
        return True
    return False


# Retorna el nombre canónico de display del municipio (para construir la query de geocodificación),
# o None si la ciudad no pertenece al Valle de Aburrá.
def get_canonical_city(city_str):
    city_norm = normalize_text(city_str)
    # Capa 1: substring exacto
    for key in VALLE_ABURRA_CITIES:
        if key in city_norm:
            return VALLE_ABURRA_DISPLAY[key]
    # Capa 2: fuzzy
    result = fuzz_process.extractOne(city_norm, VALLE_ABURRA_CITIES)
    if result is not None and result[1] >= FUZZY_THRESHOLD:
        return VALLE_ABURRA_DISPLAY[result[0]]
    return None


# Verifica que las coordenadas caigan dentro del bounding box del Valle de Aburrá.
# Evita aceptar resultados de geocodificación que apunten a otra región de Colombia.
def is_within_valle_aburra(lat, lon):
    return VALLE_LAT_MIN <= lat <= VALLE_LAT_MAX and VALLE_LON_MIN <= lon <= VALLE_LON_MAX


# Función para geocodificar una dirección y obtener latitud y longitud
def geocode_address(address):
    try:
        location = gen.geocode(address, timeout=15)
        if location:
            return location.latitude, location.longitude
        return None, None
    except Exception:
        return None, None


# Función para calcular la distancia en kilómetros entre dos puntos usando OSRM.
# Reintenta hasta OSRM_RETRIES veces antes de caer a distancia geodésica como respaldo.
def calculate_distance(lat1, lon1, lat2, lon2):
    url = f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
    for attempt in range(OSRM_RETRIES):
        try:
            response = requests.get(url, timeout=15)
            data = response.json()
            if 'routes' in data and data['routes']:
                return data['routes'][0]['distance'] / 1000
        except Exception:
            pass
        if attempt < OSRM_RETRIES - 1:
            time.sleep(1)
    return geodesic((lat1, lon1), (lat2, lon2)).km


# Función para cargar un archivo CSV desde un buffer de bytes, intentando diferentes codificaciones
def load_csv_buffer(buffer):
    text = None
    try:
        text = buffer.getvalue().decode('utf-8')
        df = pd.read_csv(io.StringIO(text), sep=None, engine='python', quotechar='"')
        return df
    except Exception:
        try:
            text = buffer.getvalue().decode('latin-1')
            return pd.read_csv(io.StringIO(text), sep=None, engine='python', quotechar='"')
        except Exception as exc:
            raise ValueError(f'No se pudo leer el CSV: {exc}')


# Función para cargar un archivo subido (CSV o Excel) y devolver un DataFrame de pandas
def load_file(uploaded_file):
    name = uploaded_file.name
    ext = os.path.splitext(name)[1].lower()
    if ext in ['.xlsx', '.xls']:
        return pd.read_excel(uploaded_file)
    if ext == '.csv':
        return load_csv_buffer(uploaded_file)
    raise ValueError('Sólo se aceptan archivos .csv o .xlsx')


# Función que construye la query de geocodificación más completa posible combinando
# Shipping Street (Address1 + Address2 ya unidos por Shopify), o Address1 + Address2
# por separado, más la ciudad canónica y provincia para máxima precisión.
def build_geocode_query(row, canonical_city):
    def get_col(col):
        val = row.get(col, '')
        return str(val).strip() if pd.notna(val) and str(val).strip() not in ('', 'nan') else ''

    street = get_col('Shipping Street')
    addr1 = get_col('Shipping Address1')
    addr2 = get_col('Shipping Address2')

    # Preferir Shipping Street si existe (Shopify ya combina Address1 + Address2)
    if street:
        base = street
    elif addr1:
        # Agregar Address2 solo si aporta info nueva (no es substring de Address1)
        if addr2 and addr2.lower() not in addr1.lower():
            base = f"{addr1}, {addr2}"
        else:
            base = addr1
    else:
        raise ValueError('No se encontró dirección válida en las columnas Shipping Street / Address1.')

    city_suffix = f"{canonical_city}, Antioquia, Colombia"
    # Evitar duplicar la ciudad si ya aparece en la dirección
    if canonical_city.lower() in base.lower():
        return f"{base}, Antioquia, Colombia"
    return f"{base}, {city_suffix}"


# Función para limpiar el DataFrame agrupando por 'Name' y rellenando valores faltantes hacia adelante y atrás
def clean_dataframe(df):
    if 'Name' not in df.columns:
        raise ValueError('El archivo debe contener la columna Name para agrupar pedidos.')

    df_clean = df.copy()
    groups = df_clean.groupby('Name')
    for col in df_clean.columns:
        if col == 'Name':
            continue
        df_clean[col] = groups[col].ffill().bfill()
    return df_clean


# Función principal para procesar el DataFrame: limpiar, geocodificar direcciones, calcular distancias solo para filas con 'ANT' en Shipping Province, y mostrar progreso
def process_dataframe(df, delay=0.4):
    df = clean_dataframe(df)

    origin_lat, origin_lon = geocode_address(ORIGIN_ADDRESS)
    if origin_lat is None or origin_lon is None:
        raise RuntimeError(f'No se pudo geocodificar el punto de partida: {ORIGIN_ADDRESS}')

    distances = []
    progress = st.progress(0)
    total = len(df)

    for idx, row in df.iterrows():
        province = str(row['Shipping Province']) if 'Shipping Province' in df.columns and pd.notna(row['Shipping Province']) else ''
        city = str(row['Shipping City']) if 'Shipping City' in df.columns and pd.notna(row['Shipping City']) else ''
        if 'ant' not in province.lower() or not is_valle_aburra_city(city):
            distances.append('-')
        else:
            canonical_city = get_canonical_city(city)
            try:
                full_address = build_geocode_query(row, canonical_city or 'Medellín')
            except ValueError:
                distances.append('-')
                progress.progress((idx + 1) / total)
                time.sleep(delay)
                continue

            lat2, lon2 = geocode_address(full_address)
            if lat2 is None or lon2 is None:
                distances.append('-')
            elif not is_within_valle_aburra(lat2, lon2):
                # El geocodificador apuntó a una zona fuera del Valle de Aburrá
                distances.append('-')
            else:
                distances.append(calculate_distance(origin_lat, origin_lon, lat2, lon2))

        progress.progress((idx + 1) / total)
        time.sleep(delay)

    df['Distance (km)'] = distances
    return df


# Función para convertir un DataFrame a bytes de un archivo Excel
def to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Distances')
    return output.getvalue()


# Función principal de la aplicación Streamlit: configura la página, muestra el header con logo, maneja la subida de archivos, procesa datos y permite descarga
def app():
    st.set_page_config(page_title='Cálculo de distancias de entrega Terceros', layout='wide')
    
    cols = st.columns([2, 1])
    cols[0].markdown('<h1 style="color: #4ECDC4; margin: 0;">Cálculo de distancias de entrega Terceros</h1>', unsafe_allow_html=True)
    logo_path = 'logo.avif'
    if os.path.exists(logo_path):
        cols[1].image(logo_path, width=200)
    
    st.write('Sube un archivo CSV o XLSX, calcularemos la distancia desde el COP a cada dirección de entrega.')
    st.markdown(f'**Punto de partida fijo:** {ORIGIN_ADDRESS}')
    st.info('Sólo se calcularán distancias para entregas en municipios del Valle de Aburrá (Medellín, Bello, Itagüí, Envigado, Sabaneta, La Estrella, Caldas, Copacabana, Girardota, Barbosa). Las demás filas mostrarán "-".')

    uploaded_file = st.file_uploader('Sube un archivo .csv o .xlsx', type=['csv', 'xlsx', 'xls'])
    if uploaded_file is None:
        st.info('Sube un archivo para comenzar.')
        return

    try:
        df = load_file(uploaded_file)
    except Exception as exc:
        st.error(f'Error al leer el archivo: {exc}')
        return

    st.success(f'Archivo cargado correctamente. Columnas encontradas: {len(df.columns)}')
    st.dataframe(df.head(5), use_container_width=True)

    if st.button('Calcular distancias'):
        with st.spinner('Procesando direcciones y calculando distancias...'):
            try:
                result_df = process_dataframe(df)
            except Exception as exc:
                st.error(f'No se pudo procesar el archivo: {exc}')
                return

        st.success('Cálculo completado.')
        result_display = result_df.copy()
        result_display['Distance (km)'] = result_display['Distance (km)'].apply(
            lambda x: f"{x:.2f} km" if isinstance(x, (int, float)) else x
        )
        st.dataframe(result_display.head(10), use_container_width=True)
        excel_bytes = to_excel_bytes(result_df)
        st.download_button('Descargar resultado en Excel', data=excel_bytes, file_name='distancias_entrega.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        st.write('Puedes descargar el archivo con la columna `Distance (km)` agregada.')


# Bloque principal para ejecutar la aplicación cuando el script se corre directamente
if __name__ == '__main__':
    app()



