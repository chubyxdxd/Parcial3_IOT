# -*- coding: utf-8 -*-
import os, sys, time
import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision import transforms
import torchvision.models as models
from PIL import Image
import urllib.request
import mysql.connector
from datetime import datetime
import threading

# 1. CONFIGURACIÓN DEL SISTEMA Y TRADUCCIÓN
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "modelo_resnet18_iot.pth")
CAM_INDEX = 1  # Cambia a 2 si usas una webcam USB

URL_ESP32 = "http://192.168.1.215"

config_db = {
    'host': '192.168.1.212',  
    'user': 'fabricio',
    'password': 'efenomas',
    'database': 'basurero'
}
# Estructura: 'clase_del_modelo': (Bandera_ESP32, 'Columna_BD', (Color_BGR))
DICCIONARIO_TRADUCCION = {
    # Variantes en Español
    'papel y carton': (0, 'paper', (251, 191, 36)),
    'vidrio':         (1, 'vidrio', (56, 189, 248)),
    'plastico':       (2, 'plastics', (239, 68, 68)),
    'organico':      (3, 'biological', (34, 197, 94)),
    
    # Variantes en Inglés (Las que tu modelo .pth está arrojando ahora mismo)
    'paper':          (0, 'paper', (251, 191, 36)),
    'glass':          (1, 'vidrio', (56, 189, 248)),
    'plastics':       (2, 'plastics', (239, 68, 68)),
    'plastic':        (2, 'plastics', (239, 68, 68)),
    'biological':     (3, 'biological', (34, 197, 94))
}

CONF_THRESH = 0.70  
COLOR_BUSCANDO = (200, 200, 200) # Gris claro para estado de espera

# --- VARIABLES GLOBALES PARA LOS HILOS ---
frame_actual = None
estado_ia = {"clase": "Buscando...", "confianza": 0.0, "color": COLOR_BUSCANDO}
sistema_corriendo = True  

