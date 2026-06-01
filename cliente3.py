import tkinter as tk
import mysql.connector
import urllib.request
import json
import time
from datetime import datetime
import base64
import io
import threading
from PIL import Image, ImageTk

# Configuracion de red y base de datos
URL_ESP32  = "http://192.168.1.215"
URL_RASPI5 = "http://192.168.1.117:5000"

config = {
    'host': '192.168.1.212',  
    'user': 'fabricio',
    'password': 'efenomas',
    'database': 'basurero'    
}

# Estilos y colores
BG_DARK   = "#0D0F1A"; BG_CARD   = "#161929"; BG_INPUT  = "#1E2235"; BORDER    = "#2A2F4A"
TEXT_PRI  = "#E8EAFF"; TEXT_SEC  = "#7B82A8"; TEXT_HINT = "#454D70"
ACCENT_A  = "#6C63FF"; ACCENT_B  = "#00C2CB"; ACCENT_C  = "#00E899"; ACCENT_W  = "#FF6B6B"

FONT_TITLE  = ("Courier New", 22, "bold"); FONT_SUB    = ("Courier New", 11)
FONT_BTN    = ("Courier New", 12, "bold"); FONT_LABEL  = ("Courier New", 10)
FONT_INPUT  = ("Courier New", 13); FONT_SMALL  = ("Courier New", 9)

id_usuario_actual = ""
leyendo_datos = False 

# Inicializacion de ventana principal
root = tk.Tk()
root.title("DEEPRECYCLE - Control Center")
root.geometry("620x720")
root.configure(bg=BG_DARK)
root.resizable(False, False)

root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)
frame = tk.Frame(root, bg=BG_CARD)
frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
frame.grid_columnconfigure(0, weight=1)

# --- Helper widgets ---
def limpiar():
    for w in frame.winfo_children(): w.destroy()

def boton_moderno(texto, color, comando, parent, fill=True):
    outer = tk.Frame(parent, bg=color, padx=2, pady=0)
    if fill: outer.pack(fill="x", padx=30, pady=6)
    else: outer.pack(padx=10, pady=6)
    inner = tk.Frame(outer, bg=BG_INPUT, cursor="hand2"); inner.pack(fill="both")
    lbl = tk.Label(inner, text=texto, font=FONT_BTN, bg=BG_INPUT, fg=color, pady=13, anchor="center")
    lbl.pack(fill="both", expand=True)
    def on(e): inner.config(bg=color); lbl.config(bg=color, fg="white")
    def off(e): inner.config(bg=BG_INPUT); lbl.config(bg=BG_INPUT, fg=color)
    def click(e): comando()
    for w in (outer, inner, lbl):
        w.bind("<Enter>", on); w.bind("<Leave>", off); w.bind("<Button-1>", click)

def separador(parent, pady=10): tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=30, pady=pady)

def entry_widget(parent, placeholder="", show=None):
    wrap = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
    wrap.pack(fill="x", padx=30, pady=(0, 8))
    inner = tk.Frame(wrap, bg=BG_INPUT); inner.pack(fill="both")
    kw = dict(font=FONT_INPUT, bg=BG_INPUT, fg=TEXT_PRI, insertbackground=ACCENT_A, relief="flat", bd=8, highlightthickness=0)
    if show: kw["show"] = show
    e = tk.Entry(inner, **kw); e.pack(fill="x")
    def act(ev): wrap.config(bg=ACCENT_A)
    def des(ev): wrap.config(bg=BORDER)
    e.bind("<FocusIn>", lambda ev: (act(ev),)); e.bind("<FocusOut>", lambda ev: (des(ev),))
    return e

# --- Ventanas emergentes ---
def popup_error(titulo, mensaje): _popup(titulo, mensaje, ACCENT_W, "X " + titulo)
def popup_ok(titulo, mensaje): _popup(titulo, mensaje, ACCENT_C, "V " + titulo)
def popup_info(titulo, mensaje): _popup(titulo, mensaje, ACCENT_A, "O " + titulo)

