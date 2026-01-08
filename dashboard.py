import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from fpdf import FPDF
# Importamos PyPDF
try:
    from pypdf import PdfReader
except ImportError:
    st.error("⚠️ Falta librería 'pypdf' en requirements.txt"); st.stop()

from crear_base_datos import Base, Alumno, Materia, Evaluacion
from modulo_ia_github import generar_recomendacion_ia, responder_chat_educativo

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sistema Escolar AI", layout="wide", page_icon="🧠")

# --- CONEXIÓN DB ---
try:
    if "DATABASE_URL" in st.secrets:
        database_url = st.secrets["DATABASE_URL"]
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        engine = create_engine(database_url, pool_pre_ping=True, connect_args={"sslmode": "require"})
    else:
        ruta_db = 'sistema_escolar.db'
        engine = create_engine(f'sqlite:///{ruta_db}')
except Exception as e:
    st.error(f"Error DB: {e}"); st.stop()

Session = sessionmaker(bind=engine)
try: Base.metadata.create_all(engine)
except: pass

def get_session(): return Session()

# --- CSS ---
st.markdown("""<style>.stChatMessage {background-color: #f0f2f6; border-radius: 10px;}</style>""", unsafe_allow_html=True)

# --- LOGIN ---
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

# --- PDF GENERATOR ---
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

# --- NAVEGACIÓN ---
session = get_session()
st.sidebar.title("🏫 Menú Escolar")
modo = st.sidebar.radio("Ir a:", ["📊 Dashboard & Chat IA", "⚙️ Administración"])

