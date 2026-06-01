# DeepRecycle: Sistema Inteligente de Gestión de Residuos

DeepRecycle es una solución integral de IoT y Visión Computacional diseñada para la clasificación automatizada y el monitoreo en tiempo real de contenedores de basura. El sistema utiliza inteligencia artificial para identificar el tipo de residuo, microcontroladores para el accionamiento electromecánico de la clasificación y una arquitectura de software distribuida para la telemetría y visualización de datos.

---

## Estructura del Proyecto

Para entender cómo fluye la información en DeepRecycle, la arquitectura se divide en tres capas lógicas principales:

### Frontend (Capa de Presentación)
El frontend es la parte del software con la que interactúan los usuarios finales. Su objetivo es solicitar información al sistema y mostrarla de forma visual e intuitiva.
* **Centro de Control de Escritorio (`cliente.py`):** Construido con **Tkinter**, permite a los operadores locales iniciar sesión, solicitar muestreos manuales de los sensores y administrar la limpieza del sistema.
* **Dashboard Analítico Web (`raspy.py`):** Desarrollado con **Streamlit**, es un frontend diseñado para la visualización de datos de alto nivel. Transforma los números crudos en gráficos interactivos (Plotly) e indicadores visuales (como los contenedores llenándose en tiempo real).

### Backend (Capa de Lógica y Procesamiento)
El motor del sistema que corre en segundo plano. Se encarga de hacer los cálculos pesados, procesar reglas de negocio y comunicarse con el hardware.
* **Procesamiento de Inteligencia Artificial (`servidor.py`):** Actúa como un backend de visión. Utiliza **PyTorch** y **OpenCV** para ingerir video, ejecutar el modelo ResNet18, decidir qué tipo de basura es y orquestar las acciones físicas.
* **Procesamiento Edge (ESP32):** Actúa como un micro-servidor backend en el borde (IoT) programado en **MicroPython**. Expone rutas web (HTTP) para recibir comandos de movimiento de los servomotores y devuelve archivos JSON con las lecturas de los sensores ultrasónicos y el sensor de gas MQ4.

### Base de Datos (Capa de Persistencia)
El puente que conecta el Backend con el Frontend.
* **MySQL:** Utilizamos un motor relacional MySQL como única fuente de verdad. El backend escribe constantemente los datos aquí (conteos de IA, niveles de llenado, alertas de metano), mientras que el frontend lee esta base de datos para mostrar los historiales a los usuarios.

---

## Nodos del Sistema

El ecosistema está compuesto por cuatro nodos principales que interactúan entre sí a través de peticiones HTTP a través de la red local:

1. **Nodo de Visión IA (`servidor.py`):** Procesa frames de una cámara, clasifica el residuo (Papel/Cartón, Vidrio, Plástico o Biológico) y envía peticiones HTTP al ESP32 para accionar el hardware.
2. **Centro de Control (`cliente.py`):** UI de escritorio. Se comunica con el ESP32 para solicitar telemetría mediante multihilos (`threading`) y guarda registros históricos.
3. **Dashboard Analítico (`raspy.py`):** Aplicación web que visualiza niveles de llenado, evolución del gas metano y métricas de clasificación de la IA.
4. **Nodo IoT / Hardware (ESP32):** Recibe instrucciones de movimiento, lee sensores ultrasónicos (HC-SR04) para medir volumen y muestrea el sensor MQ4 por motivos de seguridad.

---

## Tecnologías Utilizadas

| Categoría | Tecnologías |
| :--- | :--- |
| **Inteligencia Artificial** | PyTorch, Torchvision, OpenCV, ResNet18 |
| **Backend & IoT** | Python 3, MicroPython, HTTP Requests |
| **Frontend & UI** | Tkinter, Streamlit, Plotly, HTML/CSS embebido |
| **Base de Datos** | MySQL |
| **Hardware** | ESP32, Servomotores, Sensores Ultrasónicos, Sensor Gas MQ4 |

---

## Esquema de Base de Datos (`basurero`)

Para el correcto funcionamiento, el servidor MySQL debe contar con la base de datos `basurero` y las siguientes tablas:

* `usuarios`: Credenciales de operadores (`id`, `password`, `nombre_usuario`).
* `ultrasonic_data`: Histórico de llenado (`idu`, `dist_bio`, `nivel_bio`, `dist_paper`, etc., `timed`).
* `mq4_data`: Lecturas de gas y alertas (`idu`, `valor_raw`, `voltaje_v`, `alerta_gas`, `timed`).
* `classification_counts`: Frecuencia de clasificación de la IA (`clase`, `total`, `ultima_vez`).

---

## Guía de Instalación y Ejecución

### 1. Configuración de la Base de Datos
1. Despliega un servidor MySQL en tu red local.
2. Crea la base de datos `basurero` y las tablas mencionadas.
3. En los archivos `cliente.py`, `servidor.py` y `raspy.py`, busca el diccionario de configuración de base de datos (`config` o `conectar_db()`) y actualiza los parámetros con tus credenciales:
   * `host`: `<IP_DE_TU_SERVIDOR_MYSQL>`
   * `user`: `<TU_USUARIO>`
   * `password`: `<TU_CONTRASEÑA>`

### 2. Despliegue del Nodo IoT (ESP32)
1. Carga tu script de control (MicroPython) en el ESP32.
2. Conecta el ESP32 a la misma red WiFi que las computadoras que correrán el software.
3. Obtén la dirección IP asignada al ESP32.
4. En los archivos `cliente.py` y `servidor.py`, actualiza la constante `URL_ESP32` con la IP correcta:
   ```python
   URL_ESP32 = "http://<IP_DE_TU_ESP32>"
   
### 3. Dependencias del Software

El ecosistema principal está desarrollado en **Python 3**. Asegúrate de tenerlo instalado en tu sistema antes de continuar.

Para instalar todas las librerías necesarias de una sola vez, abre tu terminal o símbolo del sistema y ejecuta el siguiente comando:

```bash
pip install torch torchvision opencv-python numpy pillow mysql-connector-python streamlit pandas plotly
