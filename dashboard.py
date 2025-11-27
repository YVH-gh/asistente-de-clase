import streamlit as st
import pandas as pd
import base64
from fpdf import FPDF
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from crear_base_datos import Alumno, Materia, Evaluacion
# Importamos las DOS funciones de la IA
from modulo_ia_github import generar_recomendacion_ia, responder_chat_educativo

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sistema Escolar 360", layout="wide", page_icon="🎓")

ruta_db = r'C:\Users\Silicon40\Documents\ProyectosPython\seguimiento_alumnos\sistema_escolar.db'
engine = create_engine(f'sqlite:///{ruta_db}')
Session = sessionmaker(bind=engine)

def get_session():
    return Session()


def crear_reporte_pdf(alumno, recomendaciones_ia_texto):
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, 'Informe de Rendimiento Academico', 0, 1, 'C')
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # 1. Datos del Alumno
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"Alumno: {alumno.nombre_completo}", 0, 1)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Ano Escolar: {alumno.año_escolar}", 0, 1)
    pdf.ln(5)
    
    # 2. Tabla de Notas
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Historial de Evaluaciones:", 0, 1)
    pdf.set_font("Arial", size=10)
    
    # Encabezados tabla
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(40, 10, "Materia", 1, 0, 'C', 1)
    pdf.cell(40, 10, "Instancia", 1, 0, 'C', 1)
    pdf.cell(20, 10, "Nota", 1, 0, 'C', 1)
    pdf.cell(90, 10, "Comentario", 1, 1, 'C', 1)
    
    # Filas
    if alumno.evaluaciones:
        for ev in alumno.evaluaciones:
            pdf.cell(40, 10, ev.materia.nombre[:20], 1)
            pdf.cell(40, 10, ev.instancia[:20], 1)
            pdf.cell(20, 10, str(ev.nota), 1, 0, 'C')
            # El comentario puede ser largo, cortamos para que entre en una linea simple
            comentario_corto = (ev.comentario[:45] + '...') if len(ev.comentario) > 45 else ev.comentario
            pdf.cell(90, 10, comentario_corto, 1, 1)
    else:
        pdf.cell(0, 10, "Sin evaluaciones registradas.", 1, 1)
        
    pdf.ln(10)

    # 3. Recomendaciones de la IA (Lo más valioso)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Analisis del Asistente Virtual:", 0, 1)
    pdf.set_font("Arial", 'I', 11)
    
    # Escribimos el texto que generó la IA (respetando saltos de línea)
    pdf.multi_cell(0, 10, recomendaciones_ia_texto)
    
    pdf.ln(10)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, f"Reporte generado el: {datetime.now().strftime('%d/%m/%Y')}", 0, 1)

    return pdf.output(dest='S').encode('latin-1', 'replace') # Retorna los bytes del PDF

