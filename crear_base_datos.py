import os
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Text, Date
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

# --- CORRECCIÓN: USAR LA RUTA ABSOLUTA ---
ruta_db = r'C:\Users\Silicon40\Documents\ProyectosPython\seguimiento_alumnos\sistema_escolar.db'

# Fíjate que usamos la variable ruta_db aquí dentro
engine = create_engine(f'sqlite:///{ruta_db}', echo=True)

Base = declarative_base()

# --- PASO 1: CONFIGURACIÓN ---
# Aquí definimos que usaremos SQLite.
# El archivo se llamará "sistema_escolar.db" y se creará en la misma carpeta.
# echo=True hará que veas en la consola el SQL que se escribe automáticamente (ideal para aprender).
engine = create_engine('sqlite:///sistema_escolar.db', echo=True)

# Esta es la "plantilla base" de la que heredarán todas nuestras tablas.
Base = declarative_base()

# --- PASO 2: DEFINICIÓN DE TABLAS (MODELOS) ---

class Alumno(Base):
    __tablename__ = 'alumnos' # Nombre real de la tabla en la BD

    # ... imports ...

class Alumno(Base):
    __tablename__ = 'alumnos'
    
    id = Column(Integer, primary_key=True)
    nombre_completo = Column(String, nullable=False)
    año_escolar = Column(Integer)
    dni = Column(String, unique=True) # DNI único
    email = Column(String)            # Opcional
    telefono = Column(String)         # Opcional
    año_escolar = Column(Integer) # Ej: 2 (para 2do año)
    
    # Relación inversa: Permite decir alumno.evaluaciones para ver sus notas
    evaluaciones = relationship("Evaluacion", back_populates="alumno")
    recomendaciones = relationship("Recomendacion", back_populates="alumno")

class Materia(Base):
    __tablename__ = 'materias'
    
    id = Column(Integer, primary_key=True)
    nombre = Column(String, nullable=False) # Ej: "Historia", "Matemática"
    profesor_titular = Column(String)
    
    evaluaciones = relationship("Evaluacion", back_populates="materia")

class Evaluacion(Base):
    __tablename__ = 'evaluaciones' # Nuestra Tabla de Hechos
    
    id = Column(Integer, primary_key=True)
    # Claves Foráneas (Foreign Keys) - Los enlaces a las otras tablas
    alumno_id = Column(Integer, ForeignKey('alumnos.id'))
    materia_id = Column(Integer, ForeignKey('materias.id'))
    
    instancia = Column(String) # Ej: "Parcial 1", "TP Final"
    nota = Column(Float)       # La calificación numérica
    comentario = Column(Text)  # El texto que leerá la IA (Ej: "Falla en...")
    fecha = Column(Date, default=datetime.now)
    
    # Relaciones para navegar
    alumno = relationship("Alumno", back_populates="evaluaciones")
    materia = relationship("Materia", back_populates="evaluaciones")

class Recomendacion(Base):
    __tablename__ = 'recomendaciones' # La tabla de salida de la IA
    
    id = Column(Integer, primary_key=True)
    alumno_id = Column(Integer, ForeignKey('alumnos.id'))
    materia_id = Column(Integer, ForeignKey('materias.id'))
    
    contenido = Column(Text)   # El consejo generado por la IA
    estado = Column(String, default="Pendiente") # Ej: Pendiente, Completada
    fecha_generacion = Column(Date, default=datetime.now)
    
    alumno = relationship("Alumno", back_populates="recomendaciones")

# --- PASO 3: CONSTRUCCIÓN ---
# Esta línea es la que realmente "toca" el disco duro y crea las tablas
if __name__ == "__main__":
    print("🏗️  Comenzando la construcción de la base de datos...")
    
    # Si el archivo ya existe, esto no borra los datos, solo verifica la estructura.
    Base.metadata.create_all(engine)
    
    print("✅ ¡Base de datos 'sistema_escolar.db' creada con éxito!")

    print("   Se han creado las tablas: Alumnos, Materias, Evaluaciones, Recomendaciones.")