# 2. CARGA DEL MODELO RESNET18
def load_model(path):
    if not os.path.exists(path):
        print(f"[ERROR] No se encontró el modelo: {path}")
        sys.exit(1)

    print("Cargando modelo ResNet18 en memoria...")
    state_dict = torch.load(path, map_location='cpu')

    if 'model_state_dict' in state_dict:
        weights = state_dict['model_state_dict']
        classes = state_dict.get('class_names', ['BIOLOGICO', 'PAPEL Y CARTON', 'VIDRIO', 'PLASTICO'])
        img_size = state_dict.get('input_size', 224)
    else:
        weights = state_dict
        classes = ['BIOLOGICO', 'PAPEL Y CARTON', 'VIDRIO', 'PLASTICO']
        img_size = 224 

    device = torch.device('cpu') 
    model = models.resnet18(weights=None)
    
    if "fc.0.weight" in weights:
        in_features = model.fc.in_features
        hidden_dim = weights["fc.0.weight"].shape[0] 
        out_features = weights["fc.3.weight"].shape[0] 
        model.fc = nn.Sequential(
            nn.Linear(in_features, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(p=0.5),
            nn.Linear(hidden_dim, out_features)
        )
    elif any("fc.1.weight" in k for k in weights.keys()):
        model.fc = nn.Sequential(
            nn.Dropout(p=0.5),
            nn.Linear(model.fc.in_features, len(classes))
        )
    else:
        model.fc = nn.Linear(model.fc.in_features, len(classes))

    model.load_state_dict(weights)
    model.to(device).eval()
    return model, classes, device, img_size

def build_transform(img_size):
    return transforms.Compose([
        transforms.Resize((img_size, img_size)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

def preprocess(frame_bgr, tf):
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    return tf(pil).unsqueeze(0)

# 3. HILO SECUNDARIO (PROCESAMIENTO IA E IOT)
def hilo_inferencia(model, classes, device, tf):
    global frame_actual, estado_ia, sistema_corriendo
    
    while sistema_corriendo:
        if frame_actual is None:
            time.sleep(0.1)
            continue

        frame_procesar = frame_actual.copy()
        tensor = preprocess(frame_procesar, tf)
        
        with torch.no_grad():
            logits = model(tensor.to(device))
            probs = torch.softmax(logits, dim=1)[0].numpy()
        
        top_idx = int(np.argmax(probs))
        top_conf = float(probs[top_idx])
        top_name = classes[top_idx]

        # Normalizamos el nombre del modelo
        clase_modelo_limpia = str(top_name).lower().strip()

        print(f"\r[IA PENSANDO] Clase: '{top_name}' -> '{clase_modelo_limpia}' | Confianza: {top_conf*100:.1f}%", end="", flush=True)

        # Validamos el umbral y la existencia en el diccionario
        if top_conf >= CONF_THRESH and clase_modelo_limpia in DICCIONARIO_TRADUCCION:
            bandera, db_class, color_bgr = DICCIONARIO_TRADUCCION[clase_modelo_limpia]

            # 1. Actualizar la interfaz visual
            estado_ia = {
                "clase": clase_modelo_limpia.upper(), 
                "confianza": top_conf, 
                "color": color_bgr
            }
            print(f"\n\n DETECCIÓN CONFIRMADA: {clase_modelo_limpia.upper()} (Confianza: {top_conf*100:.1f}%)")
            
            # 2. Comunicación remota con el ESP32
            try:
                url_comando = f"{URL_ESP32}/?bandera={bandera}"
                respuesta = urllib.request.urlopen(url_comando, timeout=2.0)
                if respuesta.getcode() == 200:
                    print(f"  ➜ ESP32 confirmado (Bandera: {bandera} | HTTP 200 OK)")
            except Exception as e:
                print(f"Fallo de comunicación con ESP32: {e}")

            # 3. Registro en la Base de Datos MySQL
            try:
                conexion = mysql.connector.connect(**config_db)
                cursor = conexion.cursor()
                ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute(
                    "UPDATE classification_counts SET total = total + 1, ultima_vez = %s WHERE clase = %s", 
                    (ahora, db_class)
                )
                
                if cursor.rowcount == 0:
                    cursor.execute(
                        "INSERT INTO classification_counts (clase, total, ultima_vez) VALUES (%s, 1, %s)",
                        (db_class, ahora)
                    )
                
                conexion.commit()
                cursor.close(); conexion.close()
                print(f"  ➜ Base de datos sincronizada columna: '{db_class}'")
            except Exception as e:
                print(f" Error de escritura en MySQL: {e}")

            # Cooldown de estabilización estructural
            print(" Esperando descarga de residuo (5s)...")
            time.sleep(7)
            
            estado_ia = {"clase": "Buscando...", "confianza": 0.0, "color": COLOR_BUSCANDO}
            print("  👀 Escaneando nuevamente...\n")
        
        else:
            # Pausa sutil entre frames si no cumple los requisitos
            time.sleep(0.1)

# 4. HILO PRINCIPAL (CÁMARA Y VIDEO)
def main():
    global frame_actual, sistema_corriendo, estado_ia

    model, classes, device, img_size = load_model(MODEL_PATH)
    tf = build_transform(img_size)

    hilo_ia = threading.Thread(target=hilo_inferencia, args=(model, classes, device, tf))
    hilo_ia.start()

    print("\n Iniciando cámara...")
    cap = cv2.VideoCapture(CAM_INDEX)
    if not cap.isOpened():
        print(f" ERROR: No se pudo abrir la cámara {CAM_INDEX}")
        sistema_corriendo = False
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    win_name = "DeepRecycle - Visión en Tiempo Real"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)

    print("-" * 50)
    print(" DEEPRECYCLE: CAPA DE TRADUCCIÓN INICIADA")
    print("Presiona la tecla 'Q' o 'ESC' para cerrar el sistema.")
    print("-" * 50)

    try:
        while sistema_corriendo:
            ret, frame = cap.read()
            if not ret: continue

            frame_actual = frame 

            # Interfaz gráfica superior (HUD)
            h, w = frame.shape[:2]
            cv2.rectangle(frame, (0, 0), (w, 60), (20, 20, 20), -1)
            
            if estado_ia["clase"] == "Buscando...":
                texto = estado_ia["clase"]
            else:
                texto = f"{estado_ia['clase']} ({estado_ia['confianza']*100:.1f}%)"
            
            cv2.putText(frame, texto, (15, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, estado_ia["color"], 2, cv2.LINE_AA)
            cv2.rectangle(frame, (5, 5), (w - 5, h - 5), estado_ia["color"], 4)

            cv2.imshow(win_name, frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), ord('Q'), 27):
                sistema_corriendo = False
                break

    except KeyboardInterrupt:
        sistema_corriendo = False
    finally:
        cap.release()
        cv2.destroyAllWindows()
        hilo_ia.join()
        print("✓ Ecosistema cerrado de manera limpia.")

if __name__ == '__main__':
    main()
