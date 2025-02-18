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
    invoice_numbers = {}  # Diccionario para almacenar número de factura por pedido/expediente
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
                    
                    # Buscar SERIE y FOLIO al inicio del documento
                    first_page_text = pdf.pages[0].extract_text()
                    serie_match = re.search(r'SERIE:\s*([A-Za-z])', first_page_text)
                    folio_match = re.search(r'FOLIO:\s*(\d+)', first_page_text)
                    
                    if serie_match and folio_match:
                        serie = serie_match.group(1)
                        folio = folio_match.group(1)
                        invoice_number = f"{serie}{folio}"
                    
                    for page in pdf.pages:
                        text = page.extract_text()
                        if not text:
                            continue
                            
                        full_text += text + "\n"
                        
                        # Verificar si tiene sección de DESCRIPCIÓN
                        if 'DESCRIPCIÓN' in text.upper():
                            has_description_section = True

                        lines = text.split('\n')
                        in_description_section = False
                        for line in lines:
                            # Detectar si estamos en la sección de DESCRIPCIÓN
                            if 'DESCRIPCIÓN' in line.upper():
                                in_description_section = True
                                continue
                            
                            # Si estamos en la sección de DESCRIPCIÓN y encontramos una línea que contiene 
                            # IMPUESTOS FEDERALES, salimos de la sección
                            if in_description_section and 'IMPUESTOS FEDERALES' in line.upper():
                                in_description_section = False
                                continue
                            
                            # Solo procesar líneas dentro de la sección de DESCRIPCIÓN
                            if in_description_section:
                                # Buscar números de 10 dígitos (pedidos)
                                pedidos = re.finditer(r'\b\d{10}\b', line)
                                for match in pedidos:
                                    order_number = match.group()
                                    current_orders.append(order_number)
                                    print(f"Pedido detectado en DESCRIPCIÓN: {order_number} en: {line.strip()}")
                                
                                # Buscar números de 8 dígitos (expedientes)
                                expedientes = re.finditer(r'\b\d{8}\b', line)
                                for match in expedientes:
                                    expediente = match.group()
                                    current_expedientes.append(expediente)
                                    print(f"Expediente detectado en DESCRIPCIÓN: {expediente} en: {line.strip()}")
                                    
                                # Buscar números que puedan estar separados
                                separated_numbers = re.finditer(r'\b\d{4}[\s\.\-_]\d{4,6}\b', line)
                                for match in separated_numbers:
                                    number = re.sub(r'[\s\.\-_]', '', match.group())
                                    if len(number) == 10:
                                        current_orders.append(number)
                                        print(f"Pedido detectado (formato separado) en DESCRIPCIÓN: {number} en: {line.strip()}")
                                    elif len(number) == 8:
                                        current_expedientes.append(number)
                                        print(f"Expediente detectado (formato separado) en DESCRIPCIÓN: {number} en: {line.strip()}")

                            # Finalmente, buscar números de 10 dígitos con contexto general
                            pedidos = re.finditer(r'\b\d{10}\b', line)
                            for match in pedidos:
                                order_number = match.group()
                                if is_valid_context(line, order_number, pedido_keywords):
                                    current_orders.append(order_number)
                                    print(f"Pedido detectado: {order_number} en: {line.strip()}")
                            
                            # Buscar expedientes (8 dígitos)
                            expedientes = re.finditer(r'\b\d{8}\b', line)
                            for match in expedientes:
                                expediente = match.group()
                                if is_valid_context(line, expediente, expediente_keywords):
                                    current_expedientes.append(expediente)
                                    print(f"Expediente detectado: {expediente} en: {line.strip()}")
                            
                            # Buscar números que puedan estar separados por espacios o caracteres
                            # Por ejemplo: "1234 5678" o "1234.5678"
                            separated_numbers = re.finditer(r'\b\d{4}[\s\.\-_]\d{4,6}\b', line)
                            for match in separated_numbers:
                                number = re.sub(r'[\s\.\-_]', '', match.group())
                                if len(number) == 10 and is_valid_context(line, match.group(), pedido_keywords):
                                    current_orders.append(number)
                                    print(f"Pedido detectado (formato separado): {number} en: {line.strip()}")
                                elif len(number) == 8 and is_valid_context(line, match.group(), expediente_keywords):
                                    current_expedientes.append(number)
                                    print(f"Expediente detectado (formato separado): {number} en: {line.strip()}")

                    # Solo incrementar total_processed si encontramos referencias válidas
                    if current_orders or current_expedientes:
                        if current_orders:
                            for order in current_orders:
                                orders_detected.append(order)
                                if invoice_number:
                                    invoice_numbers[order] = invoice_number
                        if current_expedientes:
                            for expediente in current_expedientes:
                                expedientes_detected.append(expediente)
                                if invoice_number:
                                    invoice_numbers[expediente] = invoice_number
                        total_processed += 1
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
    
    return list(set(orders_detected)), list(set(expedientes_detected)), invoice_numbers

