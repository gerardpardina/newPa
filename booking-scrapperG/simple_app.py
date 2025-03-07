import streamlit as st
import numpy as np
import pandas as pd

st.title("Simple Test App")

st.write("Esta es una aplicación de prueba para verificar el despliegue en Streamlit Cloud.")

st.write(f"Versiones de las bibliotecas utilizadas:")
st.write(f"- Streamlit: {st.__version__}")
st.write(f"- NumPy: {np.__version__}")
st.write(f"- Pandas: {pd.__version__}")

st.success("La aplicación está funcionando correctamente.")

# Crear un DataFrame de ejemplo
data = {
    'Hostal': ['Hostal A', 'Hostal B', 'Hostal C', 'Hostal D'],
    'Precio Privado': [75.5, 82.0, 65.3, 90.2],
    'Precio Compartido': [45.2, 50.1, 39.8, 55.5]
}

df = pd.DataFrame(data)
st.dataframe(df)

# Crear un gráfico simple
st.subheader("Gráfico de precios")
chart_data = pd.DataFrame(
    np.random.randn(20, 3),
    columns=['Privado', 'Compartido', 'Sin Tasa'])

st.line_chart(chart_data)

st.info("Si ves esta aplicación, significa que el despliegue en Streamlit Cloud está funcionando correctamente.") 