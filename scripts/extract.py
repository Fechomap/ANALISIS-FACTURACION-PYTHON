import os
import json
import pdfplumber
import pandas as pd
import sys
from decimal import Decimal, ROUND_HALF_UP

def clean_text(text):
    return ' '.join(text.split())

def format_currency(value_str):
    try:
        clean_value = value_str.replace('$', '').replace('MXN', '').strip()
        if '.' in clean_value and ',' in clean_value:
            clean_value = clean_value.replace('.', '').replace(',', '.')
        elif ',' in clean_value:
            clean_value = clean_value.replace(',', '.')
        decimal_value = Decimal(clean_value)
        formatted_value = decimal_value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return float(formatted_value)
    except Exception as e:
        print(f"Error en format_currency: {e} para valor: {value_str}")
        return 0.00

def convert_to_number(value):
    try:
        clean_value = ''.join(c for c in str(value) if c.isdigit() or c == '.')
        return int(float(clean_value))
    except (ValueError, TypeError):
        return value

def parse_date(date_str):
    """
    Convierte una fecha en formato '8 oct 2024' a 'DD/MM/AAAA'
    """
    from datetime import datetime
    
    # Diccionario de meses en español
    meses = {
        'ene': '01', 'feb': '02', 'mar': '03', 'abr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'ago': '08',
        'sept': '09', 'oct': '10', 'nov': '11', 'dic': '12'
    }
    
    try:
        # Limpiar y normalizar el texto
        date_str = date_str.lower().strip()
        print(f"Intentando parsear fecha: {date_str}")
        
        # Separar la fecha en partes
        parts = [part for part in date_str.split() if part]
        print(f"Partes de la fecha: {parts}")
        
        # Validar que tengamos suficientes partes
        if len(parts) < 3:
            print("No hay suficientes partes en la fecha")
            return None
            
        # Intentar encontrar el mes primero
        mes = None
        mes_idx = -1
        for i, part in enumerate(parts):
            if part[:3] in meses:
                mes = meses[part[:3]]
                mes_idx = i
                break
        
        if mes is None:
            print("No se encontró el mes")
            return None
            
        # Una vez encontrado el mes, buscar día y año
        try:
            # El día debería estar antes del mes
            dia = parts[mes_idx - 1] if mes_idx > 0 else parts[0]
            # Limpiar el día de cualquier carácter no numérico
            dia = ''.join(c for c in dia if c.isdigit())
            dia = dia.zfill(2)  # Añadir cero al inicio si es necesario
            
            # El año debería estar después del mes
            año = parts[mes_idx + 1] if mes_idx < len(parts) - 1 else parts[-1]
            # Limpiar el año de cualquier carácter no numérico
            año = ''.join(c for c in año if c.isdigit())
            
            if dia and año and len(año) == 4:
                fecha_formateada = f"{dia}/{mes}/{año}"
                print(f"Fecha parseada exitosamente: {fecha_formateada}")
                return fecha_formateada
        except Exception as e:
            print(f"Error procesando día/año: {e}")
            
    except Exception as e:
        print(f"Error general al parsear fecha '{date_str}': {e}")
    return None