def _popup(titulo, mensaje, color, header):
    win = tk.Toplevel(root); win.configure(bg=BG_CARD); win.resizable(False, False); win.transient(root)
    root.update_idletasks()
    x = root.winfo_x() + root.winfo_width()//2 - 220; y = root.winfo_y() + root.winfo_height()//2 - 100
    win.geometry(f"440x220+{x}+{y}")
    tk.Frame(win, bg=color, height=4).pack(fill="x")
    tk.Label(win, text=header, font=("Courier New", 13, "bold"), bg=BG_CARD, fg=color).pack(anchor="w", padx=24, pady=(16,4))
    tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=24)
    tk.Label(win, text=mensaje, font=FONT_LABEL, bg=BG_CARD, fg=TEXT_PRI, wraplength=390, justify="left").pack(anchor="w", padx=24, pady=12)
    btn = tk.Frame(win, bg=color, cursor="hand2"); btn.pack(pady=(0,18))
    lbl = tk.Label(btn, text="  OK  ", font=FONT_BTN, bg=color, fg="white", padx=20, pady=6); lbl.pack()
    def cerrar(e=None): win.destroy()
    btn.bind("<Button-1>", cerrar); lbl.bind("<Button-1>", cerrar)
    win.update_idletasks(); win.grab_set(); win.wait_window()

def popup_yesno(titulo, mensaje, color=ACCENT_A):
    result = [False]
    win = tk.Toplevel(root); win.configure(bg=BG_CARD); win.resizable(False, False); win.transient(root)
    root.update_idletasks()
    x = root.winfo_x() + root.winfo_width()//2 - 230; y = root.winfo_y() + root.winfo_height()//2 - 110
    win.geometry(f"460x210+{x}+{y}")
    tk.Frame(win, bg=color, height=4).pack(fill="x")
    tk.Label(win, text="? " + titulo, font=("Courier New", 13, "bold"), bg=BG_CARD, fg=color).pack(anchor="w", padx=24, pady=(16,4))
    tk.Label(win, text=mensaje, font=FONT_LABEL, bg=BG_CARD, fg=TEXT_PRI, wraplength=400, justify="left").pack(anchor="w", padx=24, pady=12)
    row = tk.Frame(win, bg=BG_CARD); row.pack(pady=(0,18))
    def _btn(parent, texto, accion, bg):
        f = tk.Frame(parent, bg=bg, cursor="hand2"); f.pack(side="left", padx=8)
        l = tk.Label(f, text=texto, font=FONT_BTN, bg=bg, fg="white", padx=18, pady=6); l.pack()
        def do(e=None): result[0] = accion; win.destroy()
        f.bind("<Button-1>", do); l.bind("<Button-1>", do)
    _btn(row, " Si ", True, ACCENT_C); _btn(row, " No ", False, ACCENT_W)
    win.update_idletasks(); win.grab_set(); win.wait_window()
    return result[0]

# --- DB Operations ---
def guardar_en_db(tabla, columnas, valores):
    try:
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        placeholder = ", ".join(["%s"] * len(valores))
        sql = f"INSERT INTO {tabla} ({columnas}) VALUES ({placeholder})"
        cursor.execute(sql, valores)
        conn.commit()
        cursor.close(); conn.close()
        return True
    except Exception as e:
        print(f"Error DB: {e}"); return False

# --- Autenticacion ---
def login_screen():
    global entry_id, entry_pass
    limpiar()
    banner = tk.Frame(frame, bg=ACCENT_A); banner.pack(fill="x")
    tk.Label(banner, text=" DEEPRECYCLE IOT", font=("Courier New", 16, "bold"), bg=ACCENT_A, fg="white").pack(side="left", padx=16, pady=12)
    
    tk.Label(frame, text="", bg=BG_CARD).pack(pady=8)
    tk.Label(frame, text="ACCESO AL SISTEMA", font=("Courier New", 20, "bold"), bg=BG_CARD, fg=TEXT_PRI).pack()
    tk.Label(frame, text="Ingrese sus credenciales", font=FONT_SUB, bg=BG_CARD, fg=TEXT_SEC).pack(pady=(4,20))
    separador(frame)

    tk.Label(frame, text="ID DE OPERADOR", font=FONT_LABEL, bg=BG_CARD, fg=TEXT_SEC).pack(anchor="w", padx=30, pady=(10,2))
    entry_id = entry_widget(frame)
    tk.Label(frame, text="CONTRASEÑA", font=FONT_LABEL, bg=BG_CARD, fg=TEXT_SEC).pack(anchor="w", padx=30, pady=(8,2))
    entry_pass = entry_widget(frame, show="*")
    
    boton_moderno("Conectar al servidor", ACCENT_A, guardar_usuario, frame)