# ==============================================================================
# MODO ADMINISTRACIÓN
# ==============================================================================
if "Administración" in modo:
    st.title("⚙️ Panel de Control")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📚 Materias", "👤 Alumnos", "📝 Notas Manuales", "📂 Importar Listas", "🧪 Corrección Masiva"])

    # TAB 1: MATERIAS (RAG)
    with tab1:
        st.subheader("Gestión de Materias y Documentos")
        c1, c2 = st.columns(2)
        materias = session.query(Materia).all()
        opciones = ["➕ Nueva Materia..."] + [m.nombre for m in materias]
        seleccion = c1.selectbox("Acción:", opciones)
        
        nombre_ini, prof_ini, prog_ini = "", "", ""
        obj_m = None
        if seleccion != "➕ Nueva Materia...":
            obj_m = session.query(Materia).filter_by(nombre=seleccion).first()
            if obj_m:
                nombre_ini = obj_m.nombre; prof_ini = obj_m.profesor_titular
                prog_ini = obj_m.programa if obj_m.programa else ""

        with st.form("frm_materia"):
            nom = st.text_input("Nombre", value=nombre_ini)
            prof = st.text_input("Profesor", value=prof_ini)
            st.divider()
            st.markdown("📚 **Base de Conocimiento (RAG)**")
            pdfs = st.file_uploader("Subir PDFs", type=["pdf"], accept_multiple_files=True)
            texto_nuevo = ""
            if pdfs:
                for p in pdfs:
                    try:
                        reader = PdfReader(p); t = ""
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
            df = pd.DataFrame([{"Nombre":a.nombre_completo, "DNI":a.dni} for a in todos])
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

    # TAB 3: NOTAS MANUALES
    with tab3:
        ls_a = session.query(Alumno).all(); ls_m = session.query(Materia).all()
        if ls_a and ls_m:
            c1, c2 = st.columns(2)
            sa = c1.selectbox("Alumno", [x.nombre_completo for x in ls_a])
            sm = c2.selectbox("Materia", [x.nombre for x in ls_m])
            st.divider()
            with st.form("frm_nota", clear_on_submit=True):
                st.write(f"Nota: **{sa}** - **{sm}**")
                ins = st.text_input("Instancia (ej: Oral)")
                nt = st.number_input("Nota", 0.0, 10.0, step=0.5)
                cm = st.text_area("Comentario")
                if st.form_submit_button("Guardar"):
                    oa = session.query(Alumno).filter_by(nombre_completo=sa).first()
                    om = session.query(Materia).filter_by(nombre=sm).first()
                    session.add(Evaluacion(alumno_id=oa.id, materia_id=om.id, instancia=ins, nota=nt, comentario=cm, fecha=datetime.now()))
                    session.commit(); st.toast("Guardado!")
        else: st.warning("Faltan alumnos o materias.")

    # TAB 4: IMPORTAR ALUMNOS
    with tab4:
        f = st.file_uploader("Lista Alumnos (Excel/CSV)", type=["xlsx", "csv"])
        if f and st.button("Importar Lista"):
            try:
                df = pd.read_excel(f) if f.name.endswith('xlsx') else pd.read_csv(f)
                c=0
                for _,r in df.iterrows():
                    if not session.query(Alumno).filter_by(nombre_completo=r['Nombre']).first():
                        session.add(Alumno(nombre_completo=r['Nombre'], año_escolar=int(r['Año'])))
                        c+=1
                session.commit(); st.success(f"Importados: {c}")
            except Exception as e: st.error(str(e))

    # --- TAB 5: CORRECCIÓN MASIVA (IA + GOOGLE FORMS) ---
    with tab5:
        st.subheader("🧪 Procesador de Evaluaciones (Google Forms)")
        st.info("Sube el Excel/CSV de Google Forms. La IA corregirá usando la bibliografía de la materia.")
        
        # 1. Elegir Materia (Contexto RAG)
        mats = session.query(Materia).all()
        if not mats: st.warning("Carga materias primero."); st.stop()
        
        materia_sel = st.selectbox("1. Seleccionar Materia del Examen:", [m.nombre for m in mats])
        instancia_txt = st.text_input("2. Nombre de la Evaluación (Ej: Parcial 1)")
        
        # 2. Subir Archivo
        archivo_eval = st.file_uploader("3. Subir Resultados (CSV/Excel)", type=["csv", "xlsx"])
        
        if archivo_eval and materia_sel and instancia_txt:
            try:
                # Leer archivo
                df_notas = pd.read_csv(archivo_eval) if archivo_eval.name.endswith('csv') else pd.read_excel(archivo_eval)
                st.write("Vista previa de datos:", df_notas.head(3))
                
                # 3. Mapeo de Columnas
                cols = df_notas.columns.tolist()
                c_nom, c_nota = st.columns(2)
                col_nombre = c_nom.selectbox("¿Qué columna tiene el NOMBRE del alumno?", cols)
                col_nota = c_nota.selectbox("¿Qué columna tiene la NOTA FINAL? (Opcional)", ["(Sin Nota)"] + cols)
                
                cols_preguntas = st.multiselect("Selecciona las columnas de PREGUNTAS a evaluar por IA:", [c for c in cols if c not in [col_nombre, col_nota]])
                
                if st.button("🚀 Iniciar Corrección con IA"):
                    obj_mat = session.query(Materia).filter_by(nombre=materia_sel).first()
                    contexto_rag = obj_mat.programa if obj_mat.programa else "Sin bibliografía."
                    
                    bar = st.progress(0)
                    total = len(df_notas)
                    
                    for i, row in df_notas.iterrows():
                        nombre_alu = row[col_nombre]
                        
                        # Buscar si el alumno existe
                        alumno_bd = session.query(Alumno).filter_by(nombre_completo=nombre_alu).first()
                        if not alumno_bd:
                            st.warning(f"Saltando a {nombre_alu} (No registrado en sistema).")
                            continue
                            
                        # Construir Prompt para este alumno
                        texto_examen = ""
                        for preg in cols_preguntas:
                            resp = str(row[preg])
                            texto_examen += f"\n- PREGUNTA: {preg}\n  RESPUESTA ALUMNO: {resp}\n"
                        
                        prompt_ia = f"""
                        Actúa como profesor experto. Tienes este contexto bibliográfico de la materia:
                        {contexto_rag[:4000]}
                        
                        Evalúa las respuestas de este alumno:
                        {texto_examen}
                        
                        TAREA:
                        Identifica errores conceptuales basándote en la bibliografía.
                        Si está bien, felicita brevemente.
                        Si está mal, explica por qué citando el tema.
                        Sé directo y constructivo. Máximo 1 párrafo.
                        """
                        
                        # Llamada IA
                        try:
                            devolucion = responder_chat_educativo(nombre_alu, "Examen", prompt_ia)
                        except: devolucion = "Error conectando con IA."
                        
                        # Guardar en BD
                        nota_final = float(row[col_nota]) if col_nota != "(Sin Nota)" and pd.to_numeric(row[col_nota], errors='coerce') else 0.0
                        
                        nueva_ev = Evaluacion(
                            alumno_id=alumno_bd.id,
                            materia_id=obj_mat.id,
                            instancia=instancia_txt,
                            nota=nota_final,
                            comentario=f"[IA FEEDBACK]: {devolucion}",
                            fecha=datetime.now()
                        )
                        session.add(nueva_ev)
                        session.commit()
                        
                        # Actualizar barra
                        bar.progress((i + 1) / total)
                    
                    st.success("✅ ¡Corrección Masiva Finalizada! Las devoluciones están en el historial de cada alumno.")
                    
            except Exception as e:
                st.error(f"Error procesando archivo: {e}")