def process_pdf(pdf_path, existing_records):
    data = []  # Para el Excel
    report_data = []  # Para el reporte
    pedido_number = None
    
    # Crear un conjunto de tuplas (expediente, pedido) para verificación rápida
    existing_pieces = {(rec.get("Nº de pieza"), rec.get("Numero de Pedido")) 
                      for rec in existing_records}
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page_text = pdf.pages[0].extract_text()
            for line in first_page_text.split('\n'):
                if "Pedido de compra:" in line:
                    pedido_str = line.split(':')[1].strip()
                    pedido_number = convert_to_number(pedido_str)
                    break
            
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                lines = text.split('\n')
                fecha_requerida = None
                
                # Debug: Imprimir todas las líneas para ver qué estamos procesando
                print("Procesando líneas del PDF:")
                for idx, line in enumerate(lines):
                    print(f"Línea {idx}: {line}")

                # Primero buscamos la fecha
                fecha_requerida = None
                for i, line in enumerate(lines):
                    # Debug: Imprimir la línea que estamos analizando
                    print(f"Analizando línea {i}: {line}")
                    
                    # Buscar específicamente en la columna de fecha
                    if any(keyword in line for keyword in ["Fecha para la que se", "Cant.", "(Unidad)", "requiere"]):
                        print(f"Encontrada línea con palabras clave: {line}")
                        
                        # Analizar esta línea y las siguientes
                        for j in range(i, min(i + 3, len(lines))):
                            current_line = lines[j]
                            words = current_line.split()
                            
                            # Debug: Mostrar las palabras que estamos analizando
                            print(f"Analizando palabras en línea {j}: {words}")
                            
                            for k, word in enumerate(words):
                                word_lower = word.lower()
                                if word_lower in ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sept', 'oct', 'nov', 'dic']:
                                    print(f"Encontrado mes: {word}")
                                    # Buscar el día y año alrededor del mes
                                    start_idx = max(0, k - 1)
                                    end_idx = min(len(words), k + 2)
                                    potential_date = ' '.join(words[start_idx:end_idx])
                                    print(f"Intentando parsear fecha: {potential_date}")
                                    parsed_date = parse_date(potential_date)
                                    if parsed_date:
                                        fecha_requerida = parsed_date
                                        print(f"¡Fecha encontrada y parseada!: {fecha_requerida}")
                                        break
                            if fecha_requerida:
                                break
                        if fecha_requerida:
                            break
                
                # Luego procesamos las líneas de Material
                for i, line in enumerate(lines):  # CORRECCIÓN: Este bucle debe estar dentro del bucle de páginas
                    if "Material" in line:
                        try:
                            parts = line.split()
                            precio_str = next((p for p in parts if '$' in p), "$0")
                            impuesto_str = next((p for p in reversed(parts) if '$' in p), "$0")
                            
                            # Crear el registro
                            num_pieza = convert_to_number(parts[2])
                            
                            data_entry = {
                                "Numero de Pedido": pedido_number,
                                "Numero de linea": convert_to_number(parts[0]),
                                "Numero de repartos": convert_to_number(parts[1]),
                                "Nº de pieza": num_pieza,
                                "pieza de cliente": convert_to_number(parts[3]),
                                "Tipo": "Material",
                                "Devolución": 1,
                                "Fecha": fecha_requerida if fecha_requerida else "Sin fecha",
                                "Descripcion": "Arrastre/M (SER)",
                                "Cantidad": "(SER)",
                                "Precio por unidad": '{:.2f}'.format(format_currency(precio_str)),
                                "Subtotal": '{:.2f}'.format(format_currency(precio_str)),
                                "Impuesto": '{:.2f}'.format(format_currency(impuesto_str))
                            }
                            
                            # Siempre agregar al reporte
                            report_data.append(data_entry)
                            
                            # Solo agregar al Excel si no es duplicado
                            if (num_pieza, pedido_number) not in existing_pieces:
                                data.append(data_entry)
                                existing_pieces.add((num_pieza, pedido_number))
                            else:
                                print(f"Saltando registro duplicado - Pieza: {num_pieza}, Pedido: {pedido_number}")
                        except Exception as e:
                            print(f"Error procesando línea: {line} en {pdf_path}. Error: {str(e)}")
                            continue
        
        return data, report_data
    except Exception as e:
        print(f"Error al abrir o procesar el archivo {pdf_path}: {e}")
        return [], []

