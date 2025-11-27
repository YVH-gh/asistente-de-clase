import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Importamos las tablas que diseñamos en el archivo anterior
# NOTA: Asegúrate de que el archivo anterior se llame 'crear_base_datos.py'
from crear_base_datos import Alumno, Materia, Evaluacion, Base

# --- CONFIGURACIÓN DE LA RUTA ESPECÍFICA ---
# Usamos 'r' antes de las comillas para indicar una "raw string" y evitar problemas con las barras invertidas de Windows
ruta_db = r'C:\Users\Silicon40\Documents\ProyectosPython\seguimiento_alumnos\sistema_escolar.db'
engine = create_engine(f'sqlite:///{ruta_db}')

# Creamos la Sesión (es como abrir una transacción en el banco)
Session = sessionmaker(bind=engine)
session = Session()

print("🚀 Iniciando carga de datos de prueba...")

# --- PASO 1: CREAR MATERIAS ---
# Verificamos si ya existen para no duplicar
if session.query(Materia).count() == 0:
    mat_historia = Materia(nombre="Historia", profesor_titular="Prof. Martínez")
    mat_matematica = Materia(nombre="Matemáticas", profesor_titular="Prof. López")
    
    session.add(mat_historia)
    session.add(mat_matematica)
    print("   -> Materias creadas.")
else:
    # Si ya existen, las recuperamos para usarlas
    mat_historia = session.query(Materia).filter_by(nombre="Historia").first()
    mat_matematica = session.query(Materia).filter_by(nombre="Matemáticas").first()
    print("   -> Materias ya existían, las recuperamos.")

# --- PASO 2: CREAR ALUMNO ---
alumno_nuevo = Alumno(nombre_completo="Carlos Ruiz", año_escolar=2)
session.add(alumno_nuevo)
print(f"   -> Alumno '{alumno_nuevo.nombre_completo}' preparado para insertar.")

# --- PASO 3: CARGAR EVALUACIONES (El dato crítico para la IA) ---
# Aquí simulamos que el profesor cargó una nota baja con un comentario

evaluacion_1 = Evaluacion(
    alumno=alumno_nuevo,      # Conectamos con Carlos (SQLAlchemy maneja el ID solo)
    materia=mat_historia,     # Conectamos con Historia
    instancia="Parcial 1 - Revolución Industrial",
    nota=4.0,                 # Nota baja
    comentario="El alumno confunde las causas económicas con las políticas. No mencionó la máquina de vapor.",
    fecha=datetime.now()
)

evaluacion_2 = Evaluacion(
    alumno=alumno_nuevo,
    materia=mat_matematica,
    instancia="Ejercicios Álgebra",
    nota=8.5,
    comentario="Buen desempeño, aunque debe revisar los signos en ecuaciones complejas.",
    fecha=datetime.now()
)

session.add(evaluacion_1)
session.add(evaluacion_2)

# --- PASO 4: GUARDAR CAMBIOS (COMMIT) ---
# Hasta aquí, todo estaba en la memoria RAM. Al hacer commit, se escribe en el disco.
session.commit()

print("✅ ¡Datos guardados exitosamente en la base de datos!")
print(f"📂 Ubicación verificada: {ruta_db}")