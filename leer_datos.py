import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
# Importamos las clases para saber qué estamos buscando
from crear_base_datos import Alumno, Materia, Evaluacion

# --- CONFIGURACIÓN (La misma ruta absoluta) ---
ruta_db = r'C:\Users\Silicon40\Documents\ProyectosPython\seguimiento_alumnos\sistema_escolar.db'
engine = create_engine(f'sqlite:///{ruta_db}')

Session = sessionmaker(bind=engine)
session = Session()

def mostrar_dashboard_alumno(nombre_busqueda):
    print(f"\n🔎 Buscando información para: '{nombre_busqueda}'...")
    print("-" * 50)
    
    # 1. Buscamos al alumno en la tabla 'alumnos'
    #    filter(Alumno.nombre_completo.like(...)) permite buscar aunque no escribas el nombre exacto
    alumno = session.query(Alumno).filter(Alumno.nombre_completo.like(f"%{nombre_busqueda}%")).first()
    
    if not alumno:
        print("❌ Alumno no encontrado.")
        return

    # 2. Si existe, mostramos sus datos básicos
    print(f"🎓 ALUMNO: {alumno.nombre_completo} (Año: {alumno.año_escolar})")
    
    # 3. Accedemos a sus evaluaciones
    #    Gracias a la relación que definimos (back_populates), no hace falta hacer otra consulta SQL.
    #    Python ya trajo las evaluaciones vinculadas.
    evaluaciones = alumno.evaluaciones
    
    if not evaluaciones:
        print("   (No hay evaluaciones registradas aún)")
    else:
        print(f"   📊 Historial de Rendimiento ({len(evaluaciones)} registros):")
        for ev in evaluaciones:
            # Accedemos al nombre de la materia a través de la relación ev.materia
            print(f"\n   📘 Materia: {ev.materia.nombre}")
            print(f"      Instancia: {ev.instancia}")
            print(f"      Nota: {ev.nota} / 10")
            print(f"      📝 Comentario del Profe: \"{ev.comentario}\"")
            
            # Lógica simple para detectar alertas (esto luego lo hará la IA mejor)
            if ev.nota < 6:
                print("      ⚠️  ALERTA: Rendimiento bajo detectado")

    print("-" * 50)

# --- EJECUCIÓN DE PRUEBA ---
if __name__ == "__main__":
    # Probamos buscar a Carlos
    mostrar_dashboard_alumno("Carlos")