def collect_duplicates(all_data, duplicate_items):
    duplicate_analysis = {}
    pieza_ocurrencias = {}
    
    for registro in all_data:
        pieza = registro.get('Nº de pieza')
        if pieza:
            if pieza not in pieza_ocurrencias:
                pieza_ocurrencias[pieza] = []
            # Convertir precio a float si es string
            precio = registro.get('Precio por unidad')
            if isinstance(precio, str):
                try:
                    precio = float(precio.replace(',', ''))
                except (ValueError, TypeError):
                    precio = 0.0
            
            pieza_ocurrencias[pieza].append({
                'pedido': registro.get('Numero de Pedido'),
                'precio': precio,  # Ahora siempre será float
                'descripcion': registro.get('Descripcion')
            })
    
    # Procesar solo las piezas que tienen más de una ocurrencia
    for pieza, ocurrencias in pieza_ocurrencias.items():
        if len(ocurrencias) > 1:  # Si hay más de una ocurrencia
            descripcion = ocurrencias[0]['descripcion']
            duplicate_analysis[pieza] = {
                'expediente': pieza,
                'descripcion': descripcion,
                'ocurrencias': ocurrencias,
                'pedidos_set': set(o['pedido'] for o in ocurrencias)
            }
            print(f"DEBUG - Expediente {pieza} encontrado en pedidos: {set(o['pedido'] for o in ocurrencias)}")
    
    return duplicate_analysis

def generate_duplicate_report(duplicate_analysis):
    """
    Genera el reporte de duplicados con el nuevo formato
    """
    report_lines = []
    report_lines.append("=== ANÁLISIS DE DUPLICADOS ===")
    
    for expediente, info in duplicate_analysis.items():
        report_lines.append(f"\nExpediente duplicado: {expediente}")
        report_lines.append(f"Descripción: {info['descripcion']}")
        
        # Determinar tipo de duplicado
        num_pedidos = len(info['pedidos_set'])
        if num_pedidos == 1:
            pedido_unico = next(iter(info['pedidos_set']))
            report_lines.append(f"TIPO DE DUPLICADO: Mismo pedido ({pedido_unico})")
            report_lines.append(f"Número de ocurrencias: {len(info['ocurrencias'])}")
        else:
            report_lines.append(f"TIPO DE DUPLICADO: Diferentes pedidos ({num_pedidos} pedidos distintos)")
            report_lines.append("Pedidos involucrados:")
            for pedido in sorted(info['pedidos_set']):
                report_lines.append(f"   - Pedido: {pedido}")
        
        # Detalles de cada ocurrencia
        report_lines.append("\nDetalles de ocurrencias:")
        # Convertir valores antes de ordenar
        ocurrencias_normalizadas = []
        for ocurrencia in info['ocurrencias']:
            precio = ocurrencia['precio']
            if isinstance(precio, str):
                try:
                    precio = float(precio.replace('$', '').replace(',', ''))
                except (ValueError, TypeError):
                    precio = 0.0
                    
            pedido = ocurrencia['pedido']
            if isinstance(pedido, str):
                try:
                    pedido = float(pedido)
                except (ValueError, TypeError):
                    pedido = 0.0
                    
            ocurrencias_normalizadas.append({
                'pedido': pedido,
                'precio': precio,
                'pedido_original': ocurrencia['pedido'],
                'precio_original': ocurrencia['precio']
            })
        
        ocurrencias_ordenadas = sorted(ocurrencias_normalizadas, key=lambda x: (x['pedido'], x['precio']))
        for ocurrencia in ocurrencias_ordenadas:
            report_lines.append(f"   - Pedido: {ocurrencia['pedido_original']}")
            report_lines.append(f"     Precio: ${ocurrencia['precio_original']}")
        
        # Verificar diferencias en precios
        precios = {o['precio'] for o in ocurrencias_normalizadas}
        if len(precios) > 1:
            report_lines.append("\n   ¡ALERTA! Diferentes precios encontrados:")
            for precio in sorted(precios):
                report_lines.append(f"     - ${precio}")
    
    return "\n".join(report_lines)

