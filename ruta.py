import io
import os
import pandas as pd
import requests
import streamlit as st
import time
from geopy.geocoders import ArcGIS
from geopy.distance import geodesic

# Punto de partida fijo de la empresa
ORIGIN_ADDRESS = 'Calle 17 #43F-235, Medellin, Colombia'
CITY_HINT = 'Medellín, Colombia'
# Inicializar geolocator
gen = ArcGIS()


def geocode_address(address):
    try:
        location = gen.geocode(address, timeout=15)
        if location:
            return location.latitude, location.longitude
        return None, None
    except Exception:
        return None, None


def calculate_distance(lat1, lon1, lat2, lon2):
    try:
        url = f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
        response = requests.get(url, timeout=15)
        data = response.json()
        if 'routes' in data and data['routes']:
            return data['routes'][0]['distance'] / 1000
        return geodesic((lat1, lon1), (lat2, lon2)).km
    except Exception:
        return geodesic((lat1, lon1), (lat2, lon2)).km


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


def load_file(uploaded_file):
    name = uploaded_file.name
    ext = os.path.splitext(name)[1].lower()
    if ext in ['.xlsx', '.xls']:
        return pd.read_excel(uploaded_file)
    if ext == '.csv':
        return load_csv_buffer(uploaded_file)
    raise ValueError('Sólo se aceptan archivos .csv o .xlsx')


def find_address_column(df):
    candidates = ['Shipping Address1', 'Shipping Street', 'Shipping Address', 'Billing Address1', 'Address']
    for col in candidates:
        if col in df.columns:
            return col
    raise ValueError('No se encontró columna de dirección válida en el archivo.')


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


def process_dataframe(df, delay=0.4):
    df = clean_dataframe(df)
    address_col = find_address_column(df)

    origin_lat, origin_lon = geocode_address(ORIGIN_ADDRESS)
    if origin_lat is None or origin_lon is None:
        raise RuntimeError(f'No se pudo geocodificar el punto de partida: {ORIGIN_ADDRESS}')

    distances = []
    progress = st.progress(0)
    total = len(df)

    for idx, row in df.iterrows():
        province = str(row['Shipping Province']) if 'Shipping Province' in df.columns and pd.notna(row['Shipping Province']) else ''
        if 'ant' not in province.lower():
            distances.append('-')
        else:
            address = str(row[address_col]) if pd.notna(row[address_col]) else ''
            if not address:
                distances.append('-')
            else:
                if CITY_HINT.lower() not in address.lower():
                    full_address = f"{address}, {CITY_HINT}"
                else:
                    full_address = address

                lat2, lon2 = geocode_address(full_address)
                if lat2 is None or lon2 is None:
                    distances.append('-')
                else:
                    distances.append(calculate_distance(origin_lat, origin_lon, lat2, lon2))

        progress.progress((idx + 1) / total)
        time.sleep(delay)

    df['Distance (km)'] = distances
    return df


def to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Distances')
    return output.getvalue()


def app():
    st.set_page_config(page_title='Cálculo de distancias de entrega Terceros', layout='wide')
    
    cols = st.columns([2, 1])
    cols[0].markdown('<h1 style="color: #4ECDC4; margin: 0;">Cálculo de distancias de entrega Terceros</h1>', unsafe_allow_html=True)
    logo_path = 'logo.avif'
    if os.path.exists(logo_path):
        cols[1].image(logo_path, width=200)
    
    st.write('Sube un archivo CSV o XLSX, calcularemos la distancia desde el COP a cada dirección de entrega.')
    st.markdown(f'**Punto de partida fijo:** {ORIGIN_ADDRESS}')
    st.info('Sólo se calcularán distancias para filas donde Shipping Province contenga "ANT". Las demás mostrarán "-".')

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


if __name__ == '__main__':
    app()



