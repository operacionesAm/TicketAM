"""Punto de entrada. Vercel importa la variable `app` de este mismo módulo
(ver vercel.json); localmente se corre como script para levantar el
servidor de desarrollo.
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
