from flask import Flask, request, jsonify
from openai import OpenAI
import os
import requests
import json
from datetime import datetime

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")
LEADS_FILE = "/tmp/leads.json"


def cargar_leads():
    if os.path.exists(LEADS_FILE):
        with open(LEADS_FILE, "r") as f:
            return json.load(f)
    return []


def guardar_lead(lead):
    leads = cargar_leads()
    leads.insert(0, lead)
    with open(LEADS_FILE, "w") as f:
        json.dump(leads, f, ensure_ascii=False)


def calificar_lead(datos):
    prompt = f"""
Eres un agente experto en calificar leads para un Club de IA para emprendedores.

Analiza este lead y califícalo:

- Nombre: {datos.get('nombre')}
- Negocio propio: {datos.get('negocio_propio')}
- A qué se dedica: {datos.get('dedicacion')}
- Mayor problema: {datos.get('problema')}
- Ha usado IA antes: {datos.get('uso_ia')}
- Tiempo en el negocio: {datos.get('tiempo_negocio')}

Criterios de calificación:
- CALIENTE: tiene negocio propio + tiene un problema claro + lleva más de 1 año
- TIBIO: tiene negocio pero problema vago, o lleva menos de 1 año
- FRÍO: no tiene negocio propio o no sabe qué problema tiene

Responde en este formato exacto:
CALIFICACIÓN: [CALIENTE/TIBIO/FRÍO]
RAZÓN: [una sola línea explicando por qué]
MENSAJE: [mensaje personalizado de bienvenida para enviarle por WhatsApp, máximo 3 líneas, en tono cercano]
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


def parsear_respuesta(respuesta):
    lineas = respuesta.strip().split("\n")
    resultado = {}
    for linea in lineas:
        if linea.startswith("CALIFICACIÓN:"):
            resultado["calificacion"] = linea.replace("CALIFICACIÓN:", "").strip()
        elif linea.startswith("RAZÓN:"):
            resultado["razon"] = linea.replace("RAZÓN:", "").strip()
        elif linea.startswith("MENSAJE:"):
            resultado["mensaje"] = linea.replace("MENSAJE:", "").strip()
    return resultado


def enviar_whatsapp(telefono, mensaje):
    telefono = telefono.strip().replace(" ", "").replace("+", "")
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "text",
        "text": {"body": mensaje}
    }
    response = requests.post(url, json=payload, headers=headers)
    print(f"WhatsApp enviado: {response.status_code} - {response.text}")


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    campos = data.get("data", {}).get("fields", [])
    datos = {}
    for campo in campos:
        label = campo.get("label", "").lower()
        value = campo.get("value", "")
        if "nombre" in label:
            datos["nombre"] = value
        elif "email" in label:
            datos["email"] = value
        elif "whatsapp" in label:
            datos["whatsapp"] = value
        elif "negocio propio" in label:
            datos["negocio_propio"] = value
        elif "dedicas" in label:
            datos["dedicacion"] = value
        elif "problema" in label:
            datos["problema"] = value
        elif "usado ia" in label:
            datos["uso_ia"] = value
        elif "tiempo" in label:
            datos["tiempo_negocio"] = value

    respuesta_raw = calificar_lead(datos)
    resultado = parsear_respuesta(respuesta_raw)

    lead = {
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "nombre": datos.get("nombre", ""),
        "email": datos.get("email", ""),
        "whatsapp": datos.get("whatsapp", ""),
        "dedicacion": datos.get("dedicacion", ""),
        "problema": datos.get("problema", ""),
        "calificacion": resultado.get("calificacion", ""),
        "razon": resultado.get("razon", ""),
        "mensaje": resultado.get("mensaje", "")
    }
    guardar_lead(lead)

    if datos.get("whatsapp") and resultado.get("mensaje"):
        enviar_whatsapp(datos["whatsapp"], resultado["mensaje"])

    return jsonify({"status": "ok", **lead})


@app.route("/", methods=["GET"])
def home():
    return "Agente de leads activo ✅"


@app.route("/dashboard", methods=["GET"])
def dashboard():
    leads = cargar_leads()

    calientes = sum(1 for l in leads if l.get("calificacion") == "CALIENTE")
    tibios = sum(1 for l in leads if l.get("calificacion") == "TIBIO")
    frios = sum(1 for l in leads if l.get("calificacion") == "FRÍO")

    filas = ""
    for lead in leads:
        cal = lead.get("calificacion", "")
        if cal == "CALIENTE":
            color = "#ff4444"
            emoji = "🔥"
        elif cal == "TIBIO":
            color = "#ff9900"
            emoji = "🌡️"
        else:
            color = "#4488ff"
            emoji = "❄️"

        filas += f"""
        <tr>
            <td>{lead.get('fecha', '')}</td>
            <td><strong>{lead.get('nombre', '')}</strong></td>
            <td>{lead.get('whatsapp', '')}</td>
            <td>{lead.get('dedicacion', '')}</td>
            <td>{lead.get('problema', '')}</td>
            <td><span style="background:{color};color:white;padding:4px 10px;border-radius:20px;font-weight:bold;">{emoji} {cal}</span></td>
            <td style="font-size:13px;">{lead.get('razon', '')}</td>
            <td style="font-size:13px;font-style:italic;">{lead.get('mensaje', '')}</td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Dashboard de Leads</title>
        <meta http-equiv="refresh" content="30">
        <style>
            body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
            h1 {{ color: #333; }}
            .stats {{ display: flex; gap: 20px; margin-bottom: 30px; }}
            .stat {{ background: white; padding: 20px 30px; border-radius: 12px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
            .stat h2 {{ margin: 0; font-size: 40px; }}
            .stat p {{ margin: 5px 0 0; color: #666; }}
            table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
            th {{ background: #333; color: white; padding: 12px 15px; text-align: left; }}
            td {{ padding: 12px 15px; border-bottom: 1px solid #eee; vertical-align: top; }}
            tr:hover {{ background: #f9f9f9; }}
        </style>
    </head>
    <body>
        <h1>📊 Dashboard de Leads — Club de IA</h1>
        <div class="stats">
            <div class="stat"><h2 style="color:#ff4444">🔥 {calientes}</h2><p>Calientes</p></div>
            <div class="stat"><h2 style="color:#ff9900">🌡️ {tibios}</h2><p>Tibios</p></div>
            <div class="stat"><h2 style="color:#4488ff">❄️ {frios}</h2><p>Fríos</p></div>
            <div class="stat"><h2>{len(leads)}</h2><p>Total</p></div>
        </div>
        <table>
            <tr>
                <th>Fecha</th>
                <th>Nombre</th>
                <th>WhatsApp</th>
                <th>Negocio</th>
                <th>Problema</th>
                <th>Calificación</th>
                <th>Razón</th>
                <th>Mensaje WhatsApp</th>
            </tr>
            {filas}
        </table>
        <p style="color:#999;font-size:12px;margin-top:20px;">Se actualiza automáticamente cada 30 segundos</p>
    </body>
    </html>
    """
    return html


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