# --- CSS PARA EL CHAT ---
st.markdown("""
<style>
    .stChatMessage {background-color: #f0f2f6; border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

# --- NAVEGACIÓN ---
session = get_session()
st.sidebar.title("🏫 Menú Principal")
modo = st.sidebar.radio("Ir a:", ["📊 Dashboard & Chat IA", "⚙️ Administración General"])

# ==============================================================================
# MODO 1: ADMINISTRACIÓN (CARGA Y GESTIÓN)
# ==============================================================================
if modo == "⚙️ Administración General":
    st.title("⚙️ Panel de Control")
    tab1, tab2, tab3, tab4 = st.tabs(["📚 GESTIÓN MATERIAS", "👤 Alumnos", "📝 Notas", "📂 Importar"])

    # --- PESTAÑA 1: GESTIÓN DE MATERIAS (LO QUE PEDISTE) ---
    with tab1:
        st.subheader("Administrar Materias")
        col_new, col_edit = st.columns(2)
        
        # 1. Crear Nueva Materia
        with col_new:
            st.info("➕ Crear Nueva Materia")
            with st.form("add_materia"):
                new_mat_name = st.text_input("Nombre de la Materia")
                new_prof = st.text_input("Profesor Titular")
                if st.form_submit_button("Crear Materia") and new_mat_name:
                    existe = session.query(Materia).filter_by(nombre=new_mat_name).first()
                    if not existe:
                        session.add(Materia(nombre=new_mat_name, profesor_titular=new_prof))
                        session.commit()
                        st.success(f"Materia '{new_mat_name}' creada.")
                        st.rerun()
                    else:
                        st.error("Esa materia ya existe.")

        # 2. Editar / Borrar Materia Existente
        with col_edit:
            st.warning("✏️ Editar o Eliminar")
            materias = session.query(Materia).all()
            if materias:
                materia_a_editar = st.selectbox("Selecciona Materia", [m.nombre for m in materias])
                obj_materia = session.query(Materia).filter_by(nombre=materia_a_editar).first()
                
                nuevo_nombre = st.text_input("Nuevo Nombre", value=obj_materia.nombre)
                nuevo_profe = st.text_input("Nuevo Profesor", value=obj_materia.profesor_titular)
                
                c1, c2 = st.columns(2)
                if c1.button("💾 Guardar Cambios"):
                    obj_materia.nombre = nuevo_nombre
                    obj_materia.profesor_titular = nuevo_profe
                    session.commit()
                    st.success("Actualizado.")
                    st.rerun()
                
                if c2.button("🗑️ ELIMINAR MATERIA", type="primary"):
                    # Verificamos seguridad: ¿Tiene notas cargadas?
                    if obj_materia.evaluaciones:
                        st.error("⛔ No puedes eliminar esta materia porque tiene notas asociadas. Borra las notas primero.")
                    else:
                        session.delete(obj_materia)
                        session.commit()
                        st.success("Materia eliminada.")
                        st.rerun()

    # --- PESTAÑA 2: ALUMNOS (Carga Rápida) ---
    with tab2:
        with st.form("add_alumno"):
            st.write("Nuevo Alumno")
            nom = st.text_input("Nombre Completo")
            anio = st.number_input("Año", 1, 6)
            if st.form_submit_button("Guardar") and nom:
                session.add(Alumno(nombre_completo=nom, año_escolar=anio))
                session.commit()
                st.success("Alumno guardado.")

    # --- PESTAÑA 3: CARGA DE NOTAS ---
    with tab3:
        alumnos_list = session.query(Alumno).all()
        materias_list = session.query(Materia).all()
        if alumnos_list and materias_list:
            with st.form("add_nota"):
                c_a, c_m = st.columns(2)
                alu_sel = c_a.selectbox("Alumno", [a.nombre_completo for a in alumnos_list])
                mat_sel = c_m.selectbox("Materia", [m.nombre for m in materias_list])
                
                instancia = st.text_input("Instancia (Ej: TP Final)")
                nota = st.number_input("Nota", 0.0, 10.0, step=0.5)
                comentario = st.text_area("Comentario")
                
                if st.form_submit_button("Guardar Nota"):
                    a_id = session.query(Alumno).filter_by(nombre_completo=alu_sel).first().id
                    m_id = session.query(Materia).filter_by(nombre=mat_sel).first().id
                    
                    session.add(Evaluacion(alumno_id=a_id, materia_id=m_id, instancia=instancia, nota=nota, comentario=comentario, fecha=datetime.now()))
                    session.commit()
                    st.success("Nota guardada.")
        else:
            st.warning("Carga alumnos y materias primero.")

    # --- PESTAÑA 4: IMPORTACIÓN ---
    with tab4:
        st.write("Sube tu Excel (Columnas: Nombre, Año)")
        archivo = st.file_uploader("Archivo", type=['xlsx', 'csv'])
        if archivo and st.button("Importar"):
            try:
                df = pd.read_excel(archivo) if archivo.name.endswith('xlsx') else pd.read_csv(archivo)
                count = 0
                for _, row in df.iterrows():
                    if not session.query(Alumno).filter_by(nombre_completo=row['Nombre']).first():
                        session.add(Alumno(nombre_completo=row['Nombre'], año_escolar=int(row['Año'])))
                        count += 1
                session.commit()
                st.success(f"Importados {count} alumnos.")
            except Exception as e:
                st.error(f"Error: {e}")

# ==============================================================================
# MODO 2: DASHBOARD + CHAT IA
# ==============================================================================
elif modo == "📊 Dashboard & Chat IA":
    st.title("Dashboard del Alumno")
    
    alumnos = session.query(Alumno).all()
    if alumnos:
        seleccion = st.sidebar.selectbox("🔍 Buscar Alumno:", [a.nombre_completo for a in alumnos])
        alumno = session.query(Alumno).filter_by(nombre_completo=seleccion).first()
        
        # --- ENCABEZADO Y KPI ---
        notas = [e.nota for e in alumno.evaluaciones]
        promedio = sum(notas) / len(notas) if notas else 0
        col1, col2, col3 = st.columns(3)
        col1.metric("Alumno", alumno.nombre_completo)
        col2.metric("Promedio General", f"{promedio:.2f}")
        col3.metric("Evaluaciones", len(notas))
        st.divider()

        
        # --- GENERADOR DE REPORTE ---
        col_btn_1, col_btn_2 = st.columns([3, 1])
        with col_btn_2:
            # Botón para generar el PDF
            if st.button("📄 Preparar Informe PDF"):
                # Primero, pedimos a la IA un resumen general para poner en el PDF
                with st.spinner("Generando resumen ejecutivo con IA..."):
                    resumen_ia = responder_chat_educativo(
                        alumno.nombre_completo, 
                        f"Promedio: {promedio}. Notas: {notas}", 
                        "Escribe un párrafo de conclusión formal sobre el rendimiento de este alumno para los padres."
                    )
                
                # Creamos el archivo en memoria
                pdf_bytes = crear_reporte_pdf(alumno, resumen_ia)
                
                # Mostramos el botón de descarga real
                st.download_button(
                    label="⬇️ Descargar PDF Final",
                    data=pdf_bytes,
                    file_name=f"Reporte_{alumno.nombre_completo}.pdf",
                    mime="application/pdf"
                )
        
        # ... (Aquí sigue la sección de 'dividir la pantalla' con col_datos y col_chat)

        # --- DIVIDIMOS LA PANTALLA: DATOS A LA IZQ, CHAT A LA DER ---
        col_datos, col_chat = st.columns([2, 1])

        with col_datos:
            st.subheader("📉 Historial Académico")
            if alumno.evaluaciones:
                df_show = pd.DataFrame([{
                    "Fecha": e.fecha,
                    "Materia": e.materia.nombre,
                    "Instancia": e.instancia,
                    "Nota": e.nota,
                    "Comentario": e.comentario
                } for e in alumno.evaluaciones])
                st.dataframe(df_show, use_container_width=True)
                
                # Gráfico rápido
                st.line_chart(df_show.set_index("Fecha")["Nota"])
            else:
                st.info("Sin datos para mostrar gráficos.")

        with col_chat:
            st.subheader("💬 Chat con IA")
            st.markdown("Pregunta sobre este alumno. La IA leerá sus notas.")
            
            # Historial del chat (se borra al recargar, simple para prototipo)
            if "messages" not in st.session_state:
                st.session_state.messages = []

            # Input del usuario
            pregunta = st.chat_input(f"Ej: ¿Cómo va {alumno.nombre_completo} en Historia?")
            
            if pregunta:
                # 1. Mostramos pregunta usuario
                with st.chat_message("user"):
                    st.write(pregunta)
                
                # 2. Preparamos el contexto para la IA (Le damos los datos crudos)
                contexto_notas = ""
                if alumno.evaluaciones:
                    for ev in alumno.evaluaciones:
                        contexto_notas += f"- En {ev.materia.nombre} ({ev.instancia}): Nota {ev.nota}. Comentario profe: {ev.comentario}\n"
                else:
                    contexto_notas = "El alumno no tiene notas registradas aún."

                # 3. Llamamos a la IA (con Spinner para que se vea que piensa)
                with st.chat_message("assistant"):
                    with st.spinner("Leyendo base de datos..."):
                        respuesta = responder_chat_educativo(alumno.nombre_completo, contexto_notas, pregunta)
                        st.write(respuesta)

session.close()