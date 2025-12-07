import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from fpdf import FPDF
# Importamos Base para auto-creación y las clases actualizadas
from crear_base_datos import Base, Alumno, Materia, Evaluacion
from modulo_ia_github import generar_recomendacion_ia, responder_chat_educativo

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Escolar AI", layout="wide", page_icon="🧠")

# --- CONEXIÓN DB (SUPABASE + LOCAL) ---
try:
    database_url = st.secrets["DATABASE_URL"]
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(database_url, pool_pre_ping=True)
except:
    ruta_db = 'sistema_escolar.db'
    engine = create_engine(f'sqlite:///{ruta_db}')

Session = sessionmaker(bind=engine)
# Auto-creación de tablas (por si borraste todo en Supabase o es nuevo)
try: Base.metadata.create_all(engine)
except: pass

def get_session(): return Session()

# --- CSS PERSONALIZADO ---
st.markdown("""<style>.stChatMessage {background-color: #f0f2f6; border-radius: 10px;}</style>""", unsafe_allow_html=True)

# --- 1. SEGURIDAD (LOGIN) ---
def check_password():
    if "PASSWORD_ACCESO" not in st.secrets: return True 
    if "password_correcta" not in st.session_state: st.session_state.password_correcta = False
    if not st.session_state.password_correcta:
        st.text_input("🔑 Contraseña", type="password", on_change=password_entered, key="password_input")
        return False
    return True

def password_entered():
    if st.session_state["password_input"] == st.secrets["PASSWORD_ACCESO"]:
        st.session_state.password_correcta = True
        del st.session_state["password_input"]
    else: st.error("❌ Incorrecta")

if not check_password(): st.stop()