def extract_data(input_folder, output_json, output_excel, report_txt):
    import time  # Agregar al inicio de la función
    # Extraer directorio base desde el archivo Excel para asegurar consistencia
    output_dir = os.path.dirname(output_excel)
    os.makedirs(output_dir, exist_ok=True)  # Asegurarse de que la carpeta de salida exista

    # Ajustar las rutas de salida para que siempre estén dentro de la carpeta `output`
    output_json_path = os.path.join(output_dir, os.path.basename(output_json))
    output_excel_path = output_excel
    report_file_path = report_txt

    all_data = []  # Para el Excel
    all_report_data = []  # Para el reporte
    invalid_pdfs = []

    # Cargar datos existentes
    if os.path.exists(output_excel_path):
        try:
            df_existing = pd.read_excel(output_excel_path)
            df_existing['Precio por unidad'] = pd.to_numeric(df_existing['Precio por unidad'], errors='coerce')
            all_data.extend(df_existing.to_dict(orient='records'))
            all_report_data.extend(df_existing.to_dict(orient='records'))
        except Exception as e:
            print(f"Error al leer {output_excel_path}: {e}")

    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith('.pdf')]
    
    for pdf_filename in pdf_files:
        pdf_path = os.path.join(input_folder, pdf_filename)
        print(f"Procesando {pdf_path}...")
        excel_data, report_data = process_pdf(pdf_path, all_data)
        if not excel_data and not report_data:
            invalid_pdfs.append(pdf_filename)
            continue
        
        all_data.extend(excel_data)  # Solo datos no duplicados para Excel
        all_report_data.extend(report_data)  # Todos los datos para el reporte
        time.sleep(0.5)

    # Crear lista de items duplicados para el reporte (incluye todos los duplicados)
    duplicate_items = []
    for registro in all_report_data:
        pieza = registro.get('Nº de pieza')
        pedido = registro.get('Numero de Pedido')
        if pieza:
            found = False
            for item in duplicate_items:
                if item['pieza'] == pieza:
                    found = True
                    item['ocurrencias'].append({
                        'pedido': pedido,
                        'precio': registro.get('Precio por unidad'),
                        'descripcion': registro.get('Descripcion')
                    })
                    break
            if not found:
                duplicate_items.append({
                    'pieza': pieza,
                    'ocurrencias': [{
                        'pedido': pedido,
                        'precio': registro.get('Precio por unidad'),
                        'descripcion': registro.get('Descripcion')
                    }]
                })

    # Filtrar items que realmente son duplicados
    duplicate_items = [item for item in duplicate_items 
                    if len(item['ocurrencias']) > 1]

    # Aplicar la conversión antes de guardar
    all_data_safe = convert_datetime_to_str(all_data)

    # 1. PRIMERO guardar JSON (asegurando que no hay objetos datetime)
    with open(output_json_path, 'w', encoding='utf-8') as json_file:
        json.dump(all_data_safe, json_file, ensure_ascii=False, indent=4)

    # 2. DESPUÉS crear el DataFrame y procesar datos numéricos
    df = pd.DataFrame(all_data)
    numeric_columns = ['Precio por unidad', 'Subtotal', 'Impuesto']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    if "Numero de Pedido" in df.columns:
        df["Numero de Pedido"] = pd.to_numeric(df["Numero de Pedido"], errors='coerce')

    # 3. Convertir columna 'Fecha' a datetime para que Excel la reconozca correctamente
    if 'Fecha' in df.columns:
        # Crear una máscara para identificar fechas válidas en formato DD/MM/YYYY
        fecha_valida = df['Fecha'].apply(lambda x: isinstance(x, str) and x != "Sin fecha" and "/" in x)
        
        # Convertir solo las fechas válidas a formato datetime
        df.loc[fecha_valida, 'Fecha'] = pd.to_datetime(df.loc[fecha_valida, 'Fecha'], format="%d/%m/%Y", errors='coerce')

    # 4. Guardar el Excel con las fechas ya convertidas
    df.to_excel(output_excel_path, index=False)

    # Análisis de duplicados para el reporte
    duplicate_analysis = {
        item['pieza']: {
            'expediente': item['pieza'],
            'descripcion': item['ocurrencias'][0]['descripcion'],
            'ocurrencias': item['ocurrencias'],
            'pedidos_set': set(o['pedido'] for o in item['ocurrencias'])
        }
        for item in duplicate_items
    }

    # Crear el reporte de texto mejorado
    reporte_texto = []
    reporte_texto.append("=== REPORTE DE EXTRACCIÓN DE PDF ===\n")
    reporte_texto.append(f"Total de PDFs encontrados: {len(pdf_files)}")
    reporte_texto.append(f"PDFs procesados con éxito: {len(pdf_files) - len(invalid_pdfs)}")
    reporte_texto.append(f"PDFs inválidos: {len(invalid_pdfs)}")
    if invalid_pdfs:
        reporte_texto.append("\nArchivos inválidos:")
        reporte_texto.append("   " + ", ".join(invalid_pdfs))
    
    reporte_texto.append(f"\nRegistros duplicados encontrados: {len(duplicate_items)}")
    reporte_texto.append(f"Registros extraídos totales: {len(all_data)}\n")
    
    # Agregar el análisis de duplicados al reporte
    if duplicate_items:
        reporte_texto.append(generate_duplicate_report(duplicate_analysis))
    else:
        reporte_texto.append("\nNo se encontraron registros duplicados.")

    # El resto del código sigue igual
    reporte_texto = "\n".join(reporte_texto)
    
    with open(report_file_path, 'w', encoding='utf-8') as rep_file:
        rep_file.write(reporte_texto)

    print(f"Extracción completada. Se encontraron {len(all_data)} registros en total.")
    print(f"Reporte guardado en: {report_file_path}")