def guardar_usuario():
    global id_usuario_actual
    entrada_id   = entry_id.get().strip()
    entrada_pass = entry_pass.get().strip()
    if not entrada_id.isdigit():
        popup_error("ID invalido", "El ID debe ser numerico.")
        return
    try:
        conexion = mysql.connector.connect(**config)
        cursor   = conexion.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE id = %s", (entrada_id,))
        usuario  = cursor.fetchone()
        if usuario:
            if usuario["password"] == entrada_pass:
                id_usuario_actual = int(entrada_id)
                menu_principal()
            else: popup_error("Acceso denegado", "Contrasena incorrecta.")
        else:
            if popup_yesno("Nuevo operador", f"El ID {entrada_id} no existe.\nCrear cuenta nueva?", ACCENT_A):
                cursor.execute("INSERT INTO usuarios (id, password, nombre_usuario) VALUES (%s, %s, %s)", (entrada_id, entrada_pass, f"Operador_{entrada_id}"))
                conexion.commit()
                id_usuario_actual = int(entrada_id)
                menu_principal()
        cursor.close(); conexion.close()
    except mysql.connector.Error as err:
        popup_error("Error DB", f"{err}")

# --- Menu principal ---
def menu_principal():
    global leyendo_datos
    leyendo_datos = False
    limpiar()

    status = tk.Frame(frame, bg=BG_DARK); status.pack(fill="x", padx=0, pady=0)
    tk.Label(status, text=f"CONECTADO | OP-{id_usuario_actual}", font=FONT_SMALL, bg=BG_DARK, fg=ACCENT_C).pack(side="left", padx=16, pady=6)

    tk.Label(frame, text="CONTROL BASURERO INTELIGENTE", font=("Courier New", 18, "bold"), bg=BG_CARD, fg=TEXT_PRI).pack(pady=(28, 4))
    separador(frame)

    boton_moderno("1. Adquisición Sensores (ESP32)", ACCENT_A, menu_config_telemetria, frame)
    boton_moderno("2. Revisar Niveles de Llenado", ACCENT_B, revisar_niveles_llenado, frame)
    boton_moderno("3. Revisar Alerta de Gas (MQ4)", ACCENT_W, revisar_alerta_gas, frame)
    boton_moderno("4. Base de Datos / Limpieza", ACCENT_C, menu_base_datos, frame)
    
    separador(frame)
    boton_moderno("Cerrar Sesion", TEXT_HINT, login_screen, frame)

