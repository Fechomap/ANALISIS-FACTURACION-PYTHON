import pdfplumber
import os
import re
import argparse
import pandas as pd
import time

def clean_text(text):
    """Limpia el texto eliminando espacios extras y caracteres especiales"""
    # Eliminar caracteres especiales pero mantener números
    text = re.sub(r'[^0-9a-zA-Z\s]', ' ', text)
    # Eliminar espacios múltiples
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def is_valid_context(line, number, context_keywords):
    """
    Verifica si un número aparece en un contexto válido, considerando
    las palabras clave antes y después del número
    """
    # Limpiar y normalizar el texto
    line = clean_text(line.upper())
    
    # Buscar el número en la línea y obtener su posición
    number_pos = line.find(number)
    if number_pos == -1:
        return False
        
    # Examinar el contexto antes y después del número
    context_before = line[:number_pos].strip()
    context_after = line[number_pos + len(number):].strip()
    
    # Verificar si alguna palabra clave está presente en el contexto
    for keyword in context_keywords:
        # Buscar en el contexto cercano (antes y después)
        if (keyword in context_before[-30:] or  # Últimos 30 caracteres antes
            keyword in context_after[:30]):     # Primeros 30 caracteres después
            return True
            
    return False

def extract_order_from_invoice(pdf_folder, log_file):
    orders_detected = []
    expedientes_detected = []
    invoice_info = {}  # Diccionario para almacenar información de factura por pedido/expediente
    invalid_pdfs = []
    total_processed = 0
    pdf_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith('.pdf')]
    
    # Palabras clave expandidas para contexto
    pedido_keywords = [
        "PEDIDO", "ORDEN", "COMPRA", "SERVICIO", "REFERENCIA",
        "PED", "OC", "O C", "NUM", "NUMERO", "NO", "Nº",
        "REALIZADO", "SERVICIO REALIZADO", "MUERTO", "ARRASTRE",
        "GRUA", "FACTURA", "REMISION"
    ]
    
    expediente_keywords = [
        "EXPEDIENTE", "ARRASTRE", "GRUA", "EXP", "EXPTE",
        "SINIESTRO", "SERVICIO", "NUM", "NUMERO", "NO", "Nº"
    ]

    with open(log_file, 'w', encoding='utf-8') as log:
        log.write("=== REPORTE DE PROCESAMIENTO DE FACTURAS ===\n\n")
        log.write("1. ARCHIVOS SIN REFERENCIAS ENCONTRADAS\n")
        log.write("==========================================\n")
        
        for pdf_file in pdf_files:
            pdf_path = os.path.join(pdf_folder, pdf_file)
            try:
                print(f"Procesando factura: {pdf_file}")
                
                with pdfplumber.open(pdf_path) as pdf:
                    full_text = ""
                    current_orders = []
                    current_expedientes = []
                    has_description_section = False
                    invoice_number = None
                    emission_date = None
                    
                    # Buscar SERIE, FOLIO y FECHA DE EMISIÓN al inicio del documento
                    first_page_text = pdf.pages[0].extract_text()
                    
                    # Buscar fecha de emisión
                    emission_date_match = re.search(r'Fecha emisión\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})', first_page_text)
                    if emission_date_match:
                        # Extraer solo la parte de la fecha (sin hora) para mejor compatibilidad con Excel
                        fecha_parte = emission_date_match.group(1)
                        hora_parte = emission_date_match.group(2)
                        # Convertir de YYYY-MM-DD a DD/MM/YYYY (formato más compatible con Excel)
                        partes_fecha = fecha_parte.split('-')
                        if len(partes_fecha) == 3:
                            fecha_formateada = f"{partes_fecha[2]}/{partes_fecha[1]}/{partes_fecha[0]}"
                            emission_date = fecha_formateada
                        else:
                            emission_date = fecha_parte
                        print(f"Fecha de emisión detectada: {emission_date} (original: {fecha_parte} {hora_parte})")
                    
                    # Buscar el folio de la factura directamente
                    folio_match = re.search(r'Folio\s+A(\d+)', first_page_text)
                    if folio_match:
                        invoice_number = f"A{folio_match.group(1)}"
                        print(f"Número de factura detectado: {invoice_number}")
                    
                    # Variable para indicar si encontramos al menos un pedido/expediente
                    references_found = False
                    
                    # Primero, buscar todos los números de 10 dígitos en todo el texto del documento
                    # y su posible asociación con "PEDIDO DE COMPRA"
                    all_text = ""
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            all_text += page_text + "\n"
                    
                    # Buscar específicamente números de 10 dígitos que comiencen con "51009" o "51008"
                    # ya que todos los pedidos observados tienen ese patrón
                    pedido_numbers = re.findall(r'\b(51009\d{5}|51008\d{5})\b', all_text)
                    
                    if pedido_numbers:
                        for pedido in pedido_numbers:
                            if pedido not in current_orders:
                                current_orders.append(pedido)
                                references_found = True
                                print(f"Número de pedido detectado en documento: {pedido}")
                    
                    # Buscar específicamente la sección donde están los pedidos
                    for page in pdf.pages:
                        text = page.extract_text()
                        if not text:
                            continue
                            
                        full_text += text + "\n"
                        
                        # Imprimir un fragmento del texto para depuración
                        print(f"Fragmento de texto: {text[:200]}...")
                        
                        # Buscar la línea completa donde aparece "ARRASTRE DE GRUA PEDIDO DE COMPRA"
                        lines = text.split('\n')
                        for line in lines:
                            if 'ARRASTRE DE GRUA PEDIDO DE COMPRA' in line.upper():
                                print(f"Línea con Arrastre de grúa: {line.strip()}")
                                
                                # Verificar si hay un número de pedido en la misma línea
                                # que coincida con los patrones de pedido
                                for pedido in pedido_numbers:
                                    if pedido in line:
                                        if pedido not in current_orders:
                                            current_orders.append(pedido)
                                            references_found = True
                                            print(f"Número de pedido encontrado en línea con PEDIDO DE COMPRA: {pedido}")
                            
                            # Buscar expedientes (8 dígitos) - ignorando el código 78101803
                            expedientes = re.finditer(r'\b\d{8}\b', line)
                            for match in expedientes:
                                expediente = match.group()
                                if expediente != "78101803" and expediente not in current_expedientes and is_valid_context(line, expediente, expediente_keywords):
                                    current_expedientes.append(expediente)
                                    references_found = True
                                    print(f"Expediente detectado: {expediente} en: {line.strip()}")
                    
                    # Registrar que se procesó correctamente si se encontraron referencias
                    if references_found:
                        total_processed += 1
                        # Registrar los números de pedido
                        for order in current_orders:
                            orders_detected.append(order)
                            if invoice_number:
                                invoice_info[order] = {
                                    'folio': invoice_number,
                                    'fecha': emission_date if emission_date else ''
                                }
                                print(f"Registrando pedido {order} con factura {invoice_number} y fecha {emission_date}")
                        
                        # Registrar los expedientes
                        for expediente in current_expedientes:
                            expedientes_detected.append(expediente)
                            if invoice_number:
                                invoice_info[expediente] = {
                                    'folio': invoice_number,
                                    'fecha': emission_date if emission_date else ''
                                }
                                print(f"Registrando expediente {expediente} con factura {invoice_number} y fecha {emission_date}")
                    else:
                        invalid_pdfs.append(pdf_file)
                        log.write(f"\n=== {pdf_file} ===\n")
                        log.write("Primeras 10 líneas del contenido:\n")
                        preview_lines = full_text.split('\n')[:10]
                        for line in preview_lines:
                            log.write(f"{line}\n")
                        log.write("-" * 50 + "\n")
                        
            except Exception as e:
                invalid_pdfs.append(pdf_file)
                log.write(f"\n=== {pdf_file} ===\n")
                log.write(f"Error al procesar el archivo: {str(e)}\n")
                log.write("-" * 50 + "\n")

        # Resumen final
        log.write("\n\n=== RESUMEN ===\n")
        log.write(f"Total de PDFs encontrados: {len(pdf_files)}\n")
        log.write(f"PDFs procesados exitosamente: {total_processed}\n")
        log.write(f"PDFs sin referencias encontradas: {len(invalid_pdfs)}\n")
        log.write("\nLista de archivos a revisar:\n")
        for pdf in invalid_pdfs:
            log.write(f"- {pdf}\n")
        
        # Añadir los pedidos y expedientes detectados al reporte
        if orders_detected:
            log.write("\nNúmeros de pedido detectados:\n")
            for order in orders_detected:
                log.write(f"- {order}: Factura {invoice_info.get(order, {}).get('folio', 'N/A')}, Fecha {invoice_info.get(order, {}).get('fecha', 'N/A')}\n")
        
        if expedientes_detected:
            log.write("\nNúmeros de expediente detectados:\n")
            for exp in expedientes_detected:
                log.write(f"- {exp}: Factura {invoice_info.get(exp, {}).get('folio', 'N/A')}, Fecha {invoice_info.get(exp, {}).get('fecha', 'N/A')}\n")
    
    return list(set(orders_detected)), list(set(expedientes_detected)), invoice_info