def convert_datetime_to_str(data):
    """
    Convierte cualquier objeto datetime a string en formato DD/MM/YYYY
    para asegurar la serialización correcta en JSON
    """
    import datetime as dt
    import pandas as pd
    
    # Crea una copia de los datos para no modificar el original
    processed_data = []
    
    for record in data:
        # Crear una copia del registro para no modificar el original
        new_record = {}
        for key, value in record.items():
            # Detectar si es un objeto datetime (pandas Timestamp o datetime de Python)
            if isinstance(value, (dt.datetime, pd.Timestamp)):
                # Convertir a string en formato DD/MM/YYYY
                new_record[key] = value.strftime('%d/%m/%Y')
            else:
                # Mantener el valor original
                new_record[key] = value
        processed_data.append(new_record)
        
    return processed_data

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("""
=== Procesador de Pedidos de Compra ===

Uso: python scripts/extract.py PDF-PEDIDOS output/data.xlsx output/log.txt

Estructura de carpetas:
    PDF-PEDIDOS/      → Carpeta con los pedidos a procesar
    output/           → Carpeta donde se guardan los resultados
        data.xlsx     → Excel con los datos
        log.txt       → Archivo de log del proceso

Ejemplo:
    python scripts/extract.py PDF-PEDIDOS output/data.xlsx output/log.txt
        """)
        sys.exit(1)

    input_folder = sys.argv[1]
    output_excel = sys.argv[2]
    report_txt = sys.argv[3]

    print("\n=== Iniciando Procesamiento de Pedidos ===")
    print(f"Carpeta de pedidos: {input_folder}")
    print(f"Archivo Excel: {output_excel}")
    print(f"Archivo de log: {report_txt}")

    # Se crea un JSON temporal para almacenar datos acumulados
    output_dir = os.path.dirname(output_excel)
    output_json = os.path.join(output_dir, "output_temp.json")

    extract_data(input_folder, output_json, output_excel, report_txt)