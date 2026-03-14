from fastapi import FastAPI, File, UploadFile, Query
from fastapi.middleware.cors import CORSMiddleware
from fpdf import FPDF
from fastapi.responses import FileResponse
import requests
import datetime
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HF_TOKEN = "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"  # Reemplaza con tu token
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

URL_IMAGEN = "https://router.huggingface.co/hf-inference/models/Organika/sdxl-detector"
URL_CHAT   = "https://router.huggingface.co/hf-inference/models/unitary/toxic-bert"

@app.get("/")
def root():
    return {"mensaje": "TruthLens AI activo ✅"}

@app.post("/analyze/image")
async def analyze_image(file: UploadFile = File(...)):
    contenido = await file.read()
    content_type = file.content_type or "image/jpeg"
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": content_type}
    respuesta = requests.post(URL_IMAGEN, headers=headers, data=contenido)

    if respuesta.status_code != 200:
        return {"error": f"HuggingFace respondió con código {respuesta.status_code}", "detalle": respuesta.text}

    try:
        resultado = respuesta.json()
    except Exception:
        return {"error": "Modelo cargando, intenta en 20 segundos", "detalle": respuesta.text}

    score_ai = 0
    label_ai = "No determinado"
    for item in resultado:
        if item["label"].lower() == "artificial":
            score_ai = round(item["score"] * 100, 2)
            label_ai = item["label"]

    nivel = "Alto" if score_ai > 70 else "Medio" if score_ai > 40 else "Bajo"
    return {
        "archivo": file.filename,
        "tipo": "imagen",
        "probabilidad_ia": f"{score_ai}%",
        "etiqueta": label_ai,
        "nivel_riesgo": nivel,
        "recomendacion": "Reportar a la plataforma o autoridad" if score_ai > 70 else "Monitorear"
    }

@app.post("/analyze/chat")
async def analyze_chat(file: UploadFile = File(...)):
    contenido = await file.read()
    texto = contenido.decode("utf-8")
    respuesta = requests.post(URL_CHAT, headers=HEADERS, json={"inputs": texto[:512]})
    resultado = respuesta.json()

    score_toxico = 0
    if isinstance(resultado, list) and len(resultado) > 0:
        for item in resultado[0]:
            if item["label"].lower() == "toxic":
                score_toxico = round(item["score"] * 100, 2)

    nivel = "Alto" if score_toxico > 70 else "Medio" if score_toxico > 40 else "Bajo"
    return {
        "archivo": file.filename,
        "tipo": "chat",
        "texto_analizado": texto[:200],
        "probabilidad_toxicidad": f"{score_toxico}%",
        "nivel_riesgo": nivel,
        "recomendacion": "Guardar como evidencia y reportar" if score_toxico > 70 else "Monitorear"
    }

