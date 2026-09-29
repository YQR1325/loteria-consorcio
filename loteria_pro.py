# ============================================================
# 🍀 LA RED DE LA SUERTE — SISTEMA PRO v3.0 FINAL
# Multi-banca · Red · Monitoreo · QR · Alertas · Capital
# Límites · Sorteos · Cuadre · Auditoría · Respaldos
# Compatible con Render / Railway / VPS
# ============================================================

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import hashlib
import os
import socket
import time
import io
import qrcode
import plotly.express as px
import plotly.graph_objects as go
import requests
import zipfile
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.utils import ImageReader

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

st.set_page_config(
    page_title="La Red de la Suerte",
    page_icon="🍀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# RUTA DE BASE DE DATOS (soporta Render con disco persistente)
# ============================================================
if os.environ.get("RENDER"):
    DB = "/var/data/loteria_pro.db"
else:
    DB = "loteria_pro.db"

os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
BACKUP_DIR = os.path.join(os.path.dirname(DB) or ".", "respaldos")
os.makedirs(BACKUP_DIR, exist_ok=True)


# ============================================================
# 🎨 MARCA
# ============================================================
MARCA = {
    "nombre": "LA RED DE LA SUERTE",
    "slogan": "Donde todos los días se gana",
    "color_primario": "#1B5E20",
    "color_secundario": "#FFD700",
    "color_acento": "#C62828",
    "telefono": "(809) 555-1234",
    "whatsapp": "18095551234",
    "web": "www.lareddelasuerte.com",
    "logo_path": "logo.png",
    "rnc": "1-31-12345-6",
    "telegram_bot": "alertas_redsuerte_bot",
}

# ============================================================
# 🔔 ALERTAS
# ============================================================
ALERTAS = {
    "activas": True,
    "telegram_token": os.getenv("TELEGRAM_TOKEN", ""),
    "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
    "umbral_perdida": 5000,
    "umbral_venta_alta": 50000,
}

# ============================================================
# 🎰 LOTERÍAS DE REPÚBLICA DOMINICANA
# ============================================================
LOTERIAS = {
    "Lotería Nacional": {
        "Gana Más": {"horario": "13:30"},
        "Lotería Nacional": {"horario": "20:00"},
        "Juega + Pega +": {"horario": "20:00"},
        "Billete Electrónico": {"horario": "18:00"},
    },
    "Leidsa": {
        "Quiniela Leidsa": {"horario": "20:55"},
        "Pega 3 Más": {"horario": "20:55"},
        "Loto Pool": {"horario": "20:55"},
        "Super Kino TV": {"horario": "20:55"},
        "Loto": {"horario": "20:55"},
        "Super Loto": {"horario": "20:55"},
    },
    "Loteka": {
        "Quiniela Loteka": {"horario": "19:55"},
        "Mega Chances": {"horario": "19:55"},
        "Toca 3": {"horario": "19:55"},
        "Mega Lotto": {"horario": "19:55"},
    },
    "Loto Real del Cibao": {
        "Quiniela Real": {"horario": "12:55"},
        "Tu Fecha Real": {"horario": "12:55"},
        "Pega 4 Real": {"horario": "12:55"},
        "Loto Pool Real": {"horario": "12:55"},
        "Loto Real": {"horario": "12:55"},
    },
    "La Suerte Dominicana": {
        "La Suerte Día": {"horario": "12:30"},
        "La Suerte Noche": {"horario": "18:00"},
    },
    "LoteDom": {
        "La Quiniela LoteDom": {"horario": "12:00"},
        "El Quemaito Mayor": {"horario": "12:00"},
        "Agarra 4": {"horario": "12:00"},
    },
    "La Primera": {
        "La Primera Día": {"horario": "12:00"},
        "La Primera Noche": {"horario": "19:00"},
        "El Quinielon": {"horario": "19:00"},
        "Loto 5": {"horario": "19:00"},
        "Loto 5+": {"horario": "19:00"},
    },
    "Anguila": {
        "Anguila 10AM": {"horario": "10:00"},
        "Anguila 1PM": {"horario": "13:00"},
        "Anguila 6PM": {"horario": "18:00"},
        "Anguila 9PM": {"horario": "21:00"},
    },
    "King Lottery": {
        "King Lottery 12:30": {"horario": "12:30"},
        "King Lottery 7:30": {"horario": "19:30"},
    },
}

MULTIPLICADORES = {
    "Fijo": 60,
    "Parle": 1000,
    "Pale": 1000,
    "Tripleta": 10000,
}


# ============================================================
# 🔔 TELEGRAM
# ============================================================
def enviar_telegram(mensaje):
    if not ALERTAS["activas"] or not ALERTAS["telegram_token"]:
        return False
    try:
        url = f"https://api.telegram.org/bot{ALERTAS['telegram_token']}/sendMessage"
        r = requests.post(url, json={
            "chat_id": ALERTAS["telegram_chat_id"],
            "text": mensaje,
            "parse_mode": "HTML"
        }, timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def verificar_alertas():
    if not ALERTAS["activas"]:
        return
    hoy = date.today().strftime("%Y-%m-%d")
    conn = conectar()
    df = pd.read_sql_query(f"""
        SELECT l.nombre AS banca,
               SUM(v.monto) AS vendido,
               SUM(CASE WHEN v.estado='ganadora' THEN v.premio_pagado ELSE 0 END) AS premios
        FROM ventas v
        JOIN locales l ON l.id = v.local_id
        WHERE DATE(v.fecha) = '{hoy}'
        GROUP BY l.nombre
    """, conn)
    conn.close()
    for _, row in df.iterrows():
        vendido = row["vendido"] or 0
        premios = row["premios"] or 0
        ganancia = vendido - premios
        if ganancia < -ALERTAS["umbral_perdida"]:
            enviar_telegram(
                f"🚨 <b>ALERTA DE PÉRDIDA</b>\n\n"
                f"Banca: <b>{row['banca']}</b>\n"
                f"Vendido: ${vendido:,.2f}\n"
                f"Premios: ${premios:,.2f}\n"
                f"Ganancia: <b>${ganancia:,.2f}</b>"
            )
        if vendido > ALERTAS["umbral_venta_alta"]:
            enviar_telegram(
                f"📈 <b>VENTA ALTA</b>\n\n"
                f"Banca: <b>{row['banca']}</b>\n"
                f"Vendido: <b>${vendido:,.2f}</b>"
            )


# ============================================================
# BASE DE DATOS
# ============================================================
def conectar():
    return sqlite3.connect(DB, check_same_thread=False)


def hash_clave(clave):
    return hashlib.sha256(clave.encode()).hexdigest()


def init_db():
    conn = conectar()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS locales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            direccion TEXT,
            encargado TEXT,
            telefono TEXT,
            rnc TEXT,
            capital_inicial REAL DEFAULT 0,
            comision_porcentaje REAL DEFAULT 0,
            activo INTEGER DEFAULT 1
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            clave TEXT NOT NULL,
            nombre TEXT NOT NULL,
            rol TEXT NOT NULL,
            local_id INTEGER,
            comision_porcentaje REAL DEFAULT 0,
            activo INTEGER DEFAULT 1,
            FOREIGN KEY(local_id) REFERENCES locales(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sorteos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loteria TEXT NOT NULL,
            producto TEXT NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT,
            numero_ganador TEXT,
            estado TEXT DEFAULT 'abierto',
            local_id INTEGER,
            FOREIGN KEY(local_id) REFERENCES locales(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sorteo_id INTEGER NOT NULL,
            local_id INTEGER NOT NULL,
            usuario_id INTEGER NOT NULL,
            numero TEXT NOT NULL,
            tipo TEXT DEFAULT 'Fijo',
            monto REAL NOT NULL,
            premio_potencial REAL NOT NULL,
            premio_pagado REAL DEFAULT 0,
            comision REAL DEFAULT 0,
            estado TEXT DEFAULT 'activa',
            cliente TEXT,
            telefono_cliente TEXT,
            fecha TEXT NOT NULL,
            FOREIGN KEY(sorteo_id) REFERENCES sorteos(id),
            FOREIGN KEY(local_id) REFERENCES locales(id),
            FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS caja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            local_id INTEGER NOT NULL,
            usuario_id INTEGER,
            tipo TEXT NOT NULL,
            monto REAL NOT NULL,
            descripcion TEXT,
            fecha TEXT NOT NULL,
            FOREIGN KEY(local_id) REFERENCES locales(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS capital (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            local_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            monto REAL NOT NULL,
            descripcion TEXT,
            fecha TEXT NOT NULL,
            FOREIGN KEY(local_id) REFERENCES locales(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS sesiones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            local_id INTEGER NOT NULL,
            ip TEXT,
            ultimo_ping TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            accion TEXT,
            detalle TEXT,
            fecha TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS limites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_jugada TEXT NOT NULL,
            combinacion TEXT NOT NULL,
            monto_maximo REAL NOT NULL,
            local_id INTEGER,
            aplica_todas INTEGER DEFAULT 0,
            hora_inicio TEXT,
            hora_fin TEXT,
            activo INTEGER DEFAULT 1,
            creado_por INTEGER,
            fecha_creacion TEXT,
            FOREIGN KEY(local_id) REFERENCES locales(id)
        )
    """)

    conn.commit()

    c.execute("SELECT COUNT(*) FROM usuarios WHERE rol='admin'")
    if c.fetchone()[0] == 0:
        c.execute("""INSERT INTO usuarios (usuario, clave, nombre, rol)
                     VALUES (?, ?, ?, ?)""",
                  ("admin", hash_clave("admin123"), "Dueño del Consorcio", "admin"))
        c.execute("""INSERT INTO locales 
                     (nombre, direccion, encargado, telefono, rnc, capital_inicial, comision_porcentaje)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  ("Banca Central", "Av. Principal #1, Santo Domingo",
                   "Admin", "(809) 555-1234", "1-31-12345-6", 50000, 10))
        conn.commit()

    conn.close()


def auditar(accion, detalle=""):
    try:
        conn = conectar()
        c = conn.cursor()
        uid = st.session_state.user["id"] if "user" in st.session_state else None
        c.execute("""INSERT INTO auditoria (usuario_id, accion, detalle, fecha)
                     VALUES (?, ?, ?, ?)""",
                  (uid, accion, detalle, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ============================================================
# QR + TICKET
# ============================================================
def generar_qr(datos_texto):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(datos_texto)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def generar_ticket(datos_venta, ruta_salida="ticket.pdf"):
    ancho, alto = 80 * mm, 200 * mm
    c = canvas.Canvas(ruta_salida, pagesize=(ancho, alto))

    color_prim = HexColor(MARCA["color_primario"])
    color_sec = HexColor(MARCA["color_secundario"])
    color_ace = HexColor(MARCA["color_acento"])

    c.setStrokeColor(color_sec)
    c.setLineWidth(3)
    c.rect(5, 5, ancho - 10, alto - 10)
    c.setStrokeColor(color_prim)
    c.setLineWidth(1)
    c.rect(8, 8, ancho - 16, alto - 16)

    c.setFillColor(color_prim)
    c.rect(8, alto - 60, ancho - 16, 52, fill=1, stroke=0)

    if os.path.exists(MARCA["logo_path"]):
        try:
            img = ImageReader(MARCA["logo_path"])
            c.drawImage(img, ancho / 2 - 18, alto - 63, width=36, height=36,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass
    else:
        c.setFillColor(color_sec)
        c.circle(ancho / 2, alto - 35, 18, fill=1, stroke=0)
        c.setFillColor(color_prim)
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(ancho / 2, alto - 42, "S")

    c.setFillColor(color_sec)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(ancho / 2, alto - 48, MARCA["nombre"])
    c.setFillColor(white)
    c.setFont("Helvetica-Oblique", 6)
    c.drawCentredString(ancho / 2, alto - 56, MARCA["slogan"])

    c.setStrokeColor(color_sec)
    c.setLineWidth(2)
    c.line(15, alto - 65, ancho - 15, alto - 65)

    y = alto - 80
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(15, y, datos_venta["banca"])
    y -= 11
    c.setFont("Helvetica", 7)
    c.drawString(15, y, datos_venta.get("direccion", "")[:38])
    y -= 10
    c.drawString(15, y, f"RNC: {MARCA['rnc']}")
    y -= 10
    c.drawString(15, y, f"Tel: {MARCA['telefono']}")
    y -= 10
    c.drawString(15, y, f"Vendedor: {datos_venta['vendedor']}")
    y -= 10
    c.drawString(15, y, f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    y -= 20
    c.setFillColor(HexColor("#F5F5F5"))
    c.rect(12, y - 20, ancho - 24, 22, fill=1, stroke=0)
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(15, y - 5, "Sorteo:")
    c.setFont("Helvetica", 7)
    c.drawString(15, y - 15, datos_venta["sorteo"][:38])

    y -= 30
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(15, y, "Jugada:")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(color_prim)
    c.drawString(60, y, datos_venta["tipo"].upper())

    y -= 45
    c.setFillColor(color_sec)
    c.roundRect(20, y - 5, ancho - 40, 32, 5, fill=1, stroke=0)
    c.setStrokeColor(color_prim)
    c.setLineWidth(1.5)
    c.roundRect(20, y - 5, ancho - 40, 32, 5, fill=0, stroke=1)
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(ancho / 2, y + 20, "NUMERO JUGADO")
    c.setFillColor(color_prim)
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(ancho / 2, y + 3, datos_venta["numero"])

    y -= 20
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(15, y, "Monto:")
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(ancho - 15, y, f"${datos_venta['monto']:,.2f}")

    y -= 16
    c.setFillColor(color_ace)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(15, y, "Premio potencial:")
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(ancho - 15, y, f"${datos_venta['premio']:,.2f}")

    y -= 12
    c.setStrokeColor(black)
    c.setDash(2, 2)
    c.setLineWidth(0.5)
    c.line(15, y, ancho - 15, y)
    c.setDash()

    y -= 12
    c.setFont("Helvetica", 7)
    c.drawString(15, y, f"Ticket #: {datos_venta['ticket_id']}")
    y -= 9
    c.drawString(15, y, f"Cliente: {datos_venta.get('cliente', 'Anonimo')}")

    y -= 55
    try:
        qr_data = (f"TICKET:{datos_venta['ticket_id']}|"
                   f"NUM:{datos_venta['numero']}|"
                   f"MONTO:{datos_venta['monto']}|"
                   f"PREMIO:{datos_venta['premio']}|"
                   f"WEB:{MARCA['web']}")
        qr_buf = generar_qr(qr_data)
        qr_img = ImageReader(qr_buf)
        c.drawImage(qr_img, ancho / 2 - 25, y, width=50, height=50,
                    preserveAspectRatio=True)
        c.setFillColor(black)
        c.setFont("Helvetica", 6)
        c.drawCentredString(ancho / 2, y - 8, "Escanea para verificar")
    except Exception:
        pass

    y -= 20
    c.setFillColor(color_prim)
    c.rect(8, y - 30, ancho - 16, 32, fill=1, stroke=0)
    c.setFillColor(color_sec)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(ancho / 2, y - 5, "BUENA SUERTE")
    c.setFillColor(white)
    c.setFont("Helvetica", 6)
    c.drawCentredString(ancho / 2, y - 15, "Verifica tu ticket en:")
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString(ancho / 2, y - 24, MARCA["web"])

    c.setStrokeColor(color_sec)
    c.setLineWidth(1)
    for i in range(15, int(ancho) - 10, 6):
        c.circle(i, 10, 1, fill=1, stroke=0)

    c.save()
    return ruta_salida


# ============================================================
# RESPALDO
# ============================================================
def crear_respaldo():
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo = os.path.join(BACKUP_DIR, f"respaldo_{ts}.zip")
        with zipfile.ZipFile(archivo, "w", zipfile.ZIP_DEFLATED) as z:
            if os.path.exists(DB):
                z.write(DB, os.path.basename(DB))
        return archivo
    except Exception:
        return None


# ============================================================
# LOGIN
# ============================================================
def login():
    st.markdown("<h1 style='text-align:center;'>🍀 LA RED DE LA SUERTE</h1>",
                unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;color:gray;'>Sistema Central del Consorcio</h4>",
                unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login"):
            usuario = st.text_input("👤 Usuario")
            clave = st.text_input("🔑 Contraseña", type="password")
            submit = st.form_submit_button("Ingresar", use_container_width=True)
            if submit:
                conn = conectar()
                c = conn.cursor()
                c.execute("""SELECT id, usuario, nombre, rol, local_id FROM usuarios
                             WHERE usuario=? AND clave=? AND activo=1""",
                          (usuario, hash_clave(clave)))
                user = c.fetchone()
                if user:
                    ip = "0.0.0.0"
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        s.connect(("8.8.8.8", 80))
                        ip = s.getsockname()[0]
                        s.close()
                    except Exception:
                        pass
                    c.execute("""INSERT INTO sesiones (usuario_id, local_id, ip, ultimo_ping)
                                 VALUES (?, ?, ?, ?)""",
                              (user[0], user[4] or 0, ip,
                               datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    conn.close()
                    st.session_state.user = {
                        "id": user[0], "usuario": user[1],
                        "nombre": user[2], "rol": user[3], "local_id": user[4]
                    }
                    auditar("LOGIN", f"Usuario {usuario} ingresó")
                    st.rerun()
                else:
                    conn.close()
                    st.error("❌ Usuario o contraseña incorrectos")
        st.info("💡 **Admin por defecto:** admin / admin123")


# ============================================================
# UTILIDADES
# ============================================================
def obtener_locales():
    conn = conectar()
    df = pd.read_sql_query("SELECT * FROM locales WHERE activo=1", conn)
    conn.close()
    return df


def obtener_sorteos(abiertos=True):
    conn = conectar()
    q = "SELECT * FROM sorteos"
    if abiertos:
        q += " WHERE estado='abierto'"
    q += " ORDER BY fecha DESC, hora DESC"
    df = pd.read_sql_query(q, conn)
    conn.close()
    return df


def obtener_saldo_banca(local_id):
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT capital_inicial FROM locales WHERE id=?", (local_id,))
    r = c.fetchone()
    capital_inicial = r[0] if r else 0
    c.execute("SELECT COALESCE(SUM(monto),0) FROM capital WHERE local_id=? AND tipo='Ingreso'", (local_id,))
    ingresos_cap = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(monto),0) FROM capital WHERE local_id=? AND tipo='Retiro'", (local_id,))
    retiros = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(monto),0) FROM ventas WHERE local_id=?", (local_id,))
    ventas = c.fetchone()[0]
    c.execute("""SELECT COALESCE(SUM(premio_pagado),0) FROM ventas 
                 WHERE local_id=? AND estado='ganadora'""", (local_id,))
    premios = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(monto),0) FROM caja WHERE local_id=? AND tipo='Gasto'", (local_id,))
    gastos = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(monto),0) FROM caja WHERE local_id=? AND tipo='Ingreso'", (local_id,))
    otros_ingresos = c.fetchone()[0]
    conn.close()
    return (capital_inicial + ingresos_cap - retiros + ventas - premios
            - gastos + otros_ingresos)


def verificar_limites_venta(local_id, tipo_jugada, numeros, monto_nuevo):
    conn = conectar()
    c = conn.cursor()
    hora_actual = datetime.now().strftime("%H:%M")
    c.execute("""
        SELECT id, tipo_jugada, combinacion, monto_maximo, local_id, 
               aplica_todas, hora_inicio, hora_fin
        FROM limites
        WHERE activo=1 AND (aplica_todas=1 OR local_id=?)
    """, (local_id,))
    limites = c.fetchall()
    numeros_ordenados = "-".join(sorted(numeros))

    for lim in limites:
        lim_id, tipo_lim, comb_lim, max_lim, loc_lim, todas, h_ini, h_fin = lim
        if h_ini and h_fin and not (h_ini <= hora_actual <= h_fin):
            continue
        if tipo_lim != tipo_jugada:
            continue
        comb_lim_ordenada = "-".join(sorted(comb_lim.split("-")))

        if comb_lim_ordenada == numeros_ordenados:
            conn2 = conectar()
            c2 = conn2.cursor()
            if todas:
                c2.execute("""SELECT COALESCE(SUM(monto),0) FROM ventas
                              WHERE numero=? AND tipo=? AND estado='activa'
                                AND DATE(fecha)=DATE('now')""",
                           (comb_lim, tipo_lim))
            else:
                c2.execute("""SELECT COALESCE(SUM(monto),0) FROM ventas
                              WHERE local_id=? AND numero=? AND tipo=? 
                                AND estado='activa' AND DATE(fecha)=DATE('now')""",
                           (local_id, comb_lim, tipo_lim))
            ya_vendido = c2.fetchone()[0]
            conn2.close()
            disponible = max_lim - ya_vendido
            if monto_nuevo > disponible:
                conn.close()
                return (False,
                        f"🚫 LÍMITE alcanzado para {tipo_lim} {comb_lim}.\n"
                        f"Máximo: ${max_lim:,.2f}\n"
                        f"Ya vendido: ${ya_vendido:,.2f}\n"
                        f"Disponible: ${disponible:,.2f}",
                        disponible)

        if tipo_lim == "Fijo" and tipo_jugada in ("Parle", "Pale", "Tripleta"):
            if comb_lim in numeros:
                conn2 = conectar()
                c2 = conn2.cursor()
                if todas:
                    c2.execute("""SELECT COALESCE(SUM(monto),0) FROM ventas
                                  WHERE numero LIKE ? AND estado='activa'
                                    AND DATE(fecha)=DATE('now')""", (f"%{comb_lim}%",))
                else:
                    c2.execute("""SELECT COALESCE(SUM(monto),0) FROM ventas
                                  WHERE local_id=? AND numero LIKE ? AND estado='activa'
                                    AND DATE(fecha)=DATE('now')""",
                               (local_id, f"%{comb_lim}%"))
                ya_vendido_comb = c2.fetchone()[0]
                conn2.close()
                if ya_vendido_comb + monto_nuevo > max_lim:
                    conn.close()
                    return (False,
                            f"🚫 El número {comb_lim} está dentro de una "
                            f"combinación limitada.\n"
                            f"Límite del {comb_lim}: ${max_lim:,.2f}\n"
                            f"Ya comprometido: ${ya_vendido_comb:,.2f}",
                            max_lim - ya_vendido_comb)
    conn.close()
    return (True, "✅ Venta permitida", 0)


# ============================================================
# MÓDULO: VENTA
# ============================================================
def modulo_venta():
    st.header("⚡ Venta en Vivo")
    user = st.session_state.user
    locales = obtener_locales()
    sorteos = obtener_sorteos()

    if sorteos.empty:
        st.warning("⚠️ No hay sorteos abiertos. Crea uno en **🎲 Sorteos**.")
        return

    col1, col2 = st.columns([1, 1])
    with col1:
        if user["rol"] == "admin":
            local_sel = st.selectbox("🏪 Banca", locales["nombre"].tolist())
            local_id = int(locales[locales["nombre"] == local_sel]["id"].values[0])
        else:
            local_id = user["local_id"]
            local_nombre = locales[locales["id"] == local_id]["nombre"].values
            local_sel = local_nombre[0] if len(local_nombre) else "Sin asignar"
            st.info(f"🏪 Banca: **{local_sel}**")

        saldo = obtener_saldo_banca(local_id)
        color = "green" if saldo > 5000 else "orange" if saldo > 0 else "red"
        st.markdown(f"💵 **Saldo disponible:** :{color}[**${saldo:,.2f}**]")

        sorteo_opciones = {}
        for _, r in sorteos.iterrows():
            key = f"{r['loteria']} - {r['producto']} ({r['hora']}) #{r['id']}"
            sorteo_opciones[key] = r["id"]
        sorteo_sel = st.selectbox("🎯 Sorteo", list(sorteo_opciones.keys()))
        sorteo_id = sorteo_opciones[sorteo_sel]

        tipo = st.selectbox("🎲 Tipo de jugada", ["Fijo", "Parle", "Pale", "Tripleta"])

        if tipo == "Fijo":
            numero = st.text_input("Número (00-99)", max_chars=2, placeholder="07")
            numeros = [numero] if numero else []
        elif tipo in ("Parle", "Pale"):
            n1 = st.text_input("1er número", max_chars=2, key="p1")
            n2 = st.text_input("2do número", max_chars=2, key="p2")
            numeros = [n1, n2]
        else:
            n1 = st.text_input("Número 1", max_chars=2, key="t1")
            n2 = st.text_input("Número 2", max_chars=2, key="t2")
            n3 = st.text_input("Número 3", max_chars=2, key="t3")
            numeros = [n1, n2, n3]

        monto = st.number_input("💵 Monto apostado", min_value=1.0, value=10.0, step=5.0)
        cliente = st.text_input("👤 Cliente", placeholder="Anónimo")
        tel_cliente = st.text_input("📱 WhatsApp del cliente (opcional)")

    with col2:
        st.markdown("### 🧾 Resumen del Ticket")
        numeros_validos = [n.zfill(2) for n in numeros
                           if n and n.isdigit() and 0 <= int(n) <= 99]
        mult = MULTIPLICADORES[tipo]
        premio = monto * mult if len(numeros_validos) == len(numeros) else 0

        st.markdown(f"""
        - **Tipo:** {tipo}
        - **Números:** {', '.join(numeros_validos) if numeros_validos else '—'}
        - **Monto:** ${monto:.2f}
        - **Multiplicador:** x{mult}
        - **Premio potencial:** :green[**${premio:,.2f}**]
        """)

        if st.button("✅ REGISTRAR VENTA", use_container_width=True, type="primary"):
            if len(numeros_validos) != len(numeros):
                st.error("❌ Números inválidos. Deben ser entre 00 y 99.")
            elif premio > saldo:
                st.error(f"❌ Saldo insuficiente. Saldo: ${saldo:,.2f} | "
                         f"Premio posible: ${premio:,.2f}")
            else:
                permitido, mensaje, disponible = verificar_limites_venta(
                    local_id, tipo, numeros_validos, monto
                )
                if not permitido:
                    st.error(mensaje)
                    auditar("VENTA_BLOQUEADA",
                            f"Límite: {tipo} {numeros_validos} | "
                            f"Monto: {monto} | Banca: {local_id}")
                    st.stop()

                numero_final = "-".join(numeros_validos)
                conn = conectar()
                c = conn.cursor()
                c.execute("""INSERT INTO ventas 
                    (sorteo_id, local_id, usuario_id, numero, tipo, monto, premio_potencial,
                     cliente, telefono_cliente, fecha)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (sorteo_id, local_id, user["id"], numero_final, tipo, monto, premio,
                           cliente or "Anónimo", tel_cliente or "",
                           datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                venta_id = c.lastrowid
                conn.commit()
                conn.close()

                st.success(f"✅ Venta #{venta_id}: {tipo} {numero_final} por ${monto:.2f}")

                datos_ticket = {
                    "banca": local_sel,
                    "direccion": "Av. Principal #1, Santo Domingo",
                    "vendedor": user["nombre"],
                    "sorteo": sorteo_sel,
                    "tipo": tipo,
                    "numero": numero_final,
                    "monto": monto,
                    "premio": premio,
                    "cliente": cliente or "Anónimo",
                    "ticket_id": f"{venta_id:06d}",
                }
                archivo = generar_ticket(datos_ticket, f"ticket_{venta_id}.pdf")
                with open(archivo, "rb") as f:
                    pdf_bytes = f.read()
                st.download_button(
                    label="🖨️ DESCARGAR / IMPRIMIR TICKET (con QR)",
                    data=pdf_bytes,
                    file_name=f"ticket_{venta_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary"
                )
                st.balloons()

    st.markdown("---")
    st.subheader("📋 Ventas recientes de este sorteo")
    conn = conectar()
    df = pd.read_sql_query(f"""
        SELECT v.id, v.numero, v.tipo, v.monto, v.premio_potencial, v.cliente, v.fecha,
               u.nombre AS vendedor, l.nombre AS banca
        FROM ventas v
        JOIN usuarios u ON u.id = v.usuario_id
        JOIN locales l ON l.id = v.local_id
        WHERE v.sorteo_id = {sorteo_id}
        ORDER BY v.id DESC LIMIT 30
    """, conn)
    conn.close()
    if not df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.metric("💰 Total vendido en este sorteo", f"${df['monto'].sum():,.2f}")


# ============================================================
# MÓDULO: SORTEOS
# ============================================================
def modulo_sorteos():
    st.header("🎲 Gestión de Sorteos")
    user = st.session_state.user
    tab1, tab2 = st.tabs(["➕ Crear sorteo", "🏁 Cerrar y sortear"])

    with tab1:
        with st.form("nuevo_sorteo"):
            col1, col2, col3 = st.columns(3)
            with col1:
                loteria = st.selectbox("Lotería", list(LOTERIAS.keys()))
            with col2:
                producto = st.selectbox("Producto", list(LOTERIAS[loteria].keys()))
            with col3:
                fecha = st.date_input("Fecha", value=date.today())
            hora_sugerida = LOTERIAS[loteria][producto]["horario"]
            hora = st.text_input("Hora", value=hora_sugerida)
            if user["rol"] == "admin":
                locales = obtener_locales()
                local_sel = st.selectbox("Banca", ["TODAS"] + locales["nombre"].tolist())
            else:
                local_sel = "TODAS"
            if st.form_submit_button("Crear sorteo", use_container_width=True):
                local_id = None
                if local_sel != "TODAS":
                    loc_df = obtener_locales()
                    local_id = int(loc_df[loc_df["nombre"] == local_sel]["id"].values[0])
                conn = conectar()
                c = conn.cursor()
                c.execute("""INSERT INTO sorteos (loteria, producto, fecha, hora, local_id, estado)
                             VALUES (?, ?, ?, ?, ?, 'abierto')""",
                          (loteria, producto, str(fecha), hora, local_id))
                conn.commit()
                conn.close()
                st.success(f"✅ Sorteo **{loteria} - {producto}** creado.")
                st.rerun()

    with tab2:
        sorteos = obtener_sorteos(abiertos=True)
        if sorteos.empty:
            st.info("No hay sorteos abiertos.")
            return
        opciones = {f"#{r['id']} - {r['loteria']} {r['producto']} ({r['fecha']} {r['hora']})": r["id"]
                    for _, r in sorteos.iterrows()}
        sel = st.selectbox("Sorteo a cerrar", list(opciones.keys()))
        sorteo_id = opciones[sel]
        ganador = st.text_input("🏆 Número ganador (00-99)", max_chars=2)

        if st.button("🎰 CERRAR Y SORTEAR (con animación)", type="primary",
                     use_container_width=True):
            if not ganador.isdigit() or not (0 <= int(ganador) <= 99):
                st.error("❌ Número ganador inválido.")
                return
            ganador = ganador.zfill(2)
            st.markdown("### 🎰 Girando la ruleta...")
            placeholder = st.empty()
            for i in range(25):
                num_aleatorio = f"{i % 100:02d}"
                placeholder.markdown(
                    f"<h1 style='text-align:center;color:#FFD700;font-size:80px;"
                    f"text-shadow:3px 3px 6px #000;'>🎰 {num_aleatorio} 🎰</h1>",
                    unsafe_allow_html=True
                )
                time.sleep(0.08)
            placeholder.markdown(
                f"<h1 style='text-align:center;color:#1B5E20;font-size:100px;"
                f"text-shadow:4px 4px 8px #FFD700;'>🏆 {ganador} 🏆</h1>",
                unsafe_allow_html=True
            )
            st.balloons()
            conn = conectar()
            c = conn.cursor()
            c.execute("UPDATE sorteos SET estado='cerrado', numero_ganador=? WHERE id=?",
                      (ganador, sorteo_id))
            c.execute("""SELECT id, numero, tipo, monto, premio_potencial
                         FROM ventas WHERE sorteo_id=? AND estado='activa'""", (sorteo_id,))
            ventas = c.fetchall()
            total_pagado = 0
            ganadores_lista = []
            for v in ventas:
                v_id, numeros_v, tipo_v, monto_v, premio_pot = v
                if ganador in numeros_v.split("-"):
                    c.execute("""UPDATE ventas SET estado='ganadora', premio_pagado=?
                                 WHERE id=?""", (premio_pot, v_id))
                    total_pagado += premio_pot
                    ganadores_lista.append((numeros_v, tipo_v, monto_v, premio_pot))
                else:
                    c.execute("UPDATE ventas SET estado='perdida' WHERE id=?", (v_id,))
            conn.commit()
            conn.close()
            st.success(f"✅ Sorteo cerrado. Número ganador: **{ganador}**")
            if ganadores_lista:
                st.markdown("### 🏆 Ganadores")
                df_g = pd.DataFrame(ganadores_lista,
                                    columns=["Números", "Tipo", "Monto", "Premio"])
                st.dataframe(df_g, use_container_width=True, hide_index=True)
                st.metric("💸 Total pagado en premios", f"${total_pagado:,.2f}")
                enviar_telegram(
                    f"🏆 <b>SORTEO CERRADO</b>\n\n"
                    f"Número ganador: <b>{ganador}</b>\n"
                    f"Ganadores: {len(ganadores_lista)}\n"
                    f"Total pagado: ${total_pagado:,.2f}"
                )
            else:
                st.info("Nadie ganó este sorteo. 🎉 Ganancia completa.")


# ============================================================
# MÓDULO: CUADRE
# ============================================================
def modulo_cuadre():
    st.header("📊 Cuadre y Reportes en Vivo")
    user = st.session_state.user
    col1, col2, col3 = st.columns(3)
    with col1:
        fecha_ini = st.date_input("Desde", value=date.today())
    with col2:
        fecha_fin = st.date_input("Hasta", value=date.today())
    with col3:
        locales = obtener_locales()
        if user["rol"] == "admin":
            local_sel = st.selectbox("Banca", ["TODOS"] + locales["nombre"].tolist())
        else:
            local_sel = locales[locales["id"] == user["local_id"]]["nombre"].values[0]

    filtro_local = ""
    if local_sel != "TODOS":
        lid = int(locales[locales["nombre"] == local_sel]["id"].values[0])
        filtro_local = f" AND v.local_id = {lid}"

    conn = conectar()
    df = pd.read_sql_query(f"""
        SELECT v.*, u.nombre AS vendedor, l.nombre AS banca,
               s.loteria || ' - ' || s.producto AS sorteo
        FROM ventas v
        JOIN usuarios u ON u.id = v.usuario_id
        JOIN locales l ON l.id = v.local_id
        JOIN sorteos s ON s.id = v.sorteo_id
        WHERE DATE(v.fecha) BETWEEN '{fecha_ini}' AND '{fecha_fin}' {filtro_local}
        ORDER BY v.fecha DESC
    """, conn)
    conn.close()

    if df.empty:
        st.info("No hay ventas en el rango seleccionado.")
        return

    total_vendido = df["monto"].sum()
    total_premios = df[df["estado"] == "ganadora"]["premio_pagado"].sum()
    ganancia_neta = total_vendido - total_premios

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💰 Total vendido", f"${total_vendido:,.2f}")
    k2.metric("🏆 Premios pagados", f"${total_premios:,.2f}")
    k3.metric("📈 Ganancia neta", f"${ganancia_neta:,.2f}",
              delta="✅ Positiva" if ganancia_neta >= 0 else "⚠️ Pérdida")
    k4.metric("🎫 Tickets", len(df))

    st.markdown("---")
    tab1, tab2, tab3, tab4 = st.tabs(["🏪 Por banca", "👥 Por trabajador",
                                       "🎰 Por número", "📋 Detalle"])
    with tab1:
        res = df.groupby("banca").agg(
            Tickets=("id", "count"),
            Vendido=("monto", "sum"),
            Premios=("premio_pagado", "sum")
        ).reset_index()
        res["Ganancia"] = res["Vendido"] - res["Premios"]
        st.dataframe(res, use_container_width=True, hide_index=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Vendido", x=res["banca"], y=res["Vendido"],
                             marker_color="#1B5E20"))
        fig.add_trace(go.Bar(name="Premios", x=res["banca"], y=res["Premios"],
                             marker_color="#C62828"))
        fig.add_trace(go.Bar(name="Ganancia", x=res["banca"], y=res["Ganancia"],
                             marker_color="#FFD700"))
        fig.update_layout(barmode="group", height=400)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        res = df.groupby("vendedor").agg(
            Tickets=("id", "count"),
            Vendido=("monto", "sum"),
            Premios=("premio_pagado", "sum")
        ).reset_index()
        res["Ganancia"] = res["Vendido"] - res["Premios"]
        st.dataframe(res, use_container_width=True, hide_index=True)

    with tab3:
        res = df.groupby("numero").agg(
            Veces=("id", "count"),
            Total=("monto", "sum"),
            Premios=("premio_pagado", "sum")
        ).reset_index().sort_values("Total", ascending=False)
        st.dataframe(res, use_container_width=True, hide_index=True)
        fig = px.bar(res.head(15), x="numero", y="Total",
                     title="Top 15 números más vendidos",
                     color="Total", color_continuous_scale="Greens")
        st.plotly_chart(fig, use_container_width=True)

    with tab4:
        st.dataframe(df[["fecha", "banca", "vendedor", "sorteo", "numero",
                         "tipo", "monto", "premio_pagado", "estado", "cliente"]],
                     use_container_width=True, hide_index=True)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Descargar CSV", csv, "reporte.csv", "text/csv")


# ============================================================
# MÓDULO: LÍMITES
# ============================================================
def modulo_limites():
    st.header("🔒 Control de Límites de la Red")
    user = st.session_state.user
    if user["rol"] != "admin":
        st.error("⛔ Solo el administrador puede gestionar límites.")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "➕ Crear límite", "📋 Límites activos", "📊 En vivo", "⚡ Acciones rápidas"
    ])
    locales = obtener_locales()

    with tab1:
        st.subheader("Crear nuevo límite")
        with st.form("nuevo_limite"):
            col1, col2 = st.columns(2)
            with col1:
                tipo_jugada = st.selectbox("🎲 Tipo de jugada",
                                           ["Fijo", "Parle", "Pale", "Tripleta"])
                combinacion_input = st.text_input("🔢 Combinación",
                                                  placeholder="07  o  07-23  o  07-23-45")
                monto_maximo = st.number_input("💰 Monto máximo",
                                               min_value=0.0, value=500.0, step=100.0,
                                               help="0 = BLOQUEAR totalmente")
            with col2:
                aplicar_a = st.radio("🌐 Aplicar a",
                                     ["Todas las bancas",
                                      "Una banca específica",
                                      "Varias bancas"])
                locales_seleccionados = []
                if aplicar_a == "Una banca específica":
                    loc_sel = st.selectbox("Banca", locales["nombre"].tolist())
                    loc_id = int(locales[locales["nombre"] == loc_sel]["id"].values[0])
                    locales_seleccionados = [loc_id]
                elif aplicar_a == "Varias bancas":
                    for _, loc in locales.iterrows():
                        if st.checkbox(loc["nombre"], key=f"chk_{loc['id']}"):
                            locales_seleccionados.append(int(loc["id"]))
                st.markdown("**⏰ Restricción horaria (opcional)**")
                col_h1, col_h2 = st.columns(2)
                hora_inicio = col_h1.text_input("Desde (HH:MM)", placeholder="00:00")
                hora_fin = col_h2.text_input("Hasta (HH:MM)", placeholder="23:59")

            if st.form_submit_button("✅ Crear límite",
                                     use_container_width=True, type="primary"):
                partes = [p.strip().zfill(2)
                          for p in combinacion_input.split("-") if p.strip()]
                if not partes or not all(p.isdigit() and 0 <= int(p) <= 99 for p in partes):
                    st.error("❌ Combinación inválida. Ej: `07`, `07-23`, `07-23-45`")
                elif tipo_jugada == "Fijo" and len(partes) != 1:
                    st.error("❌ 'Fijo' debe tener 1 número")
                elif tipo_jugada in ("Parle", "Pale") and len(partes) != 2:
                    st.error("❌ 'Parle/Pale' debe tener 2 números")
                elif tipo_jugada == "Tripleta" and len(partes) != 3:
                    st.error("❌ 'Tripleta' debe tener 3 números")
                else:
                    combinacion = "-".join(partes)
                    conn = conectar()
                    c = conn.cursor()
                    if aplicar_a == "Todas las bancas":
                        c.execute("""INSERT INTO limites 
                            (tipo_jugada, combinacion, monto_maximo, aplica_todas,
                             hora_inicio, hora_fin, creado_por, fecha_creacion)
                            VALUES (?, ?, ?, 1, ?, ?, ?, ?)""",
                                  (tipo_jugada, combinacion, monto_maximo,
                                   hora_inicio or None, hora_fin or None,
                                   user["id"],
                                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    else:
                        for lid in locales_seleccionados:
                            c.execute("""INSERT INTO limites 
                                (tipo_jugada, combinacion, monto_maximo, local_id,
                                 hora_inicio, hora_fin, creado_por, fecha_creacion)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                                      (tipo_jugada, combinacion, monto_maximo, lid,
                                       hora_inicio or None, hora_fin or None,
                                       user["id"],
                                       datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit()
                    conn.close()
                    alcance = ("TODAS las bancas" if aplicar_a == "Todas las bancas"
                               else f"{len(locales_seleccionados)} banca(s)")
                    st.success(f"✅ Límite creado: **{tipo_jugada} {combinacion}** "
                               f"→ máx. **${monto_maximo:,.2f}** en **{alcance}**")
                    auditar("CREAR_LIMITE",
                            f"{tipo_jugada} {combinacion} = ${monto_maximo} → {alcance}")
                    enviar_telegram(
                        f"🔒 <b>NUEVO LÍMITE ACTIVADO</b>\n\n"
                        f"Tipo: {tipo_jugada}\n"
                        f"Combinación: <b>{combinacion}</b>\n"
                        f"Monto máx: ${monto_maximo:,.2f}\n"
                        f"Alcance: {alcance}"
                    )
                    st.rerun()

    with tab2:
        st.subheader("Límites activos en la red")
        conn = conectar()
        df = pd.read_sql_query("""
            SELECT lim.id, lim.tipo_jugada, lim.combinacion, lim.monto_maximo,
                   lim.aplica_todas, lim.hora_inicio, lim.hora_fin, lim.fecha_creacion,
                   l.nombre AS banca_especifica
            FROM limites lim
            LEFT JOIN locales l ON l.id = lim.local_id
            WHERE lim.activo = 1
            ORDER BY lim.id DESC
        """, conn)
        conn.close()
        if df.empty:
            st.info("No hay límites activos.")
        else:
            df["alcance"] = df.apply(
                lambda r: "🌐 TODAS" if r["aplica_todas"] == 1
                else f"🏪 {r['banca_especifica']}", axis=1)
            df["horario"] = df.apply(
                lambda r: f"{r['hora_inicio']} - {r['hora_fin']}"
                if r["hora_inicio"] and r["hora_fin"] else "Siempre", axis=1)
            df["bloqueo_total"] = df["monto_maximo"].apply(
                lambda x: "🚫 SÍ" if x == 0 else "No")
            df_mostrar = df[["id", "tipo_jugada", "combinacion", "monto_maximo",
                             "alcance", "horario", "bloqueo_total", "fecha_creacion"]]
            df_mostrar.columns = ["ID", "Tipo", "Combinación", "Máx",
                                  "Alcance", "Horario", "Bloqueo", "Creado"]
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("#### 🗑️ Desactivar límite")
            id_desactivar = st.selectbox("ID del límite a desactivar",
                                         df["id"].tolist())
            if st.button("🚫 Desactivar límite", type="secondary"):
                conn = conectar()
                c = conn.cursor()
                c.execute("UPDATE limites SET activo=0 WHERE id=?", (id_desactivar,))
                conn.commit()
                conn.close()
                st.success(f"✅ Límite #{id_desactivar} desactivado.")
                auditar("DESACTIVAR_LIMITE", f"ID {id_desactivar}")
                st.rerun()

    with tab3:
        st.subheader("📊 Consumo de límites en vivo (HOY)")
        conn = conectar()
        limites = pd.read_sql_query("""
            SELECT id, tipo_jugada, combinacion, monto_maximo, aplica_todas, local_id
            FROM limites WHERE activo=1
        """, conn)
        if limites.empty:
            st.info("No hay límites activos para monitorear.")
            conn.close()
            return
        for _, lim in limites.iterrows():
            tipo = lim["tipo_jugada"]
            comb = lim["combinacion"]
            maximo = lim["monto_maximo"]
            todas = lim["aplica_todas"]
            local_esp = lim["local_id"]
            if todas:
                q = f"""SELECT COALESCE(SUM(monto),0) AS total FROM ventas
                        WHERE numero LIKE '%{comb}%' AND tipo='{tipo}'
                          AND estado='activa' AND DATE(fecha)=DATE('now')"""
            else:
                q = f"""SELECT COALESCE(SUM(monto),0) AS total FROM ventas
                        WHERE local_id={local_esp} AND numero LIKE '%{comb}%' 
                          AND tipo='{tipo}' AND estado='activa' 
                          AND DATE(fecha)=DATE('now')"""
            vendido = pd.read_sql_query(q, conn).iloc[0]["total"]
            porcentaje = (vendido / maximo * 100) if maximo > 0 else 100
            if porcentaje >= 100:
                color, estado = "🔴", "AGOTADO"
            elif porcentaje >= 80:
                color, estado = "🟠", "CRÍTICO"
            elif porcentaje >= 50:
                color, estado = "🟡", "MEDIO"
            else:
                color, estado = "🟢", "OK"
            alcance = "TODAS" if todas else f"Banca #{local_esp}"
            st.markdown(f"**{color} {tipo} {comb}** — {alcance} — {estado}")
            st.progress(min(porcentaje / 100, 1.0))
            st.caption(f"Vendido: ${vendido:,.2f} / ${maximo:,.2f} "
                       f"({porcentaje:.1f}%) | Disponible: ${max(0, maximo - vendido):,.2f}")
            st.markdown("")
        conn.close()

    with tab4:
        st.subheader("⚡ Acciones rápidas")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🚫 Bloquear TODOS los pales")
            if st.button("Bloquear pales en toda la red", use_container_width=True):
                conn = conectar()
                c = conn.cursor()
                for i in range(100):
                    for j in range(i + 1, 100):
                        comb = f"{i:02d}-{j:02d}"
                        c.execute("""INSERT INTO limites 
                            (tipo_jugada, combinacion, monto_maximo, aplica_todas,
                             creado_por, fecha_creacion)
                            VALUES ('Parle', ?, 0, 1, ?, ?)""",
                                  (comb, user["id"],
                                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                conn.close()
                st.success("✅ Todos los pales bloqueados.")
                auditar("BLOQUEO_MASIVO", "Todos los pales")
        with col2:
            st.markdown("#### 💰 Límite global por número")
            limite_global = st.number_input("Máximo por número",
                                            min_value=0.0, value=1000.0, step=100.0)
            if st.button("Aplicar a los 100 números", use_container_width=True):
                conn = conectar()
                c = conn.cursor()
                for i in range(100):
                    num = f"{i:02d}"
                    c.execute("""INSERT INTO limites 
                        (tipo_jugada, combinacion, monto_maximo, aplica_todas,
                         creado_por, fecha_creacion)
                        VALUES ('Fijo', ?, ?, 1, ?, ?)""",
                              (num, limite_global, user["id"],
                               datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                conn.close()
                st.success(f"✅ Límite de ${limite_global:,.2f} aplicado.")


# ============================================================
# MÓDULO: ADMINISTRACIÓN
# ============================================================
def modulo_admin():
    st.header("⚙️ Administración del Consorcio")
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏪 Bancas", "👥 Usuarios", "💵 Caja", "💰 Capital", "💾 Respaldos"
    ])

    with tab1:
        with st.form("nuevo_local"):
            st.subheader("Nueva banca")
            col1, col2 = st.columns(2)
            nombre = col1.text_input("Nombre")
            encargado = col2.text_input("Encargado")
            direccion = col1.text_input("Dirección")
            telefono = col2.text_input("Teléfono")
            capital = st.number_input("Capital inicial", min_value=0.0,
                                       value=50000.0, step=1000.0)
            if st.form_submit_button("Agregar", use_container_width=True):
                try:
                    conn = conectar()
                    c = conn.cursor()
                    c.execute("""INSERT INTO locales 
                                 (nombre, direccion, encargado, telefono, capital_inicial)
                                 VALUES (?, ?, ?, ?, ?)""",
                              (nombre, direccion, encargado, telefono, capital))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Banca **{nombre}** creada.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        st.subheader("Bancas registradas")
        locales = obtener_locales()
        if not locales.empty:
            locales["Saldo actual"] = locales["id"].apply(obtener_saldo_banca)
            st.dataframe(locales[["id", "nombre", "encargado", "telefono",
                                   "capital_inicial", "Saldo actual"]],
                         use_container_width=True, hide_index=True)

    with tab2:
        with st.form("nuevo_user"):
            st.subheader("Nuevo trabajador")
            col1, col2 = st.columns(2)
            usuario = col1.text_input("Usuario")
            clave = col2.text_input("Contraseña", type="password")
            nombre = col1.text_input("Nombre completo")
            rol = col2.selectbox("Rol", ["vendedor", "supervisor", "admin"])
            locales = obtener_locales()
            local_sel = st.selectbox("Banca asignada", locales["nombre"].tolist())
            if st.form_submit_button("Crear usuario", use_container_width=True):
                try:
                    local_id = int(locales[locales["nombre"] == local_sel]["id"].values[0])
                    conn = conectar()
                    c = conn.cursor()
                    c.execute("""INSERT INTO usuarios (usuario, clave, nombre, rol, local_id)
                                 VALUES (?, ?, ?, ?, ?)""",
                              (usuario, hash_clave(clave), nombre, rol, local_id))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Usuario **{usuario}** creado.")
                except Exception as e:
                    st.error(f"Error: {e}")
        st.subheader("Usuarios registrados")
        conn = conectar()
        df = pd.read_sql_query("""
            SELECT u.id, u.usuario, u.nombre, u.rol, l.nombre AS banca, u.activo
            FROM usuarios u LEFT JOIN locales l ON l.id = u.local_id
        """, conn)
        conn.close()
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("Movimientos de caja")
        locales = obtener_locales()
        with st.form("mov"):
            col1, col2, col3 = st.columns(3)
            local_sel = col1.selectbox("Banca", locales["nombre"].tolist(),
                                       key="caja_local")
            tipo = col2.selectbox("Tipo", ["Gasto", "Ingreso"])
            monto = col3.number_input("Monto", min_value=0.01, value=100.0)
            desc = st.text_input("Descripción")
            if st.form_submit_button("Registrar"):
                local_id = int(locales[locales["nombre"] == local_sel]["id"].values[0])
                conn = conectar()
                c = conn.cursor()
                c.execute("""INSERT INTO caja 
                             (local_id, usuario_id, tipo, monto, descripcion, fecha)
                             VALUES (?, ?, ?, ?, ?, ?)""",
                          (local_id, st.session_state.user["id"], tipo, monto, desc,
                           datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                conn.close()
                st.success("✅ Movimiento registrado.")
        conn = conectar()
        df = pd.read_sql_query("""
            SELECT c.id, l.nombre AS banca, c.tipo, c.monto, c.descripcion, c.fecha
            FROM caja c JOIN locales l ON l.id = c.local_id
            ORDER BY c.id DESC LIMIT 50
        """, conn)
        conn.close()
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tab4:
        st.subheader("💰 Gestión de capital")
        locales = obtener_locales()
        with st.form("capital_mov"):
            col1, col2, col3 = st.columns(3)
            local_sel = col1.selectbox("Banca", locales["nombre"].tolist(),
                                       key="cap_local")
            tipo = col2.selectbox("Tipo", ["Ingreso", "Retiro"])
            monto = col3.number_input("Monto", min_value=0.01, value=1000.0,
                                       step=500.0)
            desc = st.text_input("Descripción")
            if st.form_submit_button("Registrar movimiento"):
                local_id = int(locales[locales["nombre"] == local_sel]["id"].values[0])
                conn = conectar()
                c = conn.cursor()
                c.execute("""INSERT INTO capital 
                             (local_id, tipo, monto, descripcion, fecha)
                             VALUES (?, ?, ?, ?, ?)""",
                          (local_id, tipo, monto, desc,
                           datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                conn.close()
                st.success("✅ Movimiento registrado.")
        if not locales.empty:
            saldos_data = []
            for _, loc in locales.iterrows():
                saldos_data.append({
                    "Banca": loc["nombre"],
                    "Capital inicial": f"${loc['capital_inicial']:,.2f}",
                    "Saldo actual": f"${obtener_saldo_banca(loc['id']):,.2f}"
                })
            st.dataframe(pd.DataFrame(saldos_data),
                         use_container_width=True, hide_index=True)

    with tab5:
        st.subheader("💾 Respaldos de la base de datos")
        if st.button("🔄 Crear respaldo ahora", use_container_width=True):
            archivo = crear_respaldo()
            if archivo:
                st.success(f"✅ Respaldo creado: {archivo}")
                with open(archivo, "rb") as f:
                    st.download_button("📥 Descargar respaldo",
                                       f.read(),
                                       file_name=os.path.basename(archivo),
                                       mime="application/zip")
            else:
                st.error("❌ No se pudo crear el respaldo.")

        st.markdown("#### Respaldos existentes")
        if os.path.exists(BACKUP_DIR):
            archivos = sorted(os.listdir(BACKUP_DIR), reverse=True)
            if archivos:
                for a in archivos[:20]:
                    st.text(f"📦 {a}")
            else:
                st.info("Aún no hay respaldos.")


# ============================================================
# DASHBOARD ADMIN
# ============================================================
def dashboard_admin():
    st.markdown("### 👑 Panel del Dueño - Monitoreo en Vivo")
    col_refresh, col_info = st.columns([1, 3])
    with col_refresh:
        auto = st.toggle("🔄 Auto-actualizar (10s)", value=True)
    with col_info:
        st.caption(f"🕐 Última actualización: {datetime.now().strftime('%H:%M:%S')}")
    if auto:
        time.sleep(10)
        st.rerun()

    hoy = date.today().strftime("%Y-%m-%d")
    conn = conectar()
    df_hoy = pd.read_sql_query(f"""
        SELECT v.local_id, l.nombre AS banca,
               SUM(v.monto) AS vendido, COUNT(*) AS tickets,
               SUM(CASE WHEN v.estado='ganadora' THEN v.premio_pagado ELSE 0 END) AS premios
        FROM ventas v JOIN locales l ON l.id = v.local_id
        WHERE DATE(v.fecha) = '{hoy}'
        GROUP BY v.local_id, l.nombre
    """, conn)

    total_vendido = df_hoy["vendido"].sum() if not df_hoy.empty else 0
    total_premios = df_hoy["premios"].sum() if not df_hoy.empty else 0
    total_tickets = df_hoy["tickets"].sum() if not df_hoy.empty else 0
    ganancia_total = total_vendido - total_premios

    st.markdown("#### 💰 Resumen Global de HOY")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💰 Vendido total", f"${total_vendido:,.2f}")
    k2.metric("🏆 Premios pagados", f"${total_premios:,.2f}")
    k3.metric("📈 Ganancia neta", f"${ganancia_total:,.2f}",
              delta="✅ Positiva" if ganancia_total >= 0 else "⚠️ Pérdida")
    k4.metric("🎫 Tickets totales", total_tickets)

    # Alertas de límites críticos
    limites_df = pd.read_sql_query("""
        SELECT id, tipo_jugada, combinacion, monto_maximo, aplica_todas, local_id
        FROM limites WHERE activo=1
    """, conn)
    criticos = []
    for _, lim in limites_df.iterrows():
        cond = f"numero LIKE '%{lim['combinacion']}%' AND tipo='{lim['tipo_jugada']}'"
        if not lim["aplica_todas"]:
            cond += f" AND local_id={lim['local_id']}"
        q = f"""SELECT COALESCE(SUM(monto),0) AS total FROM ventas
                WHERE {cond} AND estado='activa' AND DATE(fecha)=DATE('now')"""
        vendido = pd.read_sql_query(q, conn).iloc[0]["total"]
        pct = (vendido / lim["monto_maximo"] * 100) if lim["monto_maximo"] > 0 else 100
        if pct >= 80:
            criticos.append({
                "Tipo": lim["tipo_jugada"],
                "Combinación": lim["combinacion"],
                "Vendido": f"${vendido:,.2f}",
                "Máximo": f"${lim['monto_maximo']:,.2f}",
                "Uso": f"{pct:.0f}%"
            })
    if criticos:
        st.error(f"⚠️ **{len(criticos)} límite(s) en estado crítico (≥80%)**")
        st.dataframe(pd.DataFrame(criticos), use_container_width=True,
                     hide_index=True)
    st.markdown("---")

    st.markdown("#### 🏪 Estado de cada Banca en Tiempo Real")
    locales = pd.read_sql_query("SELECT * FROM locales WHERE activo=1", conn)
    for _, local in locales.iterrows():
        lid = local["id"]
        ventas_local = pd.read_sql_query(f"""
            SELECT SUM(monto) AS vendido, COUNT(*) AS tickets,
                   SUM(CASE WHEN estado='ganadora' THEN premio_pagado ELSE 0 END) AS premios
            FROM ventas WHERE local_id={lid} AND DATE(fecha)='{hoy}'
        """, conn).iloc[0]
        vendedores = pd.read_sql_query(f"""
            SELECT u.nombre, s.ultimo_ping
            FROM sesiones s JOIN usuarios u ON u.id = s.usuario_id
            WHERE s.local_id = {lid}
              AND datetime(s.ultimo_ping) > datetime('now', '-5 minutes')
            ORDER BY s.ultimo_ping DESC
        """, conn)
        vendido = ventas_local["vendido"] or 0
        premios = ventas_local["premios"] or 0
        tickets = ventas_local["tickets"] or 0
        ganancia = vendido - premios
        saldo = obtener_saldo_banca(lid)
        if vendido == 0:
            estado = "⚪ Sin ventas"
        elif ganancia > 0:
            estado = "🟢 Ganando"
        else:
            estado = "🔴 Perdiendo"
        with st.expander(f"{estado}  **{local['nombre']}**  |  "
                         f"Vendido: ${vendido:,.2f}  |  "
                         f"Ganancia: ${ganancia:,.2f}  |  "
                         f"Saldo: ${saldo:,.2f}"):
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("💰 Vendido", f"${vendido:,.2f}")
            c2.metric("🏆 Premios", f"${premios:,.2f}")
            c3.metric("📈 Ganancia", f"${ganancia:,.2f}")
            c4.metric("🎫 Tickets", tickets)
            c5.metric("💵 Saldo", f"${saldo:,.2f}")
            if not vendedores.empty:
                st.markdown("**👥 Vendedores conectados:**")
                for _, v in vendedores.iterrows():
                    st.markdown(f"- 🟢 {v['nombre']} — {v['ultimo_ping']}")
            else:
                st.caption("⚫ Ningún vendedor conectado ahora")
            ultimas = pd.read_sql_query(f"""
                SELECT v.fecha, v.numero, v.tipo, v.monto, v.cliente, u.nombre AS vendedor
                FROM ventas v JOIN usuarios u ON u.id = v.usuario_id
                WHERE v.local_id = {lid} AND DATE(v.fecha) = '{hoy}'
                ORDER BY v.id DESC LIMIT 5
            """, conn)
            if not ultimas.empty:
                st.markdown("**⚡ Últimas 5 ventas:**")
                st.dataframe(ultimas, use_container_width=True, hide_index=True)
    conn.close()

    st.markdown("---")
    st.markdown("#### 📊 Comparativa por Banca (HOY)")
    if not df_hoy.empty:
        df_hoy["ganancia"] = df_hoy["vendido"] - df_hoy["premios"]
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Vendido", x=df_hoy["banca"],
                             y=df_hoy["vendido"], marker_color="#1B5E20"))
        fig.add_trace(go.Bar(name="Premios", x=df_hoy["banca"],
                             y=df_hoy["premios"], marker_color="#C62828"))
        fig.add_trace(go.Bar(name="Ganancia", x=df_hoy["banca"],
                             y=df_hoy["ganancia"], marker_color="#FFD700"))
        fig.update_layout(barmode="group", height=400)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("#### 🏆 Ranking de Vendedores (HOY)")
    conn = conectar()
    ranking = pd.read_sql_query(f"""
        SELECT u.nombre AS vendedor, l.nombre AS banca,
               COUNT(*) AS tickets, SUM(v.monto) AS total_vendido
        FROM ventas v
        JOIN usuarios u ON u.id = v.usuario_id
        JOIN locales l ON l.id = v.local_id
        WHERE DATE(v.fecha) = '{hoy}'
        GROUP BY u.id, u.nombre, l.nombre
        ORDER BY total_vendido DESC
    """, conn)
    conn.close()
    if not ranking.empty:
        st.dataframe(ranking, use_container_width=True, hide_index=True)
        fig = px.bar(ranking, x="vendedor", y="total_vendido", color="banca",
                     title="Ranking de vendedores",
                     color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(fig, use_container_width=True)


def dashboard_vendedor():
    st.header("🏠 Mi Banca")
    user = st.session_state.user
    hoy = date.today().strftime("%Y-%m-%d")
    local_id = user["local_id"]
    conn = conectar()
    ventas_hoy = pd.read_sql_query(f"""
        SELECT SUM(monto) AS total, COUNT(*) AS tickets,
               SUM(CASE WHEN estado='ganadora' THEN premio_pagado ELSE 0 END) AS premios
        FROM ventas
        WHERE usuario_id = {user['id']} AND DATE(fecha) = '{hoy}'
    """, conn).iloc[0]
    conn.close()
    total = ventas_hoy["total"] or 0
    premios = ventas_hoy["premios"] or 0
    tickets = ventas_hoy["tickets"] or 0
    saldo = obtener_saldo_banca(local_id) if local_id else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Mi venta hoy", f"${total:,.2f}")
    c2.metric("🏆 Premios pagados", f"${premios:,.2f}")
    c3.metric("🎫 Mis tickets", tickets)
    c4.metric("💵 Saldo banca", f"${saldo:,.2f}")


def dashboard():
    if st.session_state.user["rol"] == "admin":
        dashboard_admin()
    else:
        dashboard_vendedor()


# ============================================================
# MAIN
# ============================================================
def main():
    init_db()
    if "user" not in st.session_state:
        login()
        return

    try:
        conn = conectar()
        c = conn.cursor()
        c.execute("""UPDATE sesiones 
                     SET ultimo_ping = ?
                     WHERE id = (SELECT id FROM sesiones 
                                 WHERE usuario_id = ? ORDER BY id DESC LIMIT 1)""",
                  (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   st.session_state.user["id"]))
        conn.commit()
        conn.close()
    except Exception:
        pass

    if "ultima_alerta" not in st.session_state:
        st.session_state.ultima_alerta = 0
    if time.time() - st.session_state.ultima_alerta > 60:
        verificar_alertas()
        st.session_state.ultima_alerta = time.time()

    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state.user['nombre']}")
        st.caption(f"Rol: **{st.session_state.user['rol']}**")
        st.markdown("---")
        menu = ["🏠 Dashboard", "⚡ Venta en Vivo", "🎲 Sorteos",
                "📊 Cuadre y Reportes"]
        if st.session_state.user["rol"] == "admin":
            menu.append("🔒 Control de Límites")
            menu.append("⚙️ Administración")
        opcion = st.radio("Menú", menu, label_visibility="collapsed")
        st.markdown("---")
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            del st.session_state.user
            st.rerun()
        st.markdown("---")
        st.caption(f"🍀 {MARCA['nombre']}\n\n*{MARCA['slogan']}*")

    if opcion == "🏠 Dashboard":
        dashboard()
    elif opcion == "⚡ Venta en Vivo":
        modulo_venta()
    elif opcion == "🎲 Sorteos":
        modulo_sorteos()
    elif opcion == "📊 Cuadre y Reportes":
        modulo_cuadre()
    elif opcion == "🔒 Control de Límites":
        modulo_limites()
    elif opcion == "⚙️ Administración":
        modulo_admin()


if __name__ == "__main__":
    main()