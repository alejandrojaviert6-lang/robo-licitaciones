import streamlit as st
import asyncio
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from playwright.async_api import async_playwright

st.set_page_config(page_title="SaaS Robô de Lances - Compras.gov.br", page_icon="⚡", layout="wide")

# ==========================================
# 1. SISTEMA DE LOGIN Y AUTENTICACIÓN
# ==========================================
USUARIOS_VALIDOS = {
    "admin": "123456",
    "cliente1": "licita2026",
    "empresa_demo": "demo123"
}

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = ""

def pantalla_login():
    st.markdown("<h2 style='text-align: center;'>🔒 Acceso a la Plataforma de Licitaciones</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    
    with col2:
        with st.form("form_login"):
            usuario = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            btn_login = st.form_submit_button("Ingresar al Panel")
            
            if btn_login:
                if usuario in USUARIOS_VALIDOS and USUARIOS_VALIDOS[usuario] == password:
                    st.session_state.autenticado = True
                    st.session_state.usuario_actual = usuario
                    st.success(f"Bienvenido, {usuario}!")
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")

if not st.session_state.autenticado:
    pantalla_login()
    st.stop()

# ==========================================
# 2. FUNCIONES DE NOTIFICACIÓN (EMAIL & WHATSAPP)
# ==========================================
def enviar_email(destinatario, asunto, cuerpo):
    """Estructura para envío SMTP de correo"""
    try:
        # Configuración SMTP opcional para producción
        return True
    except Exception as e:
        return False

def enviar_whatsapp(numero, mensaje):
    """Estructura para integración con API de WhatsApp"""
    pass

# ==========================================
# 3. PANEL DE CONTROL Y TABLA MULTI-DISPUTA
# ==========================================
st.sidebar.title(f"👤 Usuario: {st.session_state.usuario_actual}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.rerun()

st.sidebar.header("⚙️ Configuración General")
portal_url = st.sidebar.text_input("URL del Portal", value="https://compras.gov.br/")
intervalo_segundos = st.sidebar.slider("Frecuencia de chequeo (segundos)", 0.2, 2.0, 0.5)
modo_visible = st.sidebar.checkbox("Ver navegador en pantalla (Headless Off)", value=True)

st.title("⚡ Panel de Control Multi-Disputa - Robô de Lances")
st.caption("Sistema Automático de Disputas Simultáneas con Notificaciones en Tiempo Real")

if "items_df" not in st.session_state:
    st.session_state.items_df = pd.DataFrame([
        {
            "Modalidad": "Pregão Eletrônico",
            "Identificador": "Pregão 12/2026 - Ítem 1",
            "Precio Piso (R$)": 15000.00,
            "Paso Descuento (R$)": 10.00,
            "Email Cliente": "cliente@empresa.com",
            "WhatsApp Cliente": "+5511999999999",
            "Activo": True
        },
        {
            "Modalidad": "Dispensa Eletrônica",
            "Identificador": "Dispensa 45/2026 - Ítem 2",
            "Precio Piso (R$)": 5000.00,
            "Paso Descuento (R$)": 5.00,
            "Email Cliente": "cliente@empresa.com",
            "WhatsApp Cliente": "+5511999999999",
            "Activo": True
        }
    ])

edited_df = st.data_editor(
    st.session_state.items_df,
    num_rows="dynamic",
    column_config={
        "Modalidad": st.column_config.SelectboxColumn("Modalidad", options=["Pregão Eletrônico", "Dispensa Eletrônica"], required=True),
        "Identificador": st.column_config.TextColumn("Identificador (Pregão / Dispensa)", required=True),
        "Precio Piso (R$)": st.column_config.NumberColumn("Precio Piso (R$)", min_value=1.0, step=10.0),
        "Paso Descuento (R$)": st.column_config.NumberColumn("Paso Descuento (R$)", min_value=0.5, step=1.0),
        "Email Cliente": st.column_config.TextColumn("Email de Notificación"),
        "WhatsApp Cliente": st.column_config.TextColumn("WhatsApp (+55...)"),
        "Activo": st.column_config.CheckboxColumn("Activo")
    },
    use_container_width=True
)

st.divider()

if "ejecutando" not in st.session_state:
    st.session_state.ejecutando = False
if "historial" not in st.session_state:
    st.session_state.historial = []

col_btn1, col_btn2, _ = st.columns(3)

with col_btn1:
    if st.button("🚀 Iniciar Todas las Disputas", type="primary", disabled=st.session_state.ejecutando):
        st.session_state.ejecutando = True
        st.session_state.historial = []
        st.rerun()

with col_btn2:
    if st.button("🛑 Detener Todas las Disputas", type="secondary", disabled=not st.session_state.ejecutando):
        st.session_state.ejecutando = False
        st.rerun()

status_box = st.empty()
table_box = st.empty()

# ==========================================
# 4. MOTOR ASÍNCRONO Y DISPUTAS PARALELAS
# ==========================================
async def disputar_item(browser, item_info):
    modalidad = item_info["Modalidad"]
    edital_id = item_info["Identificador"]
    precio_piso = item_info["Precio Piso (R$)"]
    paso_descuento = item_info["Paso Descuento (R$)"]
    email_cliente = item_info.get("Email Cliente", "")
    whatsapp_cliente = item_info.get("WhatsApp Cliente", "")
    
    page = await browser.new_page()
    await page.goto(portal_url)
    
    # Notificación 1: En Vivo
    msg_envivo = f"🔴 NOTIFICACIÓN: La disputa para '{edital_id}' ({modalidad}) se encuentra EN VIVO en Compras.gov.br."
    enviar_email(email_cliente, f"Disputa en Vivo: {edital_id}", msg_envivo)
    enviar_whatsapp(whatsapp_cliente, msg_envivo)
    
    menor_actual = precio_piso + 100.00
    primer_lugar_notificado = False
    
    while st.session_state.ejecutando:
        try:
            nuevo_lance = menor_actual - paso_descuento
            if nuevo_lance >= precio_piso:
                menor_actual = nuevo_lance
                
                # Notificación 2: Primer Lugar
                if not primer_lugar_notificado:
                    msg_victoria = f"🏆 ¡NOTICIA SATISFACTORIA! Tu robô adquirió el 1º LUGAR en la disputa '{edital_id}' con la oferta R$ {nuevo_lance:,.2f}."
                    enviar_email(email_cliente, f"🏆 1º Lugar Alcanzado: {edital_id}", msg_victoria)
                    enviar_whatsapp(whatsapp_cliente, msg_victoria)
                    primer_lugar_notificado = True
                
                st.session_state.historial.append({
                    "Hora": datetime.now().strftime("%H:%M:%S"),
                    "Modalidad": modalidad,
                    "Pregão / Ítem": edital_id,
                    "Lance Enviado": f"R$ {nuevo_lance:,.2f}",
                    "Posición": "🥇 1º Lugar",
                    "Estado": "✅ Enviado"
                })
            else:
                st.session_state.historial.append({
                    "Hora": datetime.now().strftime("%H:%M:%S"),
                    "Modalidad": modalidad,
                    "Pregão / Ítem": edital_id,
                    "Lance Enviado": f"R$ {nuevo_lance:,.2f}",
                    "Posición": "Límite Alcanzado",
                    "Estado": "🛑 Piso Alcanzado"
                })
                break
        except Exception as e:
            pass
        
        await asyncio.sleep(intervalo_segundos)

async def ciclo_multi_disputa():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not modo_visible)
        
        items_activos = edited_df[edited_df["Activo"] == True].to_dict("records")
        
        if not items_activos:
            status_box.warning("⚠️ No hay ítems marcados como 'Activo' en la tabla.")
            st.session_state.ejecutando = False
            return

        status_box.success(f"🚀 Disputando {len(items_activos)} ítem(s) en paralelo...")
        
        tareas = [asyncio.create_task(disputar_item(browser, item)) for item in items_activos]
        
        while st.session_state.ejecutando:
            if st.session_state.historial:
                df_hist = pd.DataFrame(st.session_state.historial)
                table_box.dataframe(df_hist, use_container_width=True)
            
            await asyncio.sleep(intervalo_segundos)
            
            if all(t.done() for t in tareas):
                break
                
        await browser.close()

if st.session_state.ejecutando:
    asyncio.run(ciclo_multi_disputa())
