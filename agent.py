from flask import Flask, request, jsonify
from openai import OpenAI
import os

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    # Mapear campos de Tally
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

    # Calificar con OpenAI
    respuesta_raw = calificar_lead(datos)
    resultado = parsear_respuesta(respuesta_raw)

    # Log en consola (visible en Railway)
    print(f"\n🔔 NUEVO LEAD: {datos.get('nombre')}")
    print(f"📊 CALIFICACIÓN: {resultado.get('calificacion')}")
    print(f"💡 RAZÓN: {resultado.get('razon')}")
    print(f"💬 MENSAJE PARA WHATSAPP: {resultado.get('mensaje')}")
    print(f"📱 WHATSAPP: {datos.get('whatsapp')}")
    print("-" * 50)

    return jsonify({
        "status": "ok",
        "lead": datos.get("nombre"),
        "calificacion": resultado.get("calificacion"),
        "razon": resultado.get("razon"),
        "mensaje": resultado.get("mensaje")
    })


@app.route("/", methods=["GET"])
def home():
    return "Agente de leads activo ✅"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
