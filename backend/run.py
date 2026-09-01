"""Punto de entrada. Vercel importa la variable `app` de este mismo módulo
(ver vercel.json); localmente se corre como script para levantar el
servidor de desarrollo.
"""
import os
import sys

# Vercel importa este archivo directo (spec.loader.exec_module) sin agregar
# su carpeta a sys.path como sí hace `python run.py` al correrlo localmente
# parado en backend/ — sin esto, "from app import create_app" truena con
# ModuleNotFoundError: No module named 'app' en producción.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