# --- Nuevas Funciones de Revisión ---
def revisar_niveles_llenado():
    try:
        conexion = mysql.connector.connect(**config)
        cursor = conexion.cursor(dictionary=True)
        # Buscar el ultimo registro de niveles
        cursor.execute("SELECT * FROM ultrasonic_data ORDER BY timed DESC LIMIT 1")
        niveles = cursor.fetchone()
        cursor.close(); conexion.close()

        if niveles:
            # Crear una nueva ventana emergente personalizada
            win = tk.Toplevel(root)
            win.title("ESTADO DE LOS CONTENEDORES")
            win.configure(bg=BG_CARD)
            
            # Centrar la ventana
            root.update_idletasks()
            x = root.winfo_x() + root.winfo_width()//2 - 250
            y = root.winfo_y() + root.winfo_height()//2 - 150
            win.geometry(f"500x320+{x}+{y}")
            win.transient(root)
            win.grab_set()

            # Cabecera
            tk.Label(win, text="NIVELES ACTUALES DE LLENADO", font=("Courier New", 14, "bold"), bg=BG_CARD, fg=TEXT_PRI).pack(pady=(15, 5))
            tk.Label(win, text=f"Última lectura: {niveles['timed']}", font=FONT_SMALL, bg=BG_CARD, fg=TEXT_SEC).pack()

            # Contenedor para alinear los 4 basureros
            canvases_frame = tk.Frame(win, bg=BG_CARD)
            canvases_frame.pack(pady=20, fill="x", padx=10)

            # Función interna para dibujar cada tacho
            def dibujar_tacho(parent, titulo, pct, color):
                f = tk.Frame(parent, bg=BG_CARD)
                f.pack(side="left", expand=True)
                tk.Label(f, text=titulo, font=FONT_LABEL, bg=BG_CARD, fg=color).pack()

                # Lienzo de dibujo (Canvas)
                c = tk.Canvas(f, width=70, height=130, bg=BG_CARD, highlightthickness=0)
                c.pack(pady=5)

                # 1. Dibujar el contorno del basurero (vacio)
                c.create_rectangle(5, 5, 65, 125, outline=TEXT_SEC, width=3)
                
                # 2. Dibujar el liquido/relleno
                p = max(0, min(100, pct)) # Asegurar que este entre 0 y 100
                alto_maximo = 120 # Pixeles disponibles para llenar (de 5 a 125)
                alto_relleno = (alto_maximo * p) / 100
                
                # Coordenadas: (x1, y1, x2, y2). El y1 se calcula restando desde abajo
                y_inicio_relleno = 125 - alto_relleno
                c.create_rectangle(6, y_inicio_relleno, 64, 124, fill=color, outline="")

                # Porcentaje en texto
                tk.Label(f, text=f"{p:.1f}%", font=FONT_BTN, bg=BG_CARD, fg=TEXT_PRI).pack()

            # Dibujar los 4 basureros con los datos de la BD
            dibujar_tacho(canvases_frame, "Biológico", niveles['nivel_bio'], "#4CAF50")
            dibujar_tacho(canvases_frame, "Papel", niveles['nivel_paper'], "#2196F3")
            dibujar_tacho(canvases_frame, "Vidrio", niveles['nivel_vidrio'], "#9E9E9E")
            dibujar_tacho(canvases_frame, "Plástico", niveles['nivel_plastics'], "#FFC107")

            # Botón para cerrar
            btn_cerrar = tk.Button(win, text="Cerrar Visualización", command=win.destroy, bg=BG_INPUT, fg=TEXT_PRI, font=FONT_LABEL, relief="flat", cursor="hand2")
            btn_cerrar.pack(pady=10)

        else:
            popup_ok("Sin datos", "No hay registros de sensores en la base de datos todavía.")
    except Exception as e:
        popup_error("Error DB", str(e))

    
def revisar_alerta_gas():
    try:
        conexion = mysql.connector.connect(**config)
        cursor = conexion.cursor(dictionary=True)
        
        # MAGIA AQUÍ: Traemos SIEMPRE el último registro absoluto, sin filtrar por alertas
        cursor.execute("SELECT * FROM mq4_data ORDER BY timed DESC LIMIT 1")
        ultimo_dato = cursor.fetchone()
        cursor.close(); conexion.close()

        if ultimo_dato:
            # Evaluamos en Python el estado de ese último dato
            if ultimo_dato['alerta_gas'] == 1:
                info = f"Fecha y Hora: {ultimo_dato['timed']}\nVoltaje Detectado: {ultimo_dato['voltaje_v']} V\nLectura ADC: {ultimo_dato['valor_raw']}\n\n¡ALTO RIESGO! Inspeccionar contenedor biológico."
                popup_error("¡ALERTA DE METANO ACTIVA!", info)
            else:
                info = f"Última lectura: {ultimo_dato['timed']}\nNivel actual: {ultimo_dato['voltaje_v']} V (Seguro)"
                popup_ok("Aire Limpio", info)
        else:
            popup_info("Base de datos vacía", "No se ha registrado ninguna lectura del sensor MQ4 todavía.")
            
    except Exception as e:
        popup_error("Error DB", str(e))
# --- Configuracion de sensores ---
def menu_config_telemetria():
    limpiar()
    hdr = tk.Frame(frame, bg=ACCENT_A); hdr.pack(fill="x")
    tk.Label(hdr, text="  ADQUISICION DE SENSORES", font=("Courier New", 14, "bold"), bg=ACCENT_A, fg="white").pack(pady=10)

    tk.Label(frame, text="Duracion (segundos):", font=FONT_LABEL, bg=BG_CARD, fg=TEXT_SEC).pack(anchor="w", padx=30, pady=(15,2))
    entry_duracion = entry_widget(frame, placeholder="Ej: 10")

    tk.Label(frame, text="Intervalo (milisegundos):", font=FONT_LABEL, bg=BG_CARD, fg=TEXT_SEC).pack(anchor="w", padx=30, pady=(15,2))
    entry_intervalo = entry_widget(frame, placeholder="Ej: 500")

    def validar_e_iniciar():
        try:
            dur = int(entry_duracion.get().strip())
            inter = int(entry_intervalo.get().strip())
            if dur <= 0 or inter < 50:
                popup_error("Valores invalidos", "Duracion > 0 e intervalo > 50ms.")
                return
            pantalla_telemetria(dur, inter)
        except ValueError:
            popup_error("Error", "Ingrese numeros validos.")

    separador(frame)
    boton_moderno("Iniciar Muestreo", ACCENT_A, validar_e_iniciar, frame)
    boton_moderno("Volver", TEXT_HINT, menu_principal, frame)

