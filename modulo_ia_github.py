import os
import streamlit as st  # <--- NUEVO: Necesario para leer los secretos de la nube
from openai import OpenAI # <--- MANTENER: Necesario para hablar con la IA

# --- CONFIGURACIÓN DE SEGURIDAD ---
# Intentamos leer el token desde Streamlit Cloud
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    # Si falla (por ejemplo, si lo pruebas en tu PC sin configurar secrets.toml),
    # usa este token de respaldo (Pega tu ghp_... aquí solo si vas a probar localmente)
    GITHUB_TOKEN = ""

# Configuración del cliente (esto no cambia)
client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=GITHUB_TOKEN,
)

# --- FUNCIONES DE IA (Mantenemos la lógica que ya funcionaba) ---

def generar_recomendacion_ia(materia, nota, comentario_profesor):
    prompt = f"""
    Actúa como pedagogo. Da una recomendación breve (máx 20 palabras) para:
    Materia: {materia}, Nota: {nota}, Feedback: "{comentario_profesor}"
    """
    return consultar_llama(prompt)

def responder_chat_educativo(nombre_alumno, historial_texto, pregunta_usuario):
    prompt = f"""
    Eres un asistente escolar inteligente. Estás analizando al alumno: {nombre_alumno}.
    
    Tienes el siguiente historial de calificaciones:
    {historial_texto}
    
    El profesor pregunta: "{pregunta_usuario}"
    
    Responde basándote SOLO en los datos provistos. Sé breve, profesional y directo.
    """
    return consultar_llama(prompt)

def consultar_llama(prompt):
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Eres un asistente útil y preciso."},
                {"role": "user", "content": prompt}
            ],
            model="meta-llama-3.1-8b-instruct",
            temperature=0.7,
            max_tokens=200
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ Error de conexión: {str(e)}"