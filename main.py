import flet as ft
import threading
import pandas as pd
import random
import time
import os
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------------------------------------------
# Configuración del logger (para debug/errores)
# ---------------------------------------------
logging.basicConfig(
    filename='scraping.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ---------------------------------------------
# Lista de User-Agents para rotar
# ---------------------------------------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.2 Mobile/15E148 Safari/604.1"
]

# Variable global para controlar el ciclo de scraping
DETENER_SCRAPING = False

def main(page: ft.Page):
    """
    Función principal que construye la interfaz en Flet.
    """
    global DETENER_SCRAPING  # Declarar como global para modificarla dentro de funciones internas

    page.title = "Web Scraping Nike Chile"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.theme_mode = ft.ThemeMode.LIGHT  # Puedes cambiarlo a DARK o SYSTEM
    page.window_width = 900
    page.window_height = 700
    page.padding = 20

    # ---------------------------------------------------------------------
    # Contenedores / variables para manejar el estado en la interfaz de Flet
    # ---------------------------------------------------------------------
    text_codigos = ft.TextField(
        label="Códigos de producto (uno por línea o separados por espacio)",
        multiline=True,
        expand=True
    )

    progreso_bar = ft.ProgressBar(value=0, width=400)
    texto_estado = ft.Text("En espera...", size=12, color=ft.colors.BLUE_GREY)

    # Lista (DataTable) para mostrar resultados
    # -----------------------------------------
    # Encabezados de la tabla
    columns = [
        ft.DataColumn(ft.Text("Código")),
        ft.DataColumn(ft.Text("Nombre")),
        ft.DataColumn(ft.Text("Precio")),
        ft.DataColumn(ft.Text("Descuento")),
        ft.DataColumn(ft.Text("URL")),
    ]
    # Filas de la tabla (inicialmente vacías)
    rows = []

    # Estructura para almacenar resultados en memoria
    resultados_list = []

    # ---------------------------------------------------------------------
    # Funciones de la App
    # ---------------------------------------------------------------------
    def leer_archivo_result(e: ft.FilePickerResultEvent):
        """
        Lee el archivo seleccionado con FilePicker y lo muestra en `text_codigos`.
        """
        if not e.files:
            return
        file_path = e.files[0].path
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                contenido = f.read().strip()
                # Reemplaza saltos de línea por espacios para unificar
                text_codigos.value = contenido.replace("\n", " ")
                page.update()
        except Exception as err:
            logging.error(f"Error al leer archivo: {err}")
            texto_estado.value = f"Error al leer archivo: {err}"
            page.update()

    file_picker = ft.FilePicker(on_result=leer_archivo_result)
    page.overlay.append(file_picker)

    def armar_url(base_url: str, codigo: str) -> str:
        return f"{base_url.rstrip('/')}/{codigo}"

    def detener_scraping_func(e):
        """
        Fuerza la detención del proceso de scraping.
        """
        global DETENER_SCRAPING
        DETENER_SCRAPING = True
        texto_estado.value = "Se detendrá el scraping..."
        page.update()

    def guardar_excel(e):
        """
        Guarda los resultados en un archivo Excel con nombre automático:
        'Web Scraping Nike Chile + fecha y hora actual.xlsx'
        """
        if not resultados_list:
            texto_estado.value = "No hay datos para guardar."
            page.update()
            return
        
        # Genera nombre de archivo automáticamente
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"Web Scraping Nike Chile {timestamp}.xlsx"

        df = pd.DataFrame(resultados_list)
        try:
            df.to_excel(filename, index=False)
            texto_estado.value = f"Archivo guardado: {filename}"
            page.update()
        except Exception as err:
            texto_estado.value = f"Error al guardar Excel: {err}"
            logging.error(f"Error al guardar Excel: {err}")
            page.update()

    def procesar_scraping(codigos: list):
        """
        Lógica de scraping usando Selenium.
        """
        global DETENER_SCRAPING
        DETENER_SCRAPING = False  # Resetear la bandera al iniciar

        # Prepara Selenium con Chrome
        options = webdriver.ChromeOptions()
        # Desactiva logs molestos (opcional)
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        # Rota user agent
        options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
        # Puedes habilitar headless si quieres que no abra la ventana
        # options.add_argument("--headless")

        try:
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options
            )
        except Exception as err:
            logging.error(f"Error al iniciar el driver de Chrome: {err}")
            texto_estado.value = f"Error al iniciar el driver de Chrome: {err}"
            page.update()
            return

        base_url = "https://www.nike.cl/"
        total = len(codigos)

        for index, codigo in enumerate(codigos):
            if DETENER_SCRAPING:
                break  # Sale si se presionó 'Detener'
            
            # Actualiza la barra de progreso y mensaje
            progreso = (index + 1) / total
            codigo_actual = codigo
            actual = index + 1

            # Actualiza la barra de progreso y el texto de estado
            progreso_bar.value = progreso
            texto_estado.value = f"Procesando {codigo} ({actual}/{total})"
            page.update()

            url_final = armar_url(base_url, codigo)
            try:
                driver.get(url_final)

                # Espera explícita hasta que el elemento del nombre del producto esté presente
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "span.vtex-product-summary-2-x-productBrand"))
                )

                # Extrae datos. Ajusta los selectores según la web real.
                # Nombre:
                try:
                    nombre_elem = driver.find_element(
                        By.CSS_SELECTOR, "span.vtex-product-summary-2-x-productBrand"
                    )
                    nombre_producto = nombre_elem.text.strip()
                except:
                    nombre_producto = "No encontrado"

                # Precio:
                try:
                    precio_elem = driver.find_element(
                        By.CSS_SELECTOR, "span.vtex-product-price-1-x-currencyContainer"
                    )
                    precio_completo = precio_elem.text.strip()
                except:
                    precio_completo = "No disponible"

                # Descuento:
                try:
                    desc_elem = driver.find_element(
                        By.CSS_SELECTOR, "span.vtex-product-price-1-x-savingsPercentage"
                    )
                    descuento = desc_elem.text.strip()
                except:
                    descuento = "No aplica"

                # Almacena resultado
                resultado = {
                    "Código": codigo,
                    "Nombre del Producto": nombre_producto,
                    "Precio": precio_completo,
                    "Descuento": descuento,
                    "URL": url_final
                }
                resultados_list.append(resultado)

                # Agregar fila a la tabla en la interfaz
                new_row = ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(resultado["Código"])),
                        ft.DataCell(ft.Text(resultado["Nombre del Producto"])),
                        ft.DataCell(ft.Text(resultado["Precio"])),
                        ft.DataCell(ft.Text(resultado["Descuento"])),
                        ft.DataCell(ft.Text(resultado["URL"])),
                    ]
                )
                rows.append(new_row)
                data_table.rows = rows
                page.update()
            
            except Exception as e:
                logging.error(f"Error con {codigo}: {e}")
                resultado = {
                    "Código": codigo,
                    "Nombre del Producto": "Error de carga",
                    "Precio": "No disponible",
                    "Descuento": "No disponible",
                    "URL": url_final
                }
                resultados_list.append(resultado)

                # Agregar fila de error a la tabla
                new_row = ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(resultado["Código"])),
                        ft.DataCell(ft.Text(resultado["Nombre del Producto"])),
                        ft.DataCell(ft.Text(resultado["Precio"])),
                        ft.DataCell(ft.Text(resultado["Descuento"])),
                        ft.DataCell(ft.Text(resultado["URL"])),
                    ]
                )
                rows.append(new_row)
                data_table.rows = rows
                page.update()

        driver.quit()
        # Indica que terminó
        texto_estado.value = "Proceso finalizado."
        page.update()

    def iniciar_scraping(e):
        """
        Inicia el scraping en un hilo separado para no bloquear la interfaz.
        """
        global DETENER_SCRAPING
        DETENER_SCRAPING = False

        # Limpia tabla y resultados previos
        resultados_list.clear()
        rows.clear()
        data_table.rows = rows
        progreso_bar.value = 0
        texto_estado.value = "Iniciando scraping..."
        page.update()

        # Toma los códigos ingresados
        contenido = text_codigos.value.strip()
        # Aceptamos tanto saltos de línea como espacios
        codigos = contenido.replace("\n", " ").split()

        if not codigos:
            texto_estado.value = "Debes ingresar al menos un código."
            page.update()
            return

        # Lanza hilo para scraping
        hilo = threading.Thread(target=procesar_scraping, args=(codigos,), daemon=True)
        hilo.start()

    # ---------------------------------------------------------------------
    # Elementos de la página (Layout)
    # ---------------------------------------------------------------------
    # Botón para seleccionar archivo
    boton_filepicker = ft.ElevatedButton(
        text="Cargar archivo con códigos",
        icon=ft.icons.FOLDER_OPEN,
        on_click=lambda _: file_picker.pick_files(
            allow_multiple=False,
            file_type=ft.FilePickerFileType.ANY
        )
    )

    # Botón para iniciar
    boton_iniciar = ft.ElevatedButton(
        text="Iniciar",
        icon=ft.icons.PLAY_ARROW,
        bgcolor=ft.colors.GREEN,
        color=ft.colors.WHITE,
        on_click=iniciar_scraping
    )

    # Botón para detener
    boton_detener = ft.ElevatedButton(
        text="Detener",
        icon=ft.icons.STOP,
        bgcolor=ft.colors.RED,
        color=ft.colors.WHITE,
        on_click=detener_scraping_func
    )

    # Botón para guardar
    boton_guardar = ft.ElevatedButton(
        text="Guardar Excel",
        icon=ft.icons.SAVE,
        bgcolor=ft.colors.BLUE,
        color=ft.colors.WHITE,
        on_click=guardar_excel
    )

    # DataTable para mostrar resultados
    data_table = ft.DataTable(
        columns=columns,
        rows=rows,
        column_spacing=10,
        horizontal_lines=ft.border.BorderSide(1, ft.colors.BLACK12),
        vertical_lines=ft.border.BorderSide(1, ft.colors.BLACK12),
        divider_thickness=1,
        expand=True  # Para que la tabla ocupe el espacio disponible
    )

    # Agregamos todo al layout principal
    page.add(
        ft.Text("Web Scraping Nike Chile", 
                style=ft.TextThemeStyle.HEADLINE_SMALL, 
                weight=ft.FontWeight.BOLD),
        ft.Row(
            [
                boton_filepicker,
                boton_iniciar,
                boton_detener,
                boton_guardar,
            ],
            alignment=ft.MainAxisAlignment.START,
            spacing=10
        ),
        text_codigos,
        ft.Row([progreso_bar, texto_estado], alignment=ft.MainAxisAlignment.START),
        data_table
    )

# -------------------------------------------------------------------------
# Ejecución de la App
# -------------------------------------------------------------------------
if __name__ == "__main__":
    # Ejecuta como aplicación de escritorio
    ft.app(target=main)
