import streamlit as st
import pandas as pd
import mysql.connector
import time
import plotly.express as px

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Centro de Mando Basurero", layout="wide", page_icon="🗑️")

def conectar_db():
    return mysql.connector.connect(
        host="192.168.1.212",
        user="fabricio",
        password="efenomas", 
        database="basurero"  
    )

# --- HELPER PARA DIBUJAR LOS BASUREROS ---
def dibujar_basurero(titulo, porcentaje, color_hex):
    # Aseguramos que el porcentaje no se pase de 0 a 100 para el gráfico
    p = max(0, min(100, porcentaje))
    
    # HTML sin indentación para evitar que Streamlit lo vuelva texto
    html = f"""<div style="display: flex; flex-direction: column; align-items: center; padding: 10px;">
<h4 style="margin-bottom: 10px; color: {color_hex};">{titulo}</h4>
<div style="width: 120px; height: 180px; border: 4px solid #444; border-radius: 5px 5px 15px 15px; position: relative; overflow: hidden; background-color: #2b2b2b; box-shadow: 2px 2px 10px rgba(0,0,0,0.5);">
<div style="position: absolute; bottom: 0; width: 100%; height: {p}%; background-color: {color_hex}; transition: height 0.5s ease-in-out; opacity: 0.85;"></div>
<div style="position: absolute; width: 100%; text-align: center; top: 40%; font-size: 22px; font-weight: bold; color: white; text-shadow: 1px 1px 3px black;">{p:.1f}%</div>
</div>
<p style="margin-top: 10px; font-size: 15px; font-weight: bold; color: #bbb;">Llenado: {p:.1f} %</p>
</div>"""
    return html

def generar_resumen_usuarios():
    try:
        conn = conectar_db()
        query = """
            SELECT u.nombre_usuario, COUNT(c.idu) as total_registros
            FROM (
                SELECT idu FROM ultrasonic_data
                UNION ALL
                SELECT idu FROM mq4_data
            ) AS c
            JOIN usuarios u ON c.idu = u.id
            GROUP BY u.id, u.nombre_usuario
        """
        df_usuarios = pd.read_sql(query, conn)
        conn.close()

        if not df_usuarios.empty:
            st.subheader("Tráfico de Datos por Operador")
            
            fig = px.pie(
                df_usuarios, 
                values='total_registros', 
                names='nombre_usuario', 
                hole=0.4,
                color_discrete_sequence=px.colors.sequential.Tealgrn
            )
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("Ver tabla de aportes por usuario"):
                st.dataframe(df_usuarios.sort_values('total_registros', ascending=False), use_container_width=True)
        else:
            st.info("No hay datos registrados en el sistema todavía.")
            
    except Exception as e:
        st.error(f"Error al cargar el resumen de usuarios: {e}")

def generar_dashboard_llenado():
    try:
        conn = conectar_db()
        query = "SELECT id, dist_bio, nivel_bio, dist_paper, nivel_paper, dist_vidrio, nivel_vidrio, dist_plastics, nivel_plastics, timed FROM ultrasonic_data ORDER BY timed ASC"
        df = pd.read_sql(query, conn)
        conn.close()

        if not df.empty:
            df['timed'] = pd.to_datetime(df['timed'])
            
            # Tomar el último valor registrado de cada sensor
            ult_nivel_bio = df['nivel_bio'].iloc[-1]
            ult_nivel_papel = df['nivel_paper'].iloc[-1]
            ult_nivel_vidrio = df['nivel_vidrio'].iloc[-1]
            ult_nivel_plastico = df['nivel_plastics'].iloc[-1]
            
            st.write("### Niveles Actuales de los Contenedores")
            
            # Dibujar los 4 basureros lado a lado
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(dibujar_basurero("Biológico", ult_nivel_bio, "#4CAF50"), unsafe_allow_html=True)
            with col2:
                st.markdown(dibujar_basurero("Papel", ult_nivel_papel, "#2196F3"), unsafe_allow_html=True)
            with col3:
                st.markdown(dibujar_basurero("Vidrio", ult_nivel_vidrio, "#9E9E9E"), unsafe_allow_html=True)
            with col4:
                st.markdown(dibujar_basurero("Plástico", ult_nivel_plastico, "#FFC107"), unsafe_allow_html=True)

            st.divider()

            st.subheader("Evolución de Llenado por Sección (%)")
            df_recent = df.tail(50)
            st.line_chart(df_recent.set_index('timed')[['nivel_bio', 'nivel_paper', 'nivel_vidrio', 'nivel_plastics']])
            
            with st.expander("Historial completo (Sensores Ultrasónicos)"):
                st.dataframe(df.sort_values('timed', ascending=False))
        else:
            st.warning("Esperando datos de los sensores ultrasónicos...")
            
    except Exception as e:
        st.error(f"Error: {e}")