def update_excel_with_status(excel_path, orders_detected, expedientes_detected, invoice_numbers):
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
        
        print(f"Columnas después de verificar: {df.columns.tolist()}")
        
        # Asegurar que las columnas sean string y limpiar espacios
        df['Numero de Pedido'] = df['Numero de Pedido'].astype(str).str.strip()
        df['Nº de pieza'] = df['Nº de pieza'].astype(str).str.strip()
        
        # Limpiar números de pedido detectados
        orders_detected = [str(order).strip() for order in orders_detected]
        expedientes_detected = [str(exp).strip() for exp in expedientes_detected]
        
        print(f"Procesando {len(orders_detected)} pedidos y {len(expedientes_detected)} expedientes")
        
        # Actualizar solo los registros encontrados en los PDFs actuales
        actualizados = 0
        for index, row in df.iterrows():
            pedido = str(row['Numero de Pedido']).strip()
            expediente = str(row['Nº de pieza']).strip()
            
            # Solo actualizar si el registro está en los detectados actualmente
            if pedido in orders_detected:
                # Si ya está facturado, verificar si es la misma factura
                current_factura = invoice_numbers.get(pedido, '')
                if row['Status'] != 'FACTURADO' or (row['No factura'] != current_factura and current_factura != ''):
                    df.at[index, 'Status'] = 'FACTURADO'
                    df.at[index, 'No factura'] = current_factura
                    actualizados += 1
                    print(f"Actualizando pedido {pedido} con factura {current_factura}")
                    
            elif expediente in expedientes_detected:
                # Si ya está facturado por expediente, verificar si es la misma factura
                current_factura = invoice_numbers.get(expediente, '')
                if row['Status'] != 'FACTURADO POR EXPEDIENTE' or (row['No factura'] != current_factura and current_factura != ''):
                    df.at[index, 'Status'] = 'FACTURADO POR EXPEDIENTE'
                    df.at[index, 'No factura'] = current_factura
                    actualizados += 1
                    print(f"Actualizando expediente {expediente} con factura {current_factura}")
            
            # Si no está en los detectados, mantener su estado actual
        
        print(f"Total de registros actualizados: {actualizados}")
        
        # Guardar el Excel con las modificaciones
        df.to_excel(excel_path, index=False)
        print(f"Excel guardado exitosamente en: {excel_path}")
        
        # Verificar que los cambios se guardaron
        df_verification = pd.read_excel(excel_path)
        print(f"Verificación - Columnas en el archivo guardado: {df_verification.columns.tolist()}")
        print(f"Verificación - Número de registros con factura: {df_verification['No factura'].notna().sum()}")
        
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

    orders_detected, expedientes_detected, invoice_numbers = extract_order_from_invoice(args.facturas_folder, args.log_file)
    if not orders_detected and not expedientes_detected:
        print("\n⚠️  No se detectaron números de pedido ni expedientes en los PDFs de facturas.")
    else:
        if orders_detected:
            print(f"\n✓ Números de pedido detectados ({len(orders_detected)}):")
            print(f"  {', '.join(orders_detected)}")
        if expedientes_detected:
            print(f"\n✓ Números de expediente detectados ({len(expedientes_detected)}):")
            print(f"  {', '.join(expedientes_detected)}")

    update_excel_with_status(args.excel_path, orders_detected, expedientes_detected, invoice_numbers)