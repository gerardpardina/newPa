import subprocess
import sys
import os

# Mostrar información del entorno
print("Python version:", sys.version)
print("Current directory:", os.getcwd())
print("Files in directory:", os.listdir())

try:
    # Intenta importar directamente el módulo finalapp
    print("Intentando importar finalapp directamente...")
    import finalapp
    print("Importación exitosa, continuando con la ejecución normal...")
except ImportError as e:
    print(f"Error al importar finalapp directamente: {e}")
    print("Intentando ejecutar con Poetry...")
    
    try:
        # Verifica si Poetry está instalado
        subprocess.run(["poetry", "--version"], check=True)
        print("Poetry está instalado, ejecutando aplicación...")
        
        # Intenta ejecutar la app con Poetry
        result = subprocess.run(
            ["poetry", "run", "streamlit", "run", "finalapp.py"],
            check=True
        )
        
        print(f"Aplicación ejecutada con código de salida: {result.returncode}")
    except subprocess.CalledProcessError as e:
        print(f"Error al ejecutar con Poetry: {e}")
    except FileNotFoundError:
        print("Poetry no está instalado en este entorno")
        
        # Si Poetry no está disponible, intenta ejecutar directamente con Streamlit
        print("Intentando ejecutar directamente con Streamlit...")
        try:
            # Importar streamlit para confirmar que está disponible
            import streamlit as st
            
            # Ejecutar el módulo como un script
            with open("finalapp.py", "r") as f:
                exec(f.read())
        except Exception as e:
            print(f"Error al ejecutar finalapp.py: {e}")
            raise 