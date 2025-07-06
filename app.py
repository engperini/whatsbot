import os
import json
import requests
import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, redirect, url_for
from openai import OpenAI

import asyncio
import time

import tempfile

# Importa o módulo agents
from audio_agent import transcribe_via_agent
from audio_agent import analyze_image_via_agent
from myagents import process_llm


load_dotenv()
client = OpenAI()

app = Flask(__name__)

# Arquivos de configuração e log unificado
ALLOWED_CONTACTS_FILE = "allowed_contacts.txt"
MESSAGES_LOG_FILE = "messages.log"
CONFIG_FILE = "config.txt"
LOG_FOLDER = "logs"
if not os.path.exists(LOG_FOLDER):
    os.makedirs(LOG_FOLDER)

# Funções de envio
def send_message(chat_id, text):
    r = requests.post("http://localhost:3000/api/sendText", json={
        "chatId": chat_id,
        "text": text,
        "session": "default",
    })
    r.raise_for_status()

def send_message_quote(chat_id, text, message_id=None):
    r = requests.post("http://localhost:3000/api/sendText", json={
        "chatId": chat_id,
        "text": text,
        "session": "default",
        "quotedMessageId": message_id,
    })
    r.raise_for_status()

def send_seen(chat_id, message_id, participant):
    r = requests.post("http://localhost:3000/api/sendSeen", json={
        "session": "default",
        "chatId": chat_id,
        "messageId": message_id,
        "participant": participant,
    })
    r.raise_for_status()

def typing(chat_id, seconds):
    requests.post("http://localhost:3000/api/startTyping", json={"session": "default", "chatId": chat_id})
    time.sleep(seconds)
    requests.post("http://localhost:3000/api/stopTyping", json={"session": "default", "chatId": chat_id})

# Gerenciamento de contatos permitidos
def load_allowed_contacts():
    contacts = []
    if os.path.exists(ALLOWED_CONTACTS_FILE):
        with open(ALLOWED_CONTACTS_FILE) as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) == 3:
                    c, n, e = parts
                    contacts.append({"contact": c.strip(), "name": n.strip(), "enabled": e.strip().lower() == "true"})
                elif len(parts) == 2:
                    c, e = parts
                    contacts.append({"contact": c.strip(), "name": c.strip(), "enabled": e.strip().lower() == "true"})
                else:
                    contacts.append({"contact": parts[0].strip(), "name": parts[0].strip(), "enabled": True})
    else:
        contacts = [{"contact": "55191111111111", "name": "user-change", "enabled": True}]
    return contacts

def save_allowed_contacts(contacts):
    with open(ALLOWED_CONTACTS_FILE, "w") as f:
        for c in contacts:
            f.write(f"{c['contact']},{c.get('name', c['contact'])},{str(c['enabled']).lower()}\n")

allowed_contacts = load_allowed_contacts()

# Gerenciamento de configuração
def load_config():
    config = {"enable_responses": "true", "enable_group_responses": "true"}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    config[k.strip()] = v.strip()
    return config

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        for k, v in config.items():
            f.write(f"{k}={v}\n")

config = load_config()

def get_log_filename(contact: str) -> str:
    return os.path.join(LOG_FOLDER, f"messages_{contact}.log")

# Interface de configuração
@app.route("/", methods=["GET", "POST"])
def index():
    global config, allowed_contacts
    if request.method == "POST":
        # global responses
        config["enable_responses"] = "true" if request.form.get("enable_responses") == "on" else "false"
        # group responses
        config["enable_group_responses"] = "true" if request.form.get("enable_group_responses") == "on" else "false"
        # contatos
        for c in allowed_contacts:
            c["enabled"] = request.form.get(f"enabled_{c['contact']}") == "on"
        delete_contact = request.form.get("delete_contact", "").strip()
        if delete_contact:
            allowed_contacts = [c for c in allowed_contacts if c["contact"] != delete_contact]
        new_contact = request.form.get("new_contact", "").strip()
        new_name    = request.form.get("new_contact_name", "").strip()
        if new_contact and all(new_contact != c["contact"] for c in allowed_contacts):
            if len(allowed_contacts) < 10:
                allowed_contacts.append({
                    "contact": new_contact,
                    "name": new_name or new_contact,
                    "enabled": True
                })
        save_config(config)
        save_allowed_contacts(allowed_contacts)
        return redirect(url_for("index", message="Configurações salvas."))
    # GET: carrega logs
    msg = request.args.get("message", "")
    if os.path.exists(MESSAGES_LOG_FILE):
        with open(MESSAGES_LOG_FILE) as f:
            lines = f.readlines()
        logs = []
        for l in lines:
            try:
                logs.append(json.loads(l))
            except:
                pass
        log_sent_content = "\n".join(json.dumps(entry, indent=2, ensure_ascii=False) for entry in logs)
    else:
        log_sent_content = "Nenhuma mensagem registrada."
    return render_template("index.html",
                           config=config,
                           allowed_contacts=allowed_contacts,
                           message=msg,
                           log_sent_content=log_sent_content)