# --- 2. GENERADOR PDF ---
def crear_reporte_pdf(alumno, recomendaciones_ia_texto):
    class PDF(FPDF):
        def header(self):
            try:
                self.add_font("MiFuente", "", "fuente.ttf")
                self.set_font("MiFuente", "", 18)
            except: self.set_font("Helvetica", "B", 15)
            self.cell(0, 10, "Informe Académico", new_x="LMARGIN", new_y="NEXT", align='C'); self.ln(10)
        def footer(self):
            self.set_y(-15); self.set_font("Helvetica", "I", 8); self.cell(0, 10, f'Pag {self.page_no()}', align='C')

    pdf = PDF(); pdf.add_page()
    try: pdf.add_font("MiFuente", "", "fuente.ttf"); pdf.set_font("MiFuente", "", 12)
    except: pdf.set_font("Helvetica", "", 12)
    
    pdf.set_font(size=14, style=""); pdf.cell(0, 10, f"Alumno: {alumno.nombre_completo}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(size=12); pdf.cell(0, 10, f"Año: {alumno.año_escolar}º", new_x="LMARGIN", new_y="NEXT"); pdf.ln(5)
    
    pdf.cell(0, 10, "Historial:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_fill_color(240, 240, 240); pdf.set_font(size=10)
    pdf.cell(40, 10, "Materia", 1, 0, 'C', 1); pdf.cell(40, 10, "Instancia", 1, 0, 'C', 1); pdf.cell(20, 10, "Nota", 1, 0, 'C', 1); pdf.cell(90, 10, "Comentario", 1, 1, 'C', 1)
    
    if alumno.evaluaciones:
        for ev in alumno.evaluaciones:
            pdf.cell(40, 10, str(ev.materia.nombre)[:20], 1); pdf.cell(40, 10, str(ev.instancia)[:20], 1)
            pdf.cell(20, 10, str(ev.nota), 1, 0, 'C'); pdf.cell(90, 10, ev.comentario.replace("\n"," ")[:50], 1, 1)
    else: pdf.cell(0, 10, "Sin datos.", 1, 1)
    
    pdf.ln(10); pdf.set_font(size=12); pdf.cell(0, 10, "Análisis IA:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(size=11); pdf.multi_cell(0, 8, recomendaciones_ia_texto)
    return bytes(pdf.output())

# --- NAVEGACIÓN ---
session = get_session()
st.sidebar.title("🏫 Menú Escolar")
modo = st.sidebar.radio("Ir a:", ["📊 Dashboard & Chat IA", "⚙️ Administración"])

# ==============================================================================
# MODO ADMINISTRACIÓN (CRUD COMPLETO)
# ==============================================================================
if modo == "⚙️ Administración":
    st.title("⚙️ Panel de Control")
    tab1, tab2, tab3, tab4 = st.tabs(["📚 Materias (Conocimiento)", "👤 Alumnos (ABM)", "📝 Cargar Notas", "📂 Importar"])

    # --- TAB 1: MATERIAS + PROGRAMA (Knowledge Base) ---
    with tab1:
        st.subheader("Gestión de Materias y Bibliografía")
        c1, c2 = st.columns(2)
        
        # Selector para Editar o Crear
        materias_existentes = session.query(Materia).all()
        nombres_mat = ["➕ Nueva Materia..."] + [m.nombre for m in materias_existentes]
        seleccion_mat = c1.selectbox("Seleccionar acción:", nombres_mat)
        
        with st.form("form_materia"):
            # Lógica para pre-llenar datos si es edición
            if seleccion_mat == "➕ Nueva Materia...":
                nombre_val, prof_val, prog_val = "", "", ""
            else:
                obj_m = session.query(Materia).filter_by(nombre=seleccion_mat).first()
                nombre_val, prof_val = obj_m.nombre, obj_m.profesor_titular
                prog_val = obj_m.programa if obj_m.programa else ""

            nom = st.text_input("Nombre Materia", value=nombre_val)
            prof = st.text_input("Profesor Titular", value=prof_val)
            
            # EL CEREBRO: Campo para el programa
            st.caption("🧠 **Base de Conocimiento para la IA:**")
            prog = st.text_area("Programa / Bibliografía / Temas Clave", value=prog_val, height=150, 
                                placeholder="Ej: Unidad 1: Revolución Francesa. Libro recomendado: Hobsbawm.")
            
            if st.form_submit_button("💾 Guardar Cambios"):
                if seleccion_mat == "➕ Nueva Materia...":
                    if not session.query(Materia).filter_by(nombre=nom).first():
                        session.add(Materia(nombre=nom, profesor_titular=prof, programa=prog))
                        session.commit(); st.success("Materia Creada!"); st.rerun()
                    else: st.error("Ya existe.")
                else:
                    obj_m.nombre = nom; obj_m.profesor_titular = prof; obj_m.programa = prog
                    session.commit(); st.success("Materia Actualizada!"); st.rerun()

    # --- TAB 2: ALUMNOS (INCLUYE ELIMINAR) ---
    with tab2: 
        st.subheader("Gestión de Alumnos")
        
        # 1. Exportación CSV
        todos = session.query(Alumno).all()
        if todos:
            csv = pd.DataFrame([{"Nombre":a.nombre_completo, "DNI":a.dni, "Año":a.año_escolar} for a in todos]).to_csv(index=False).encode('utf-8')
            col_exp1, col_exp2 = st.columns([3,1])
            col_exp2.download_button("⬇️ Descargar CSV", csv, "alumnos.csv", "text/csv")
        
        st.divider()

        # 2. Formulario de Carga
        st.write("➕ **Registrar Nuevo Alumno**")
        with st.form("new_alu"):
            c1, c2 = st.columns(2)
            n = c1.text_input("Nombre *"); d = c2.text_input("DNI *")
            c3, c4, c5 = st.columns(3)
            a = c3.number_input("Año", 1, 6); m = c4.text_input("Email"); t = c5.text_input("Tel")
            
            if st.form_submit_button("Guardar"):
                if n and d:
                    try:
                        if not session.query(Alumno).filter_by(dni=d).first():
                            session.add(Alumno(nombre_completo=n, dni=d, año_escolar=a, email=m, telefono=t))
                            session.commit(); st.success("Guardado!"); st.rerun()
                        else: st.error("El DNI ya existe.")
                    except Exception as e: st.error(f"Error: {e}")
                else: st.warning("Nombre y DNI obligatorios.")

        st.divider()

        # 3. ZONA DE PELIGRO (ELIMINAR)
        st.subheader("🗑️ Eliminar Alumnos")
        with st.expander("⚠️ Abrir opciones de borrado"):
            if todos:
                a_del = st.selectbox("Eliminar a:", [x.nombre_completo for x in todos])
                if st.button(f"Borrar Definitivamente a {a_del}"):
                    obj = session.query(Alumno).filter_by(nombre_completo=a_del).first()
                    # Borrado en cascada manual (primero notas, luego alumno)
                    for e in obj.evaluaciones: session.delete(e)
                    session.delete(obj); session.commit(); st.success("Eliminado."); st.rerun()

    # --- TAB 3: CARGA DE NOTAS (LIMPIEZA AUTOMÁTICA) ---
    with tab3: 
        try:
            ls_a = session.query(Alumno).all()
            ls_m = session.query(Materia).all()
            if ls_a and ls_m:
                st.subheader("Cargar Calificación")
                c1, c2 = st.columns(2)
                # Selectores FUERA del form para no resetearse
                sa = c1.selectbox("Alumno", [x.nombre_completo for x in ls_a])
                sm = c2.selectbox("Materia", [x.nombre for x in ls_m])
                st.divider()
                
                with st.form("f_nota", clear_on_submit=True):
                    st.write(f"Nota para **{sa}** en **{sm}**")
                    ins = st.text_input("Instancia (ej: Parcial 1)")
                    nt = st.number_input("Nota", 0.0, 10.0, step=0.5)
                    cm = st.text_area("Comentario")
                    if st.form_submit_button("Guardar Nota"):
                        oa = session.query(Alumno).filter_by(nombre_completo=sa).first()
                        om = session.query(Materia).filter_by(nombre=sm).first()
                        session.add(Evaluacion(alumno_id=oa.id, materia_id=om.id, instancia=ins, nota=nt, comentario=cm, fecha=datetime.now()))
                        session.commit(); st.toast("✅ Nota Guardada!")
            else: st.warning("Carga alumnos y materias primero.")
        except: st.error("Error cargando listas.")

    # --- TAB 4: IMPORTAR ---
    with tab4: 
        f = st.file_uploader("Excel/CSV (Nombre, Año)", type=["xlsx", "csv"])
        if f and st.button("Importar"):
            try:
                df = pd.read_excel(f) if f.name.endswith('xlsx') else pd.read_csv(f)
                c=0
                for _,r in df.iterrows():
                    if not session.query(Alumno).filter_by(nombre_completo=r['Nombre']).first():
                        session.add(Alumno(nombre_completo=r['Nombre'], año_escolar=int(r['Año'])))
                        c+=1
                session.commit(); st.success(f"Importados: {c}")
            except Exception as e: st.error(str(e))

# ==============================================================================
# MODO DASHBOARD + CHAT IA (RAG)
# ==============================================================================
elif modo == "📊 Dashboard & Chat IA":
    st.title("🎓 Dashboard Inteligente")
    als = session.query(Alumno).all()
    if als:
        sel = st.sidebar.selectbox("Alumno:", [a.nombre_completo for a in als])
        alu = session.query(Alumno).filter_by(nombre_completo=sel).first()
        
        # KPI
        nts = [e.nota for e in alu.evaluaciones]
        p = sum(nts)/len(nts) if nts else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("Alumno", alu.nombre_completo); c2.metric("Promedio", f"{p:.2f}"); c3.metric("Notas", len(nts))
        st.divider()

        # PDF REPORT
        if st.button("📄 Informe PDF"):
            with st.spinner("IA redactando..."):
                res = responder_chat_educativo(alu.nombre_completo, str(nts), "Conclusión formal para padres (50 palabras).")
                pdf = crear_reporte_pdf(alu, res)
                st.download_button("⬇️ PDF", pdf, f"Reporte_{alu.nombre_completo}.pdf", "application/pdf")

        # GRÁFICOS
        c_izq, c_der = st.columns([2, 1])
        with c_izq:
            if alu.evaluaciones:
                df = pd.DataFrame([{"Fecha":e.fecha, "Materia":e.materia.nombre, "Nota":e.nota, "Comentario":e.comentario} for e in alu.evaluaciones])
                st.dataframe(df, use_container_width=True); st.line_chart(df.set_index("Fecha")["Nota"])
            else: st.info("Sin notas.")

        # CHAT CONTEXTUAL (RAG)
        with c_der:
            st.subheader("💬 Chat Contextual")
            if "messages" not in st.session_state: st.session_state.messages = []
            
            q = st.chat_input("Pregunta...")
            if q:
                with st.chat_message("user"): st.write(q)
                
                # --- CONSTRUCCIÓN DEL CONTEXTO (AQUÍ ESTÁ LA MAGIA) ---
                ctx_notas = ""
                ctx_programas = ""
                materias_vistas = set()

                for e in alu.evaluaciones:
                    ctx_notas += f"- {e.materia.nombre}: {e.nota} ({e.comentario})\n"
                    # Si la materia tiene programa y no lo hemos añadido aún al contexto
                    if e.materia.nombre not in materias_vistas and e.materia.programa:
                        ctx_programas += f"\n📚 DATOS DE {e.materia.nombre}:\n{e.materia.programa}\n---"
                        materias_vistas.add(e.materia.nombre)
                
                contexto_total = f"CALIFICACIONES:\n{ctx_notas}\n\nBIBLIOGRAFÍA Y PROGRAMAS:\n{ctx_programas}"
                if not ctx_notas: contexto_total = "El alumno no tiene notas."

                with st.chat_message("assistant"):
                    with st.spinner("Analizando..."):
                        res = responder_chat_educativo(alu.nombre_completo, contexto_total, q)
                        st.write(res)
    else:
        st.warning("Base de datos vacía. Cargue alumnos en Administración.")

session.close()