@app.post("/analyze/url")
async def analyze_url(url: str):
    try:
        suspicious_keywords = [
            "free", "winner", "click", "verify", "account", "suspended",
            "login", "secure", "update", "confirm", "prize", "urgent"
        ]
        url_lower = url.lower()
        found_keywords = [kw for kw in suspicious_keywords if kw in url_lower]
        indicators = []
        score = 0

        if len(found_keywords) > 0:
            indicators.append(f"Palabras sospechosas: {', '.join(found_keywords)}")
            score += len(found_keywords) * 15
        if url.count(".") > 3:
            indicators.append("Demasiados subdominios")
            score += 20
        if any(c.isdigit() for c in url.split("/")[0]):
            indicators.append("IP en lugar de dominio")
            score += 30
        if len(url) > 75:
            indicators.append("URL inusualmente larga")
            score += 15
        if "http://" in url and "https://" not in url:
            indicators.append("Sin cifrado HTTPS")
            score += 20

        score = min(score, 100)
        nivel = "Alto" if score > 70 else "Medio" if score > 40 else "Bajo"
        return {
            "url": url,
            "tipo": "url",
            "probabilidad_phishing": f"{score}%",
            "indicadores": indicators if indicators else ["Ninguno detectado"],
            "nivel_riesgo": nivel,
            "recomendacion": "No visitar esta URL" if score > 70 else "Proceder con precaución" if score > 40 else "URL aparentemente segura"
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/analyze/image-url")
async def analyze_image_url(image_url: str):
    try:
        respuesta_img = requests.get(image_url, timeout=10)
        if respuesta_img.status_code != 200:
            return {"error": "No se pudo descargar la imagen desde esa URL"}

        contenido = respuesta_img.content
        content_type = respuesta_img.headers.get("Content-Type", "image/jpeg")
        headers_hf = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": content_type}
        respuesta = requests.post(URL_IMAGEN, headers=headers_hf, data=contenido)

        if respuesta.status_code != 200:
            return {"error": f"HuggingFace respondió con código {respuesta.status_code}"}

        resultado = respuesta.json()
        score_ai = 0
        for item in resultado:
            if item["label"].lower() == "artificial":
                score_ai = round(item["score"] * 100, 2)

        nivel = "Alto" if score_ai > 70 else "Medio" if score_ai > 40 else "Bajo"
        return {
            "archivo": image_url,
            "tipo": "imagen",
            "probabilidad_ia": f"{score_ai}%",
            "nivel_riesgo": nivel,
            "recomendacion": "Reportar a la plataforma o autoridad" if score_ai > 70 else "Monitorear"
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/report")
async def generate_report(
    file: UploadFile = File(None),
    tipo: str = "imagen",
    image_url: Optional[str] = Query(None)
):
    # Obtener contenido y nombre
    if image_url:
        respuesta_img = requests.get(image_url, timeout=10)
        contenido = respuesta_img.content
        filename = image_url.split("/")[-1] or "imagen_url.jpg"
        content_type = respuesta_img.headers.get("Content-Type", "image/jpeg")
    elif file:
        contenido = await file.read()
        filename = file.filename
        content_type = file.content_type or "image/jpeg"
    else:
        return {"error": "No se proporcionó archivo ni URL"}

    # Analizar según tipo
    if tipo == "imagen":
        headers_hf = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": content_type}
        respuesta = requests.post(URL_IMAGEN, headers=headers_hf, data=contenido)
        resultado = respuesta.json()
        score = 0
        if isinstance(resultado, list):
            for item in resultado:
                if isinstance(item, dict) and item.get("label", "").lower() == "artificial":
                    score = round(item["score"] * 100, 2)
    else:
        texto = contenido.decode("utf-8")
        respuesta = requests.post(URL_CHAT, headers=HEADERS, json={"inputs": texto[:512]})
        resultado = respuesta.json()
        score = 0
        for item in resultado[0]:
            if item["label"].lower() == "toxic":
                score = round(item["score"] * 100, 2)
        nivel = "Alto" if score > 70 else "Medio" if score > 40 else "Bajo"
        detalle = f"Probabilidad de toxicidad: {score}%"

    # Generar PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 20)
    pdf.cell(0, 15, "TruthLens AI", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, "Reporte de Evidencia Digital", ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, f"Fecha: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.cell(0, 8, f"Archivo analizado: {filename}", ln=True)
    pdf.cell(0, 8, f"Tipo de analisis: {'Imagen' if tipo == 'imagen' else 'Chat'}", ln=True)
    pdf.ln(8)

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Resultado del Analisis", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, detalle, ln=True)
    pdf.cell(0, 8, f"Nivel de riesgo: {nivel}", ln=True)
    pdf.ln(8)

    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Recomendacion", ln=True)
    pdf.set_font("Arial", "", 12)
    recomendacion = "Reportar a la plataforma o autoridad competente" if score > 70 else "Monitorear el contenido"
    pdf.multi_cell(0, 8, recomendacion)

    ruta_pdf = f"reporte_{filename}_{tipo}.pdf"
    pdf.output(ruta_pdf)
    return FileResponse(ruta_pdf, media_type="application/pdf", filename=ruta_pdf)
