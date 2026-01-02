import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from fpdf import FPDF
from crear_base_datos import Base, Alumno, Materia, Evaluacion
from modulo_ia_github import generar_recomendacion_ia, responder_chat_educativo

# --- 1. CONFIGURACIÓN DE PÁGINA (PRIMERA LÍNEA OBLIGATORIA) ---
st.set_page_config(page_title="Sistema Escolar AI", layout="wide", page_icon="🧠")

# --- 2. CONTROL DE LIBRERÍA PDF ---
try:
    from pypdf import PdfReader
except ImportError:
    st.error("⚠️ ERROR CRÍTICO: Falta la librería 'pypdf'. Agrégala a requirements.txt")
    st.stop()

# --- 3. CONEXIÓN A BASE DE DATOS (SUPABASE / LOCAL) ---
try:
    if "DATABASE_URL" in st.secrets:
        database_url = st.secrets["DATABASE_URL"]
        # Parche de compatibilidad para Supabase
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        # Forzamos SSL y Pre-ping para evitar desconexiones
        engine = create_engine(database_url, pool_pre_ping=True, connect_args={"sslmode": "require"})
    else:
        # Modo Local (Fallback)
        ruta_db = 'sistema_escolar.db'
        engine = create_engine(f'sqlite:///{ruta_db}')
except Exception as e:
    st.error(f"❌ Error de Conexión DB: {e}")
    st.stop()

Session = sessionmaker(bind=engine)
try: Base.metadata.create_all(engine)
except: pass

def get_session(): return Session()

# --- ESTILOS VISUALES ---
st.markdown("""<style>.stChatMessage {background-color: #f0f2f6; border-radius: 10px;}</style>""", unsafe_allow_html=True)

# --- 4. SISTEMA DE LOGIN ---
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
    else: st.error("❌ Contraseña Incorrecta")

if not check_password(): st.stop()

# --- 5. GENERADOR DE PDF ---
def crear_reporte_pdf(alumno, recomendaciones_ia_texto):
    class PDF(FPDF):
        def header(self):
            try: self.add_font("MiFuente", "", "fuente.ttf"); self.set_font("MiFuente", "", 18)
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

# --- 6. NAVEGACIÓN ROBUSTA ---
session = get_session()
st.sidebar.title("🏫 Menú Escolar")
# Usamos strings simples para evitar errores de emojis
modo = st.sidebar.radio("Ir a:", ["📊 Dashboard & Chat IA", "⚙️ Administración"])

