import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from fpdf import FPDF  # Esto ahora usa fpdf2 gracias a requirements.txt
from crear_base_datos import Alumno, Materia, Evaluacion
from modulo_ia_github import generar_recomendacion_ia, responder_chat_educativo

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Escolar 360", layout="wide", page_icon="🎓")

# --- CONEXIÓN BASE DE DATOS ---
# Usamos ruta relativa para que funcione en la nube y en local
ruta_db = 'sistema_escolar.db'
engine = create_engine(f'sqlite:///{ruta_db}')
Session = sessionmaker(bind=engine)

def get_session():
    return Session()

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .stChatMessage {background-color: #f0f2f6; border-radius: 10px;}
    .metric-card {background-color: #f0f2f6; padding: 15px; border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

# --- 1. SISTEMA DE LOGIN (SEGURIDAD) ---
def check_password():
    if "PASSWORD_ACCESO" not in st.secrets:
        return True # Si no hay clave configurada, pasa (modo desarrollo)

    if "password_correcta" not in st.session_state:
        st.session_state.password_correcta = False

    if not st.session_state.password_correcta:
        st.text_input("🔑 Contraseña de Acceso", type="password", on_change=password_entered, key="password_input")
        return False
    return True

def password_entered():
    if st.session_state["password_input"] == st.secrets["PASSWORD_ACCESO"]:
        st.session_state.password_correcta = True
        del st.session_state["password_input"]
    else:
        st.error("❌ Contraseña incorrecta")

if not check_password():
    st.stop()

# --- 2. FUNCIÓN PDF AVANZADA (Soporte Emojis y Tildes) ---
def crear_reporte_pdf(alumno, recomendaciones_ia_texto):
    class PDF(FPDF):
        def header(self):
            # Intentamos cargar la fuente externa 'fuente.ttf'
            # Si falla (porque no se subió el archivo), usa Helvetica estándar
            try:
                self.add_font("MiFuente", "", "fuente.ttf")
                self.set_font("MiFuente", "", 18)
            except:
                self.set_font("Helvetica", "B", 15)
                
            self.cell(0, 10, "Informe de Rendimiento Académico", new_x="LMARGIN", new_y="NEXT", align='C')
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 8)
            self.cell(0, 10, f'Página {self.page_no()}', align='C')

    pdf = PDF()
    pdf.add_page()
    
    # Configurar fuente para el cuerpo
    try:
        pdf.add_font("MiFuente", "", "fuente.ttf")
        pdf.set_font("MiFuente", "", 12)
    except:
        pdf.set_font("Helvetica", "", 12)
    
    # DATOS DEL ALUMNO
    pdf.set_font(size=14, style="")
    pdf.cell(0, 10, f"Alumno: {alumno.nombre_completo}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(size=12)
    pdf.cell(0, 10, f"Año Escolar: {alumno.año_escolar}º Año", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    
    # TABLA DE NOTAS
    pdf.set_font(size=12, style="")
    pdf.cell(0, 10, "Historial de Evaluaciones:", new_x="LMARGIN", new_y="NEXT")
    
    # Encabezados
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font(size=10)
    pdf.cell(40, 10, "Materia", border=1, fill=True, align='C')
    pdf.cell(50, 10, "Instancia", border=1, fill=True, align='C')
    pdf.cell(20, 10, "Nota", border=1, fill=True, align='C')
    pdf.cell(80, 10, "Comentario", border=1, fill=True, align='C', new_x="LMARGIN", new_y="NEXT")
    
    # Filas
    if alumno.evaluaciones:
        for ev in alumno.evaluaciones:
            # Limpiamos saltos de linea en comentarios para que no rompan la tabla
            comentario_clean = ev.comentario.replace("\n", " ")[:50]
            
            pdf.cell(40, 10, str(ev.materia.nombre)[:25], border=1)
            pdf.cell(50, 10, str(ev.instancia)[:30], border=1)
            pdf.cell(20, 10, str(ev.nota), border=1, align='C')
            pdf.cell(80, 10, comentario_clean, border=1, new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 10, "Sin registros.", border=1, new_x="LMARGIN", new_y="NEXT")
        
    pdf.ln(10)

    # RECOMENDACIÓN IA
    pdf.set_font(size=12, style="")
    pdf.cell(0, 10, "Análisis del Asistente Virtual:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(size=11)
    # Multi_cell escribe párrafos largos ajustando el texto
    pdf.multi_cell(0, 8, recomendaciones_ia_texto)
    
    pdf.ln(10)
    pdf.set_font(size=9)
    fecha = datetime.now().strftime("%d/%m/%Y")
    pdf.cell(0, 10, f"Generado el {fecha}", new_x="LMARGIN", new_y="NEXT")

    # Retornamos los bytes del PDF
    return bytes(pdf.output())

# --- NAVEGACIÓN ---
session = get_session()
st.sidebar.title("🏫 Menú Principal")
modo = st.sidebar.radio("Ir a:", ["📊 Dashboard & Chat IA", "⚙️ Administración General"])

# ==============================================================================
# MODO 1: ADMINISTRACIÓN
# ==============================================================================
if modo == "⚙️ Administración General":
    st.title("⚙️ Panel de Control")
    tab1, tab2, tab3, tab4 = st.tabs(["📚 Materias", "👤 Alumnos", "📝 Notas", "📂 Importar"])

    with tab1: # Materias
        st.subheader("Gestión de Materias")
        c1, c2 = st.columns(2)
        with c1:
            with st.form("nueva_materia"):
                nom = st.text_input("Nombre Materia")
                prof = st.text_input("Profesor")
                if st.form_submit_button("Crear"):
                    if not session.query(Materia).filter_by(nombre=nom).first():
                        session.add(Materia(nombre=nom, profesor_titular=prof))
                        session.commit()
                        st.success("Creada.")
                        st.rerun()
                    else:
                        st.error("Ya existe.")
        with c2:
            mats = session.query(Materia).all()
            if mats:
                sel = st.selectbox("Editar Materia", [m.nombre for m in mats])
                obj = session.query(Materia).filter_by(nombre=sel).first()
                if st.button("🗑️ Eliminar Materia"):
                    if obj.evaluaciones:
                        st.error("No se puede borrar: tiene notas asociadas.")
                    else:
                        session.delete(obj)
                        session.commit()
                        st.success("Eliminada.")
                        st.rerun()

    with tab2: # Alumnos
        st.subheader("Registrar Nuevo Alumno")
        with st.form("nuevo_alumno"):
            col1, col2 = st.columns(2)
            nom = col1.text_input("Nombre Completo *")
            dni = col2.text_input("DNI *")
            
            col3, col4, col5 = st.columns(3)
            anio = col3.number_input("Año Escolar", 1, 6)
            mail = col4.text_input("Email")
            tel = col5.text_input("Teléfono")
            
            if st.form_submit_button("Guardar Alumno"):
                if nom and dni:
                    # Chequeo de seguridad: ¿Existe el DNI?
                    existe = session.query(Alumno).filter_by(dni=dni).first()
                    if existe:
                        st.error("❌ Error: Ese DNI ya está registrado.")
                    else:
                        nuevo = Alumno(
                            nombre_completo=nom, 
                            año_escolar=anio,
                            dni=dni,       # <--- Nuevo
                            email=mail,    # <--- Nuevo
                            telefono=tel   # <--- Nuevo
                        )
                        session.add(nuevo)
                        session.commit()
                        st.success("✅ Alumno guardado exitosamente.")
                else:
                    st.warning("⚠️ Nombre y DNI son obligatorios.")

    with tab3: # Notas
        try:
            alu = session.query(Alumno).all()
            mat = session.query(Materia).all()
            if alu and mat:
                with st.form("nota"):
                    ca, cm = st.columns(2)
                    a_sel = ca.selectbox("Alumno", [x.nombre_completo for x in alu])
                    m_sel = cm.selectbox("Materia", [x.nombre for x in mat])
                    inst = st.text_input("Instancia")
                    nota = st.number_input("Nota", 0.0, 10.0, step=0.5)
                    com = st.text_area("Comentario")
                    if st.form_submit_button("Guardar"):
                        obj_a = session.query(Alumno).filter_by(nombre_completo=a_sel).first()
                        obj_m = session.query(Materia).filter_by(nombre=m_sel).first()
                        session.add(Evaluacion(alumno_id=obj_a.id, materia_id=obj_m.id, instancia=inst, nota=nota, comentario=com, fecha=datetime.now()))
                        session.commit()
                        st.success("Nota guardada.")
            else:
                st.warning("Carga alumnos y materias primero.")
        except:
            st.error("Error cargando listas.")

    with tab4: # Importar
        f = st.file_uploader("Excel (Nombre, Año)", type=["xlsx", "csv"])
        if f and st.button("Importar"):
            try:
                df = pd.read_excel(f) if f.name.endswith('xlsx') else pd.read_csv(f)
                c = 0
                for _, r in df.iterrows():
                    if not session.query(Alumno).filter_by(nombre_completo=r['Nombre']).first():
                        session.add(Alumno(nombre_completo=r['Nombre'], año_escolar=int(r['Año'])))
                        c += 1
                session.commit()
                st.success(f"Importados {c}.")
            except Exception as e:
                st.error(f"Error: {e}")

# ==============================================================================
# MODO 2: DASHBOARD + CHAT
# ==============================================================================
elif modo == "📊 Dashboard & Chat IA":
    st.title("🎓 Dashboard del Alumno")
    alumnos = session.query(Alumno).all()
    if alumnos:
        seleccion = st.sidebar.selectbox("🔍 Buscar Alumno:", [a.nombre_completo for a in alumnos])
        alumno = session.query(Alumno).filter_by(nombre_completo=seleccion).first()
        
        # KPI
        notas = [e.nota for e in alumno.evaluaciones]
        prom = sum(notas)/len(notas) if notas else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("Alumno", alumno.nombre_completo)
        c2.metric("Promedio", f"{prom:.2f}")
        c3.metric("Evaluaciones", len(notas))
        st.divider()

        # BOTÓN PDF
        if st.button("📄 Descargar Informe PDF"):
            with st.spinner("Generando análisis con IA..."):
                # 1. Pedimos resumen a la IA
                resumen = responder_chat_educativo(alumno.nombre_completo, str(notas), "Escribe una conclusión formal del rendimiento para los padres (máx 50 palabras).")
                # 2. Creamos PDF
                pdf_data = crear_reporte_pdf(alumno, resumen)
                # 3. Botón descarga
                st.download_button("⬇️ Guardar PDF", data=pdf_data, file_name=f"Informe_{alumno.nombre_completo}.pdf", mime="application/pdf")

        # CONTENIDO PRINCIPAL
        col_izq, col_der = st.columns([2, 1])
        
        with col_izq:
            st.subheader("Historial")
            if alumno.evaluaciones:
                # Tabla simple
                df = pd.DataFrame([{
                    "Fecha": e.fecha, 
                    "Materia": e.materia.nombre,
                    "Nota": e.nota,
                    "Comentario": e.comentario
                } for e in alumno.evaluaciones])
                st.dataframe(df, use_container_width=True)
                st.line_chart(df.set_index("Fecha")["Nota"])
            else:
                st.info("Sin datos.")

        with col_der:
            st.subheader("💬 Chat IA")
            if "messages" not in st.session_state: st.session_state.messages = []
            
            q = st.chat_input("Pregunta sobre el alumno...")
            if q:
                with st.chat_message("user"): st.write(q)
                ctx = ""
                for e in alumno.evaluaciones: ctx += f"- {e.materia.nombre}: {e.nota} ({e.comentario})\n"
                with st.chat_message("assistant"):
                    with st.spinner("Pensando..."):
                        res = responder_chat_educativo(alumno.nombre_completo, ctx, q)
                        st.write(res)

session.close()

