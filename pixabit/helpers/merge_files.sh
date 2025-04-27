#!/bin/bash

# Carpeta base (por defecto el directorio actual)
BASE_DIR="${1:-.}"
OUTPUT_FILE="merged_output.txt"

# Limpiar archivo de salida anterior si existe
> "$OUTPUT_FILE"

# Buscar archivos .py y procesarlos
find "$BASE_DIR" -type f -name "*.py" | while read -r file; do
    REL_PATH="${file#$BASE_DIR/}"  # Ruta relativa
    echo "-------- START OF FILE $REL_PATH --------" >> "$OUTPUT_FILE"
    cat "$file" >> "$OUTPUT_FILE"
    echo -e "\n-------- END OF FILE $REL_PATH --------\n" >> "$OUTPUT_FILE"
done

echo "Contenido combinado en '$OUTPUT_FILE'"