# ==============================================================================
# MODO DASHBOARD
# ==============================================================================
elif "Dashboard" in modo:
    try:
        st.title("🎓 Dashboard Inteligente")
        als = session.query(Alumno).all()
        if not als: st.warning("Sin alumnos.")
        else:
            sel = st.sidebar.selectbox("Alumno:", [a.nombre_completo for a in als])
            alu = session.query(Alumno).filter_by(nombre_completo=sel).first()
            if alu:
                nts = [e.nota for e in alu.evaluaciones]
                p = sum(nts)/len(nts) if nts else 0
                c1,c2,c3 = st.columns(3)
                c1.metric("Alumno", alu.nombre_completo); c2.metric("Promedio", f"{p:.2f}"); c3.metric("Notas", len(nts))
                st.divider()
                
                if st.button("📄 PDF"):
                    with st.spinner("Creando..."):
                        res = responder_chat_educativo(alu.nombre_completo, str(nts), "Resumen.")
                        st.download_button("⬇️ PDF", crear_reporte_pdf(alu, res), f"R_{alu.nombre_completo}.pdf", "application/pdf")

                c_izq, c_der = st.columns([2, 1])
                with c_izq:
                    st.subheader("Historial")
                    if alu.evaluaciones:
                        df_n = pd.DataFrame([{"Fecha":e.fecha, "Materia":e.materia.nombre, "Instancia":e.instancia, "Nota":e.nota, "Comentario":e.comentario} for e in alu.evaluaciones])
                        st.dataframe(df_n, use_container_width=True)
                    else: st.info("Sin notas.")

                with c_der:
                    st.subheader("💬 Chat RAG")
                    if "messages" not in st.session_state: st.session_state.messages = []
                    q = st.chat_input("Pregunta...")
                    if q:
                        with st.chat_message("user"): st.write(q)
                        ctx_docs = ""
                        vistos = set()
                        for e in alu.evaluaciones:
                            if e.materia.nombre not in vistos:
                                prog = e.materia.programa if e.materia.programa else ""
                                ctx_docs += f"\n📚 {e.materia.nombre}:\n{prog[:3000]}\n---"
                                vistos.add(e.materia.nombre)
                        
                        with st.chat_message("assistant"):
                            with st.spinner("Analizando..."):
                                st.write(responder_chat_educativo(alu.nombre_completo, f"DOCS:\n{ctx_docs}", q))

    except Exception as e: st.error(f"Error Dash: {e}")

session.close()