# --- Funciones de calculo y UI para Telemetria ---
def calcular_porcentaje(dist_cm):
    # 60cm = 0%, 0cm = 100%
    if dist_cm > 60: dist_cm = 60
    if dist_cm < 0: dist_cm = 0
    return round(((60 - dist_cm) / 60) * 100, 1)

def pantalla_telemetria(duracion_seg, intervalo_ms):
    global leyendo_datos
    limpiar()
    leyendo_datos = True
    tiempo_inicio = time.time()

    hdr = tk.Frame(frame, bg=ACCENT_A); hdr.pack(fill="x")
    tk.Label(hdr, text=f"  MUESTREO EN CURSO ({duracion_seg}s)", font=("Courier New", 14, "bold"), bg=ACCENT_A, fg="white").pack(pady=10)

    panel = tk.Frame(frame, bg=BG_INPUT, bd=2, relief="groove"); panel.pack(fill="both", expand=True, padx=20, pady=10)
    lbl_tiempo = tk.Label(panel, text="Tiempo Restante: -- s", font=("Courier New", 14, "bold"), bg=BG_INPUT, fg=ACCENT_W)
    lbl_tiempo.pack(pady=10)

    # Labels para Ultrasonicos
    lbl_niveles = tk.Label(panel, text="Niveles de Llenado:", font=FONT_BTN, bg=BG_INPUT, fg=TEXT_PRI)
    lbl_niveles.pack()
    lbl_bio = tk.Label(panel, text="Bio: --%", font=FONT_LABEL, bg=BG_INPUT, fg="#4CAF50"); lbl_bio.pack()
    lbl_papel = tk.Label(panel, text="Papel: --%", font=FONT_LABEL, bg=BG_INPUT, fg="#2196F3"); lbl_papel.pack()
    lbl_vidrio = tk.Label(panel, text="Vidrio: --%", font=FONT_LABEL, bg=BG_INPUT, fg="#9E9E9E"); lbl_vidrio.pack()
    lbl_plastico = tk.Label(panel, text="Plastico: --%", font=FONT_LABEL, bg=BG_INPUT, fg="#FFC107"); lbl_plastico.pack()
    
    # Label para Gas MQ4
    tk.Label(panel, text="\nSensor Gas MQ4:", font=FONT_BTN, bg=BG_INPUT, fg=TEXT_PRI).pack()
    lbl_gas = tk.Label(panel, text="Voltaje: -- V | Estado: --", font=FONT_LABEL, bg=BG_INPUT, fg=ACCENT_W)
    lbl_gas.pack()

    lbl_estado = tk.Label(frame, text="Conectando...", font=FONT_SMALL, bg=BG_CARD, fg=TEXT_SEC)
    lbl_estado.pack(pady=10)

    def pedir_datos():
        global leyendo_datos
        if not leyendo_datos: return
        
        tiempo_actual = time.time()
        tiempo_transcurrido = tiempo_actual - tiempo_inicio
        tiempo_restante = max(0, duracion_seg - tiempo_transcurrido)
        lbl_tiempo.config(text=f"Tiempo Restante: {tiempo_restante:.1f} s")

        if tiempo_transcurrido >= duracion_seg:
            leyendo_datos = False
            lbl_estado.config(text="Muestreo Finalizado.", fg=ACCENT_C)
            lbl_tiempo.config(text="MUESTREO COMPLETADO", fg=ACCENT_C)
            return

        def fetch_and_save():
            try:
                req = urllib.request.urlopen(URL_ESP32, timeout=2)
                datos = json.loads(req.read())
                ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Calcular Niveles
                n_bio = calcular_porcentaje(datos['dist_bio'])
                n_papel = calcular_porcentaje(datos['dist_paper'])
                n_vidrio = calcular_porcentaje(datos['dist_vidrio'])
                n_plastico = calcular_porcentaje(datos['dist_plastics'])

                # Calcular Gas
                raw_gas = datos['mq4_raw']
                volts_gas = round(raw_gas * (3.3 / 4095), 2)
                alerta = 1 if volts_gas > 1.5 else 0
                estado_str = "ALERTA" if alerta else "Normal"

                # Actualizar UI con root.after para evitar bloqueos
                root.after(0, lambda: lbl_bio.config(text=f"Bio: {n_bio}% ({datos['dist_bio']}cm)"))
                root.after(0, lambda: lbl_papel.config(text=f"Papel: {n_papel}% ({datos['dist_paper']}cm)"))
                root.after(0, lambda: lbl_vidrio.config(text=f"Vidrio: {n_vidrio}% ({datos['dist_vidrio']}cm)"))
                root.after(0, lambda: lbl_plastico.config(text=f"Plastico: {n_plastico}% ({datos['dist_plastics']}cm)"))
                root.after(0, lambda: lbl_gas.config(text=f"Voltaje: {volts_gas} V | Estado: {estado_str}"))
                root.after(0, lambda: lbl_estado.config(text=f"Guardando a {intervalo_ms}ms...", fg=TEXT_PRI))

                # Guardar en BD
                guardar_en_db("ultrasonic_data", 
                              "idu, dist_bio, nivel_bio, dist_paper, nivel_paper, dist_plastics, nivel_plastics, dist_vidrio, nivel_vidrio, timed", 
                              (id_usuario_actual, datos['dist_bio'], n_bio, datos['dist_paper'], n_papel, datos['dist_plastics'], n_plastico, datos['dist_vidrio'], n_vidrio, ahora))
                
                guardar_en_db("mq4_data", "idu, valor_raw, voltaje_v, alerta_gas, timed", 
                              (id_usuario_actual, raw_gas, volts_gas, alerta, ahora))

            except Exception as e:
                root.after(0, lambda: lbl_estado.config(text=f"Error: {str(e)[:40]}", fg=ACCENT_W))

        # Lanzar peticion en hilo paralelo
        threading.Thread(target=fetch_and_save, daemon=True).start()

        if leyendo_datos: root.after(intervalo_ms, pedir_datos)

    pedir_datos()
    boton_moderno("Detener y Volver", TEXT_HINT, menu_principal, frame)

