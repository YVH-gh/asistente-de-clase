import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from fpdf import FPDF
from crear_base_datos import Base, Alumno, Materia, Evaluacion
from modulo_ia_github import generar_recomendacion_ia, responder_chat_educativo

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Escolar 360", layout="wide", page_icon="🎓")

# --- CONEXIÓN BASE DE DATOS ---
try:
    # Intenta leer Secrets (Nube)
    database_url = st.secrets["DATABASE_URL"]
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(database_url, pool_pre_ping=True)
except:
    # Fallback Local
    ruta_db = 'sistema_escolar.db'
    engine = create_engine(f'sqlite:///{ruta_db}')

Session = sessionmaker(bind=engine)

# Auto-creación de tablas si no existen
try:
    Base.metadata.create_all(engine)
except Exception as e:
    st.error(f"Error conectando a DB: {e}")

def get_session():
    return Session()

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .stChatMessage {background-color: #f0f2f6; border-radius: 10px;}
    .metric-card {background-color: #f0f2f6; padding: 15px; border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

# --- 1. LOGIN DE SEGURIDAD ---
def check_password():
    if "PASSWORD_ACCESO" not in st.secrets:
        return True 

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

# --- 2. FUNCIÓN PDF ---
def crear_reporte_pdf(alumno, recomendaciones_ia_texto):
    class PDF(FPDF):
        def header(self):
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
    
    try:
        pdf.add_font("MiFuente", "", "fuente.ttf")
        pdf.set_font("MiFuente", "", 12)
    except:
        pdf.set_font("Helvetica", "", 12)
    
    # DATOS
    pdf.set_font(size=14, style="")
    pdf.cell(0, 10, f"Alumno: {alumno.nombre_completo}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(size=12)
    pdf.cell(0, 10, f"Año Escolar: {alumno.año_escolar}º Año", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    
    # TABLA
    pdf.set_font(size=12, style="")
    pdf.cell(0, 10, "Historial de Evaluaciones:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font(size=10)
    pdf.cell(40, 10, "Materia", border=1, fill=True, align='C')
    pdf.cell(50, 10, "Instancia", border=1, fill=True, align='C')
    pdf.cell(20, 10, "Nota", border=1, fill=True, align='C')
    pdf.cell(80, 10, "Comentario", border=1, fill=True, align='C', new_x="LMARGIN", new_y="NEXT")
    
    if alumno.evaluaciones:
        for ev in alumno.evaluaciones:
            comentario_clean = ev.comentario.replace("\n", " ")[:50]
            pdf.cell(40, 10, str(ev.materia.nombre)[:25], border=1)
            pdf.cell(50, 10, str(ev.instancia)[:30], border=1)
            pdf.cell(20, 10, str(ev.nota), border=1, align='C')
            pdf.cell(80, 10, comentario_clean, border=1, new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 10, "Sin registros.", border=1, new_x="LMARGIN", new_y="NEXT")
        
    pdf.ln(10)

    # IA
    pdf.set_font(size=12, style="")
    pdf.cell(0, 10, "Análisis del Asistente Virtual:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(size=11)
    pdf.multi_cell(0, 8, recomendaciones_ia_texto)
    pdf.ln(10)
    
    fecha = datetime.now().strftime("%d/%m/%Y")
    pdf.set_font(size=9)
    pdf.cell(0, 10, f"Generado el {fecha}", new_x="LMARGIN", new_y="NEXT")

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

    with tab1: # MATERIAS
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
                        st.error("Tiene notas asociadas. No se puede borrar.")
                    else:
                        session.delete(obj)
                        session.commit()
                        st.success("Eliminada.")
                        st.rerun()

    with tab2: # ALUMNOS (Con borrado y exportación)
        st.subheader("Gestión de Alumnos")
        
        # Exportación
        alumnos_todos = session.query(Alumno).all()
        if alumnos_todos:
            data_export = [{
                "Nombre": a.nombre_completo,
                "Año": a.año_escolar,
                "DNI": a.dni,
                "Email": a.email,
                "Teléfono": a.telefono
            } for a in alumnos_todos]
            csv = pd.DataFrame(data_export).to_csv(index=False).encode('utf-8')
            col_exp1, col_exp2 = st.columns([3, 1])
            with col_exp2:
                st.download_button("⬇️ Lista CSV", data=csv, file_name="Alumnos.csv", mime="text/csv")
        st.divider()

        # Formulario Carga
        st.subheader("Registrar Nuevo Alumno")
        with st.form("nuevo_alumno"):
            c1, c2 = st.columns(2)
            nom = c1.text_input("Nombre Completo *")
            dni = c2.text_input("DNI *")
            c3, c4, c5 = st.columns(3)
            anio = c3.number_input("Año", 1, 6)
            mail = c4.text_input("Email")
            tel = c5.text_input("Teléfono")
            
            if st.form_submit_button("Guardar"):
                if nom and dni:
                    try:
                        if session.query(Alumno).filter_by(dni=dni).first():
                            st.error("DNI ya registrado.")
                        else:
                            session.add(Alumno(nombre_completo=nom, año_escolar=anio, dni=dni, email=mail, telefono=tel))
                            session.commit()
                            st.success("Guardado.")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error DB: {e}")
                else:
                    st.warning("Datos obligatorios faltantes.")
        
        st.divider()
        
        # Borrado
        st.subheader("🗑️ Zona de Peligro")
        with st.expander("Opciones de Eliminación"):
            metodo = st.radio("Método:", ["Uno a Uno", "Por Año"])
            if metodo == "Uno a Uno":
                if alumnos_todos:
                    a_del = st.selectbox("Eliminar a:", [a.nombre_completo for a in alumnos_todos])
                    if st.button(f"Borrar a {a_del}"):
                        obj = session.query(Alumno).filter_by(nombre_completo=a_del).first()
                        for ev in obj.evaluaciones: session.delete(ev)
                        session.delete(obj)
                        session.commit()
                        st.success("Eliminado.")
                        st.rerun()

    with tab3: # NOTAS (Con formulario limpio)
        try:
            alu = session.query(Alumno).all()
            mat = session.query(Materia).all()
            if alu and mat:
                st.subheader("Cargar Calificación")
                c_sel_a, c_sel_m = st.columns(2)
                a_sel = c_sel_a.selectbox("Alumno", [x.nombre_completo for x in alu])
                m_sel = c_sel_m.selectbox("Materia", [x.nombre for x in mat])
                
                st.divider()
                
                with st.form("nota_form", clear_on_submit=True):
                    st.write(f"Nota para: **{a_sel}** en **{m_sel}**")
                    inst = st.text_input("Instancia")
                    nota = st.number_input("Nota", 0.0, 10.0, step=0.5)
                    com = st.text_area("Comentario")
                    
                    if st.form_submit_button("Guardar Nota"):
                        obj_a = session.query(Alumno).filter_by(nombre_completo=a_sel).first()
                        obj_m = session.query(Materia).filter_by(nombre=m_sel).first()
                        session.add(Evaluacion(alumno_id=obj_a.id, materia_id=obj_m.id, instancia=inst, nota=nota, comentario=com, fecha=datetime.now()))
                        session.commit()
                        st.toast(f"✅ Nota guardada para {a_sel}!")
            else:
                st.warning("Carga alumnos y materias primero.")
        except:
            st.error("Error cargando listas.")

    with tab4: # IMPORTAR
        f = st.file_uploader("Excel", type=["xlsx", "csv"])
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
# MODO 2: DASHBOARD + CHAT IA (Esto era lo que faltaba o estaba roto)
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
                resumen = responder_chat_educativo(alumno.nombre_completo, str(notas), "Escribe una conclusión formal del rendimiento para los padres (máx 50 palabras).")
                pdf_data = crear_reporte_pdf(alumno, resumen)
                st.download_button("⬇️ Guardar PDF", data=pdf_data, file_name=f"Informe_{alumno.nombre_completo}.pdf", mime="application/pdf")

        # CONTENIDO VISUAL
        col_izq, col_der = st.columns([2, 1])
        
        with col_izq:
            st.subheader("Historial Académico")
            if alumno.evaluaciones:
                df = pd.DataFrame([{
                    "Fecha": e.fecha, 
                    "Materia": e.materia.nombre,
                    "Instancia": e.instancia,
                    "Nota": e.nota,
                    "Comentario": e.comentario
                } for e in alumno.evaluaciones])
                st.dataframe(df, use_container_width=True)
                st.line_chart(df.set_index("Fecha")["Nota"])
            else:
                st.info("No hay notas cargadas para este alumno.")

        with col_der:
            st.subheader("💬 Chat IA")
            st.caption(f"Pregunta sobre {alumno.nombre_completo}")
            
            if "messages" not in st.session_state: st.session_state.messages = []
            
            q = st.chat_input("Ej: ¿En qué materia necesita ayuda?")
            if q:
                with st.chat_message("user"): st.write(q)
                
                # Construimos contexto
                ctx = ""
                for e in alumno.evaluaciones: 
                    ctx += f"- {e.materia.nombre}: {e.nota} ({e.comentario})\n"
                
                if not ctx: ctx = "El alumno no tiene notas aún."

                with st.chat_message("assistant"):
                    with st.spinner("Analizando..."):
                        res = responder_chat_educativo(alumno.nombre_completo, ctx, q)
                        st.write(res)
    else:
        st.warning("La base de datos de alumnos está vacía. Ve a Administración para cargar el primero.")

session.close()