def update_excel_with_status(excel_path, orders_detected, expedientes_detected, invoice_info):
    try:
        print("Iniciando actualización del Excel...")
        # Leer el archivo Excel
        df = pd.read_excel(excel_path)
        print(f"Excel leído correctamente. Columnas actuales: {df.columns.tolist()}")
        
        # Crear las columnas si no existen, pero NO resetear valores existentes
        if 'Status' not in df.columns:
            df['Status'] = 'NO FACTURADO'
        if 'No factura' not in df.columns:
            df['No factura'] = ''
        # Crear columna para fecha de emisión si no existe
        if 'Fecha emisión' not in df.columns:
            df['Fecha emisión'] = ''
        
        print(f"Columnas después de verificar: {df.columns.tolist()}")
        
        # Asegurar que las columnas sean string y limpiar espacios
        df['Numero de Pedido'] = df['Numero de Pedido'].astype(str).str.strip()
        df['Nº de pieza'] = df['Nº de pieza'].astype(str).str.strip()
        
        # Limpiar números de pedido detectados y convertir a strings
        orders_detected = [str(order).strip() for order in orders_detected]
        expedientes_detected = [str(exp).strip() for exp in expedientes_detected]
        
        print(f"Procesando {len(orders_detected)} pedidos y {len(expedientes_detected)} expedientes")
        print(f"Lista de pedidos detectados: {orders_detected}")
        print(f"Lista de expedientes detectados: {expedientes_detected}")
        
        # Debug: Imprimir información sobre los invoice_info
        print("\nInformación de facturas detectadas:")
        for pedido, info in invoice_info.items():
            print(f"Pedido: {pedido} - Factura: {info.get('folio', 'N/A')} - Fecha: {info.get('fecha', 'N/A')}")
        
        # Debug: Imprimir algunos registros del Excel para verificar los datos
        print("\nPrimeros 5 registros del Excel:")
        for i, row in df.head().iterrows():
            print(f"Índice {i}: Pedido={row['Numero de Pedido']}, Expediente={row['Nº de pieza']}")
        
        # Actualizar solo los registros encontrados en los PDFs actuales
        actualizados = 0
        for index, row in df.iterrows():
            pedido = str(row['Numero de Pedido']).strip()
            expediente = str(row['Nº de pieza']).strip()
            
            # Debug: imprimir algunos valores para comparación
            if index < 5:
                print(f"Comparando - Row[{index}]: Pedido='{pedido}' vs pedidos detectados: {orders_detected[:3] if orders_detected else 'vacío'}")
            
            # Solo actualizar si el registro está en los detectados actualmente
            if pedido in orders_detected:
                # Obtener información de la factura para este pedido
                invoice_data = invoice_info.get(pedido, {})
                current_factura = invoice_data.get('folio', '')
                current_fecha = invoice_data.get('fecha', '')
                
                print(f"¡Coincidencia encontrada! Pedido {pedido} corresponde a factura {current_factura}")
                
                # Actualizar siempre para asegurar que se actualice
                df.at[index, 'Status'] = 'FACTURADO'
                df.at[index, 'No factura'] = current_factura
                df.at[index, 'Fecha emisión'] = current_fecha
                actualizados += 1
                print(f"Actualizando pedido {pedido} con factura {current_factura} y fecha {current_fecha}")
                    
            elif expediente in expedientes_detected:
                # Obtener información de la factura para este expediente
                invoice_data = invoice_info.get(expediente, {})
                current_factura = invoice_data.get('folio', '')
                current_fecha = invoice_data.get('fecha', '')
                
                print(f"¡Coincidencia encontrada! Expediente {expediente} corresponde a factura {current_factura}")
                
                # Actualizar siempre para asegurar que se actualice
                df.at[index, 'Status'] = 'FACTURADO POR EXPEDIENTE'
                df.at[index, 'No factura'] = current_factura
                df.at[index, 'Fecha emisión'] = current_fecha
                actualizados += 1
                print(f"Actualizando expediente {expediente} con factura {current_factura} y fecha {current_fecha}")
            
            # Si no está en los detectados, mantener su estado actual
        
        print(f"Total de registros actualizados: {actualizados}")
        
        # Convertir las fechas de emisión a formato de fecha de Excel
        # Primero asegurarse de que todas las fechas sean strings
        df['Fecha emisión'] = df['Fecha emisión'].astype(str)
        
        # Ahora intentamos convertir a fechas de pandas donde sea posible
        # pero sin afectar las celdas que no tengan un formato reconocible
        try:
            # Crear una máscara para identificar valores que parecen fechas
            fecha_mask = df['Fecha emisión'].str.contains(r'\d{2}/\d{2}/\d{4}')
            # Aplicar la conversión solo a esas celdas
            if fecha_mask.any():
                df.loc[fecha_mask, 'Fecha emisión'] = pd.to_datetime(
                    df.loc[fecha_mask, 'Fecha emisión'], 
                    format='%d/%m/%Y',
                    errors='coerce'
                )
            print("Conversión de fechas realizada correctamente")
        except Exception as e:
            print(f"Advertencia al convertir fechas: {str(e)} - Continuando sin conversión")
        
        # Guardar el Excel con las modificaciones
        df.to_excel(excel_path, index=False)
        print(f"Excel guardado exitosamente en: {excel_path}")
        
        # Verificar que los cambios se guardaron
        df_verification = pd.read_excel(excel_path)
        print(f"Verificación - Columnas en el archivo guardado: {df_verification.columns.tolist()}")
        factura_count = df_verification['No factura'].astype(str).str.strip().apply(lambda x: len(x) > 0).sum()
        fecha_count = df_verification['Fecha emisión'].astype(str).str.strip().apply(lambda x: len(x) > 0).sum()
        print(f"Verificación - Número de registros con factura: {factura_count}")
        print(f"Verificación - Número de registros con fecha de emisión: {fecha_count}")
        
    except Exception as e:
        print(f"Error al actualizar el Excel: {str(e)}")
        raise  # Re-lanzar la excepción para ver el stack trace completo

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Procesador de Facturas - Detecta y actualiza números de pedido en el Excel.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplo de uso:
    python scripts/detect.py PDF-FACTURAS output/data.xlsx --log_file output/log_facturas.txt