# --- Modulo CRUD ---
def menu_base_datos():
    global leyendo_datos; leyendo_datos = False; limpiar()
    hdr = tk.Frame(frame, bg=ACCENT_C); hdr.pack(fill="x")
    tk.Label(hdr, text="  GESTION CRUD DE HISTORICOS", font=("Courier New", 14, "bold"), bg=ACCENT_C, fg="white").pack(pady=10)
    
    ops = [
        ("VACIAR DATOS ULTRASONICOS", ACCENT_W, lambda: vaciar_tabla("ultrasonic_data")),
        ("VACIAR DATOS MQ4", ACCENT_W, lambda: vaciar_tabla("mq4_data")),
        ("REINICIAR CONTEOS IA A CERO", "#FF3333", reiniciar_ia)
    ]
    
    for texto, col, cmd in ops: boton_moderno(texto, col, cmd, frame)
    separador(frame, pady=5)
    boton_moderno("Volver al menu", TEXT_HINT, menu_principal, frame)

def vaciar_tabla(tabla):
    if popup_yesno("PELIGRO", f"¿Borrar TODO el historial de {tabla}?", "#FF3333"):
        try:
            conexion = mysql.connector.connect(**config)
            cursor = conexion.cursor()
            cursor.execute(f"DELETE FROM {tabla}")
            conexion.commit()
            popup_ok("Limpio", f"Tabla {tabla} vaciada.")
            cursor.close(); conexion.close()
        except Exception as e: popup_error("Error DB", str(e))

def reiniciar_ia():
    if popup_yesno("PELIGRO", "¿Reiniciar todos los contadores de IA a 0?", "#FF3333"):
        try:
            conexion = mysql.connector.connect(**config)
            cursor = conexion.cursor()
            cursor.execute("UPDATE classification_counts SET total = 0, ultima_vez = NULL")
            conexion.commit()
            popup_ok("Reiniciado", "Conteos de IA en 0.")
            cursor.close(); conexion.close()
        except Exception as e: popup_error("Error DB", str(e))

# Inicio
login_screen()
root.mainloop()