# Cache de mensagens processadas
mensagens_processadas = set()

# Webhook
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if data.get("event") != "message.any":
        return f"Unknown event {data.get('event')}", 400

    payload    = data.get("payload", {})
    _data      = payload.get("_data", {})
    chat_id    = payload.get("from")
    participant= payload.get("participant") or _data.get("author")
    message_id = payload.get("id")
    texto      = (payload.get("body") or "").strip()
    from_name  = _data.get("notifyName", "Desconhecido")
    msg_type  = _data.get("type")
    

    if payload.get("hasMedia"):
        media_info = payload.get("media") or {}
        mimetype = media_info.get("mimetype", "")
        media_url = media_info.get("url")

        print(mimetype)
        subtype = mimetype.split("/")[1].split(";")[0]  # -> "ogg"
        suffix = f".{subtype}"                         # -> ".ogg"

        try:
            resp = requests.get(media_url)
            resp.raise_for_status()
            media_bytes = resp.content
        except requests.exceptions.HTTPError as e:
            print(f"Falha ao baixar mídia: {e}")
            return jsonify({"status":"ok","message":"falha no download de mídia"}), 200
        else:
            # 2) Se for voz (ptt ou audio), transcreve
            if msg_type in ("ptt", "audio"):
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                tmp.write(media_bytes)
                tmp_path = tmp.name
                tmp.close()

                print(f"Transcrevendo áudio de {chat_id} ({message_id})...")

                # Transcreve: lê bytes e envia ao Agent
                with open(tmp_path, "rb") as f:
                    audio_bytes = f.read()

                texto = transcribe_via_agent(audio_bytes)
                print(f"Transcrição concluída: {texto}")

                os.unlink(tmp_path)
            
            if msg_type in ("image", "video", "document"):
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                tmp.write(media_bytes)
                tmp_path = tmp.name
                tmp.close()

                print(f"Analisando imagem de {chat_id} ({message_id})...")

                # Análise de imagem: lê bytes e envia ao Agent
                with open(tmp_path, "rb") as f:
                    image_bytes = f.read()

                texto = analyze_image_via_agent(image_bytes)
                print(f"Análise concluída: {texto}")

                os.unlink(tmp_path)

    # evita duplicatas
    if message_id in mensagens_processadas:
        return jsonify({"status":"ignorado","motivo":"mensagem duplicada"}),200
    mensagens_processadas.add(message_id)

    # ignora mensagens do bot
    if texto.startswith("🤖:"):
        return jsonify({"status":"ignorado","motivo":"mensagem do próprio bot"}),200
    
    bot_num = data.get("me",{}).get("id","").split("@")[0]

    # detecta grupo
    is_group = chat_id.endswith("@g.us") and bool(participant)
    
    # define remetente puro
    if is_group:
        remetente = participant.split("@")[0]
    else:
        remetente = chat_id.split("@")[0]

    if remetente == bot_num:
        return jsonify({"status":"ignorado","motivo":"mensagem própria"}),200



    # log entry base
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        "from": remetente,
        "from_name": from_name,
        "to": payload.get("to",""),
        "type": _data.get("type",""),
        "user_message": texto,
        "assistant_response": "",
        "timestamp": timestamp
    }

    # ————————————— LÓGICA DE DECISÃO UNIFICADA —————————————
    contact_entry = next((c for c in allowed_contacts if c["contact"] == remetente), None)
    autorizado    = bool(contact_entry and contact_entry["enabled"])
    global_on     = (config.get("enable_responses") == "true")
    group_on      = (config.get("enable_group_responses") == "true")
    devo_responder = autorizado and global_on and (not is_group or group_on) and bool(texto)
    # ———————————————————————————————————————————————————————————

    print(f"Recebido de {from_name}: {texto}, participant: {participant}, is_group: {is_group}")

    if devo_responder:
        send_seen(chat_id=chat_id, message_id=message_id, participant=participant)
        typing(chat_id, 2)
        resposta = asyncio.run(process_llm(texto, from_name, remetente))
        send_message(chat_id=chat_id, text=f"🤖: {resposta}")
        log_entry["assistant_response"] = resposta
    else:
        resposta = "Respostas desabilitadas ou remetente não autorizado."
        log_entry["assistant_response"] = resposta

    # grava no log por contato
    with open(get_log_filename(remetente), "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    print(f"Resposta enviada: {resposta}")

    return jsonify({"status":"ok","resposta": resposta}),200

if __name__ == "__main__":
    app.run(host="192.168.0.22", port=5000)