# ==============================================================================
# MODO ADMINISTRACIÓN
# ==============================================================================
if "Administración" in modo:
    st.title("⚙️ Panel de Control")
    tab1, tab2, tab3, tab4 = st.tabs(["📚 Materias (Docs)", "👤 Alumnos", "📝 Notas", "📂 Importar"])

    # TAB 1: MATERIAS + PDF
    with tab1:
        st.subheader("Gestión de Materias")
        c1, c2 = st.columns(2)
        materias = session.query(Materia).all()
        opciones = ["➕ Nueva Materia..."] + [m.nombre for m in materias]
        seleccion = c1.selectbox("Acción:", opciones)
        
        # Pre-carga de datos
        nombre_ini, prof_ini, prog_ini = "", "", ""
        obj_m = None
        if seleccion != "➕ Nueva Materia...":
            obj_m = session.query(Materia).filter_by(nombre=seleccion).first()
            if obj_m:
                nombre_ini = obj_m.nombre
                prof_ini = obj_m.profesor_titular
                prog_ini = obj_m.programa if obj_m.programa else ""

        with st.form("frm_materia"):
            nom = st.text_input("Nombre", value=nombre_ini)
            prof = st.text_input("Profesor", value=prof_ini)
            st.divider()
            st.markdown("📚 **Base de Conocimiento (RAG)**")
            
            # Carga de PDFs
            pdfs = st.file_uploader("Subir PDFs (Planificación, Libros)", type=["pdf"], accept_multiple_files=True)
            texto_nuevo = ""
            if pdfs:
                for p in pdfs:
                    try:
                        reader = PdfReader(p)
                        t = ""
                        for page in reader.pages: t += page.extract_text() + "\n"
                        texto_nuevo += f"\n--- DOC: {p.name} ---\n{t}\n"
                        st.success(f"✅ Leído: {p.name}")
                    except: st.error(f"Error en {p.name}")

            contenido = st.text_area("Contenido IA (Editable):", value=prog_ini + texto_nuevo, height=200)
            
            if st.form_submit_button("💾 Guardar"):
                if seleccion == "➕ Nueva Materia...":
                    if not session.query(Materia).filter_by(nombre=nom).first():
                        session.add(Materia(nombre=nom, profesor_titular=prof, programa=contenido))
                        session.commit(); st.success("Creada!"); st.rerun()
                    else: st.error("Ya existe.")
                else:
                    if obj_m:
                        obj_m.nombre = nom; obj_m.profesor_titular = prof; obj_m.programa = contenido
                        session.commit(); st.success("Actualizada!"); st.rerun()

    # TAB 2: ALUMNOS
    with tab2:
        st.subheader("Alumnos")
        todos = session.query(Alumno).all()
        if todos:
            df = pd.DataFrame([{"Nombre":a.nombre_completo, "DNI":a.dni, "Año":a.año_escolar} for a in todos])
            st.download_button("⬇️ CSV", df.to_csv(index=False).encode('utf-8'), "alumnos.csv")
        
        with st.form("frm_alu"):
            c1, c2 = st.columns(2)
            n = c1.text_input("Nombre *"); d = c2.text_input("DNI *")
            c3, c4, c5 = st.columns(3)
            a = c3.number_input("Año", 1, 6); m = c4.text_input("Email"); t = c5.text_input("Tel")
            if st.form_submit_button("Guardar"):
                if n and d:
                    try:
                        if not session.query(Alumno).filter_by(dni=d).first():
                            session.add(Alumno(nombre_completo=n, dni=d, año_escolar=a, email=m, telefono=t))
                            session.commit(); st.success("Listo!"); st.rerun()
                        else: st.error("DNI duplicado")
                    except Exception as e: st.error(str(e))

        with st.expander("🗑️ Borrar"):
            if todos:
                del_a = st.selectbox("Borrar a:", [x.nombre_completo for x in todos])
                if st.button("Confirmar Borrado"):
                    obj = session.query(Alumno).filter_by(nombre_completo=del_a).first()
                    for e in obj.evaluaciones: session.delete(e)
                    session.delete(obj); session.commit(); st.success("Borrado"); st.rerun()

    # TAB 3: NOTAS
    with tab3:
        ls_a = session.query(Alumno).all(); ls_m = session.query(Materia).all()
        if ls_a and ls_m:
            c1, c2 = st.columns(2)
            sa = c1.selectbox("Alumno", [x.nombre_completo for x in ls_a])
            sm = c2.selectbox("Materia", [x.nombre for x in ls_m])
            st.divider()
            with st.form("frm_nota", clear_on_submit=True):
                st.write(f"Nota: **{sa}** - **{sm}**")
                ins = st.text_input("Instancia")
                nt = st.number_input("Nota", 0.0, 10.0, step=0.5)
                cm = st.text_area("Comentario")
                if st.form_submit_button("Guardar"):
                    oa = session.query(Alumno).filter_by(nombre_completo=sa).first()
                    om = session.query(Materia).filter_by(nombre=sm).first()
                    session.add(Evaluacion(alumno_id=oa.id, materia_id=om.id, instancia=ins, nota=nt, comentario=cm, fecha=datetime.now()))
                    session.commit(); st.toast("Guardado!")
        else: st.warning("Faltan alumnos o materias.")

    # TAB 4: IMPORTAR
    with tab4:
        f = st.file_uploader("Excel/CSV", type=["xlsx", "csv"])
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
# MODO DASHBOARD (SOLUCIÓN PANTALLA BLANCA)
# ==============================================================================
elif "Dashboard" in modo:
    try:
        st.title("🎓 Dashboard Inteligente")
        
        # 1. Recuperar alumnos
        als = session.query(Alumno).all()
        
        if not als:
            st.warning("⚠️ No hay alumnos cargados. Ve a Administración para comenzar.")
        else:
            sel = st.sidebar.selectbox("Seleccionar Alumno:", [a.nombre_completo for a in als])
            alu = session.query(Alumno).filter_by(nombre_completo=sel).first()
            
            if alu:
                # KPI
                nts = [e.nota for e in alu.evaluaciones]
                p = sum(nts)/len(nts) if nts else 0
                c1, c2, c3 = st.columns(3)
                c1.metric("Alumno", alu.nombre_completo)
                c2.metric("Promedio", f"{p:.2f}")
                c3.metric("Evaluaciones", len(nts))
                st.divider()

                # PDF Report
                if st.button("📄 Generar PDF"):
                    with st.spinner("IA analizando..."):
                        res = responder_chat_educativo(alu.nombre_completo, str(nts), "Resumen breve.")
                        pdf_bytes = crear_reporte_pdf(alu, res)
                        st.download_button("⬇️ Descargar PDF", pdf_bytes, f"Reporte_{alu.nombre_completo}.pdf", "application/pdf")

                # Contenido Visual
                col_izq, col_der = st.columns([2, 1])
                
                with col_izq:
                    st.subheader("Historial Académico")
                    if alu.evaluaciones:
                        data_notas = [{"Fecha":e.fecha, "Materia":e.materia.nombre, "Nota":e.nota, "Comentario":e.comentario} for e in alu.evaluaciones]
                        df_n = pd.DataFrame(data_notas)
                        st.dataframe(df_n, use_container_width=True)
                        st.line_chart(df_n.set_index("Fecha")["Nota"])
                    else:
                        st.info("Este alumno no tiene notas registradas.")

                # CHAT CONTEXTUAL (RAG)
                with col_der:
                    st.subheader("💬 Chat IA")
                    if "messages" not in st.session_state: st.session_state.messages = []
                    
                    q = st.chat_input("Pregunta sobre el alumno...")
                    if q:
                        with st.chat_message("user"): st.write(q)
                        
                        # Construcción Contexto (Protegido contra nulos)
                        ctx_notas = ""
                        ctx_docs = ""
                        vistos = set()

                        for e in alu.evaluaciones:
                            ctx_notas += f"- {e.materia.nombre}: {e.nota} ({e.comentario})\n"
                            
                            # Lógica segura para leer programa
                            if e.materia.nombre not in vistos:
                                prog_texto = e.materia.programa if e.materia.programa else "Sin documentos."
                                # Limitamos caracteres para no romper la IA
                                ctx_docs += f"\n📚 {e.materia.nombre}:\n{prog_texto[:3000]}\n---"
                                vistos.add(e.materia.nombre)
                        
                        prompt_final = f"NOTAS:\n{ctx_notas}\n\nDOCUMENTOS:\n{ctx_docs}"
                        if not ctx_notas: prompt_final = "El alumno no tiene historial."

                        with st.chat_message("assistant"):
                            with st.spinner("Consultando base de conocimiento..."):
                                try:
                                    res_ia = responder_chat_educativo(alu.nombre_completo, prompt_final, q)
                                    st.write(res_ia)
                                except Exception as e_ia:
                                    st.error(f"Error IA: {e_ia}")
            else:
                st.error("Error al cargar datos del alumno.")

    except Exception as e_dash:
        # AQUÍ ESTÁ LA SOLUCIÓN A LA PANTALLA BLANCA
        # Si algo falla, te mostrará el error en rojo en lugar de blanco
        st.error(f"💥 Error cargando el Dashboard: {e_dash}")
        st.write("Intenta recargar la página.")

session.close()