Estructura de carpetas:
    PDF-FACTURAS/     → Carpeta con las facturas a procesar
    output/           → Carpeta donde se guardan los resultados
        data.xlsx     → Excel con los datos
        log_facturas.txt → Archivo de log del proceso
        """
    )
    
    parser.add_argument("facturas_folder", 
                      help="Ruta de la carpeta PDF-FACTURAS que contiene los PDFs de facturas")
    parser.add_argument("excel_path", 
                      help="Ruta del archivo Excel (output/data.xlsx) que se actualizará")
    parser.add_argument("--log_file", 
                      default="output/log_facturas.txt", 
                      help="Ruta del archivo de logs (default: output/log_facturas.txt)")
    args = parser.parse_args()

    print("\n=== Iniciando Procesamiento de Facturas ===")
    print(f"Carpeta de facturas: {args.facturas_folder}")
    print(f"Archivo Excel: {args.excel_path}")
    print(f"Archivo de log: {args.log_file}")

    os.makedirs(os.path.dirname(args.log_file), exist_ok=True)

    orders_detected, expedientes_detected, invoice_info = extract_order_from_invoice(args.facturas_folder, args.log_file)
    if not orders_detected and not expedientes_detected:
        print("\n⚠️  No se detectaron números de pedido ni expedientes en los PDFs de facturas.")
    else:
        if orders_detected:
            print(f"\n✓ Números de pedido detectados ({len(orders_detected)}):")
            print(f"  {', '.join(orders_detected)}")
            # Mostrar detalles de facturas para los pedidos
            print("\nDetalles de facturas para pedidos:")
            for order in orders_detected[:5]:  # Mostramos solo los primeros 5 para no saturar la consola
                if order in invoice_info:
                    factura = invoice_info[order]['folio']
                    fecha = invoice_info[order]['fecha']
                    print(f"  Pedido: {order} - Factura: {factura} - Fecha emisión: {fecha}")
        if expedientes_detected:
            print(f"\n✓ Números de expediente detectados ({len(expedientes_detected)}):")
            print(f"  {', '.join(expedientes_detected)}")
            # Mostrar detalles de facturas para los expedientes
            print("\nDetalles de facturas para expedientes:")
            for exp in expedientes_detected[:5]:  # Mostramos solo los primeros 5 para no saturar la consola
                if exp in invoice_info:
                    factura = invoice_info[exp]['folio']
                    fecha = invoice_info[exp]['fecha']
                    print(f"  Expediente: {exp} - Factura: {factura} - Fecha emisión: {fecha}")

    update_excel_with_status(args.excel_path, orders_detected, expedientes_detected, invoice_info)