def generar_dashboard_mq4():
    try:
        conn = conectar_db()
        query = "SELECT id, valor_raw, voltaje_v, alerta_gas, timed FROM mq4_data ORDER BY timed ASC"
        df = pd.read_sql(query, conn)
        conn.close()

        if not df.empty:
            df['timed'] = pd.to_datetime(df['timed'])
            ult_voltaje = df['voltaje_v'].iloc[-1]
            ult_alerta = df['alerta_gas'].iloc[-1]
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Registros de Gas", len(df))
            m2.metric("Voltaje Actual", f"{ult_voltaje:.2f} V")
            
            estado_texto = "ALERTA 🔴" if ult_alerta == 1 else "Normal 🟢"
            m3.metric("Estado del Contenedor", estado_texto)

            col_izq, col_der = st.columns(2)
            df_recent = df.tail(50)

            with col_izq:
                st.subheader("Nivel de Gas (Voltaje)")
                st.area_chart(df_recent.set_index('timed')['voltaje_v'])
            
            with col_der:
                st.subheader("Lectura Cruda (ADC)")
                st.line_chart(df_recent.set_index('timed')['valor_raw'])
            
            with st.expander("Historial completo (Sensor MQ4)"):
                st.dataframe(df.sort_values('timed', ascending=False))
        else:
            st.warning("Esperando datos del sensor MQ4...")
            
    except Exception as e:
        st.error(f"Error: {e}")

def generar_dashboard_ia():
    try:
        conn = conectar_db()
        query = "SELECT clase, total, ultima_vez FROM classification_counts ORDER BY total DESC"
        df = pd.read_sql(query, conn)
        conn.close()

        if not df.empty and df['total'].sum() > 0:
            total_inferencias = df['total'].sum()
            df_fechas = df.dropna(subset=['ultima_vez'])
            ultima_fecha = df_fechas['ultima_vez'].max() if not df_fechas.empty else "N/A"
            
            m1, m2 = st.columns(2)
            m1.metric("Total Residuos Clasificados", total_inferencias)
            m2.metric("Última Detección", str(ultima_fecha))

            st.subheader("Frecuencia de Clases (Acumulado)")
            fig_bar = px.bar(df, x='clase', y='total', color='clase', title="Detecciones Totales por Tipo")
            st.plotly_chart(fig_bar, use_container_width=True)
            
            with st.expander("Ver tabla de conteos de IA"):
                st.dataframe(df)
        else:
            st.info("Esperando que la IA clasifique el primer residuo...")
            
    except Exception as e:
        st.error(f"Error: {e}")


# --- INTERFAZ PRINCIPAL ---
st.title("🗑️ Dashboard Control Basurero Inteligente")

# Pestañas actualizadas
tabs = st.tabs(["Resumen Global", "Niveles de Llenado", "Sensor de Gas (MQ4)", "Conteo IA"])

with tabs[0]:
    generar_resumen_usuarios()
with tabs[1]:
    generar_dashboard_llenado()
with tabs[2]:
    generar_dashboard_mq4()
with tabs[3]:
    generar_dashboard_ia()

# Bucle de actualización
time.sleep(2)
st.rerun()
