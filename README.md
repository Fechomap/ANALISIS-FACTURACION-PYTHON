# Análisis Facturación

Sistema de procesamiento de PDFs para extraer información de pedidos y facturas, actualizando un archivo Excel centralizado.

## Requisitos Previos

- Python 3.7 o superior
- Node.js (opcional, pero recomendado para mejor experiencia)
- pip (gestor de paquetes de Python)
- virtualenv o venv

## Instalación

1. **Clonar el repositorio**
   ```bash
   git clone <url-del-repositorio>
   cd ANALISIS-FACTURACION
   ```

2. **Crear y activar entorno virtual**
   ```bash
   # En macOS/Linux
   python -m venv venv
   source venv/bin/activate

   # En Windows
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. **Instalar dependencias**
   ```bash
   pip install -r requirements.txt
   npm install  # Solo si vas a usar app.js
   ```

4. **Verificar instalación**
   ```bash
   python -c "import pdfplumber; import pandas; print('Instalación correcta')"
   ```

## Estructura del Proyecto

```
ANALISIS-FACTURACION/
├── PDF-PEDIDOS/    → PDFs de pedidos de compra
├── PDF-FACTURAS/   → PDFs de facturas
├── output/         → Archivos de salida (Excel y logs)
├── scripts/        → Scripts Python
│   ├── detect.py   → Procesamiento de facturas
│   ├── detect2.py  → Procesamiento de nuevas facturas (formato mejorado)
│   └── extract.py  → Procesamiento de pedidos
├── app.js          → Interfaz Node.js (recomendado)
├── package.json    → Dependencias de Node.js
├── requirements.txt → Dependencias de Python
└── README.md
```

## Uso

### 1. Método Recomendado (usando Node.js)
```bash
node app.js
```
Este comando:
- Verifica la existencia de directorios necesarios
- Muestra los PDFs disponibles para procesar
- Ejecuta ambos scripts secuencialmente
- Muestra logs detallados del proceso
- Verifica el resultado final

### 2. Método Alternativo (scripts individuales)

#### Procesamiento de Pedidos de Compra
```bash
python scripts/extract.py PDF-PEDIDOS output/data.xlsx output/log.txt
```
- Procesa PDFs de `PDF-PEDIDOS/`
- Genera/actualiza `output/data.xlsx`
- Crea log en `output/log.txt`

#### Procesamiento de Facturas
```bash
python scripts/detect.py PDF-FACTURAS output/data.xlsx --log_file output/log_facturas.txt
```
- Procesa facturas de `PDF-FACTURAS/`
- Detecta números de pedido (10 dígitos)
- Actualiza estados en Excel
- Genera log en `output/log_facturas.txt`

#### Procesamiento de Facturas (Nuevo Formato)
```bash
python scripts/detect2.py PDF-FACTURAS output/data.xlsx --log_file output/log_facturas_nuevas.txt
```
- Procesa facturas con nuevo formato de `PDF-FACTURAS/`
- Detecta números de pedido y datos adicionales
- Incluye fecha de emisión en la información
- Actualiza estados en Excel con información detallada
- Genera log en `output/log_facturas_nuevas.txt`

## Flujo de Trabajo Típico

1. Activar el entorno virtual
   ```bash
   source venv/bin/activate  # En macOS/Linux
   .\venv\Scripts\activate   # En Windows
   ```

2. Colocar archivos:
   - PDFs de pedidos en `PDF-PEDIDOS/`
   - PDFs de facturas en `PDF-FACTURAS/`

3. Ejecutar el procesamiento:
   ```bash
   node app.js
   ```

4. Verificar resultados:
   - Excel actualizado en `output/data.xlsx`
   - Logs en `output/log.txt` y `output/log_facturas.txt`

## Solución de Problemas

### Error: ModuleNotFoundError
```bash
# Asegúrate de estar en el entorno virtual y tener dependencias
source venv/bin/activate
pip install -r requirements.txt
```

### Error: FileNotFoundError
El sistema creará automáticamente las carpetas necesarias, pero asegúrate de:
- Colocar los PDFs en las carpetas correctas
- No tener caracteres especiales en nombres de archivo

## Notas Importantes

- El sistema mantiene un historial acumulativo en el Excel
- No es necesario borrar PDFs procesados
- Los nuevos PDFs se procesan y agregan/actualizan registros existentes
- Se puede ejecutar el proceso aunque no haya PDFs nuevos
- Se recomienda hacer respaldo del Excel periódicamente

## Mantenimiento

### Respaldo de Datos
```bash
# Crear copia del Excel
cp output/data.xlsx output/data_backup_$(date +%Y%m%d).xlsx
```

### Limpieza de Logs
```bash
# Limpiar archivos temporales
rm output/output_temp.json
rm output/log*.txt
```

### Actualizar Dependencias
```bash
pip freeze > requirements.txt
npm update  # Si usas Node.js
```