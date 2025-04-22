import json

with open("content.json", encoding="utf-8") as f:
    contenido = f.read()
    print("Contenido del JSON:", contenido[:100])  # Verifica inicio
    print(f"Contenido tiene {len(contenido)} caracteres")
    print(repr(contenido))

    datos = json.loads(contenido)
