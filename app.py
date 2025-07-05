import os
import json
import requests
import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template, redirect, url_for
from openai import OpenAI

import asyncio

import time
import os

# Importa o módulo agents
from myagents import process_llm

load_dotenv()
client = OpenAI()

""" server_params = {
    "command": "python",
    "args": ["server.py"],
    "env": os.environ.copy(),
} """

app = Flask(__name__)

# Arquivos de configuração e log unificado
ALLOWED_CONTACTS_FILE = "allowed_contacts.txt"
MESSAGES_LOG_FILE = "messages.log"  # Unifica mensagens recebidas e respostas (JSON line)
CONFIG_FILE = "config.txt"
# Defina o caminho da pasta de logs (por exemplo, "logs")
LOG_FOLDER = "logs"
# Cria a pasta, se não existir
if not os.path.exists(LOG_FOLDER):
    os.makedirs(LOG_FOLDER)

conversation_history = {}

# Função para enviar mensagem
def send_message(chat_id, text):
    response = requests.post(
        "http://localhost:3000/api/sendText",
        json={
            "chatId": chat_id,
            "text": text,
            "session": "default",
        },
    )
    response.raise_for_status()

# Função para marcar como "visto"
def send_seen(chat_id, message_id, participant):
    response = requests.post(
        "http://localhost:3000/api/sendSeen",
        json={
            "session": "default",
            "chatId": chat_id,
            "messageId": message_id,
            "participant": participant,
        },
    )
    response.raise_for_status()

# Simula digitação
def typing(chat_id, seconds):
    requests.post("http://localhost:3000/api/startTyping", json={"session": "default", "chatId": chat_id})
    time.sleep(seconds)
    requests.post("http://localhost:3000/api/stopTyping", json={"session": "default", "chatId": chat_id})



# Funções para gerenciar allowed contacts (formato: número,nome,enabled)
def load_allowed_contacts():
    contacts = []
    if os.path.exists(ALLOWED_CONTACTS_FILE):
        with open(ALLOWED_CONTACTS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    parts = line.split(",")
                    if len(parts) == 3:
                        contact = parts[0].strip()
                        name = parts[1].strip()
                        enabled = parts[2].strip().lower() == "true"
                        contacts.append({"contact": contact, "name": name, "enabled": enabled})
                    elif len(parts) == 2:
                        # Se só tem número e enabled, usamos o número como nome
                        contact = parts[0].strip()
                        enabled = parts[1].strip().lower() == "true"
                        contacts.append({"contact": contact, "name": contact, "enabled": enabled})
                    else:
                        contacts.append({"contact": line, "name": line, "enabled": True})
    else:
        contacts = [{"contact": "55191111111111", "name": "user-change", "enabled": True}]
    return contacts

def save_allowed_contacts(contacts):
    with open(ALLOWED_CONTACTS_FILE, "w") as f:
        for c in contacts:
            f.write(f"{c['contact']},{c.get('name', c['contact'])},{str(c['enabled']).lower()}\n")

allowed_contacts = load_allowed_contacts()


# Funções para gerenciar configuração global
def load_config():
    config = {
        "enable_responses": "true",
        "enable_group_responses": "true"
        }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    config[key.strip()] = value.strip()
    return config

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        for key, value in config.items():
            f.write(f"{key}={value}\n")

config = load_config()

def get_log_filename(contact: str) -> str:
    # Gera o nome do arquivo na pasta definida para logs
    return os.path.join(LOG_FOLDER, f"messages_{contact}.log")

# Interface de configuração – rota principal
@app.route("/", methods=["GET", "POST"])
def index():
    global config, allowed_contacts
    if request.method == "POST":
        # Atualiza a configuração global
        global_enable = request.form.get("enable_responses", "off")
        config["enable_responses"] = "true" if global_enable == "on" else "false"
        
        group_enable = request.form.get("enable_group_responses", "off")
        config["enable_group_responses"] = "true" if group_enable == "on" else "false"

        # Atualiza cada contato individual (checkbox com nome: enabled_<número>)
        for c in allowed_contacts:
            checkbox_name = f"enabled_{c['contact']}"
            c["enabled"] = True if request.form.get(checkbox_name) == "on" else False
        
        # Exclusão de contato (se enviado no campo delete_contact)
        delete_contact = request.form.get("delete_contact", "").strip()
        if delete_contact:
            allowed_contacts = [c for c in allowed_contacts if c["contact"] != delete_contact]
        
        # Adiciona novo contato, se informado
        new_contact = request.form.get("new_contact", "").strip()
        new_contact_name = request.form.get("new_contact_name", "").strip()
        if new_contact:
            if all(new_contact != c["contact"] for c in allowed_contacts):
                if len(allowed_contacts) < 10:
                    if not new_contact_name:
                        new_contact_name = new_contact
                    allowed_contacts.append({"contact": new_contact, "name": new_contact_name, "enabled": True})
                else:
                    return redirect(url_for("index", message="Limite de 10 contatos atingido."))
        
        save_config(config)
        save_allowed_contacts(allowed_contacts)
        return redirect(url_for("index", message="Configurações salvas."))
    
    msg = request.args.get("message", "")
    # Lê o log unificado para exibição na interface
    log_sent_content = ""
    if os.path.exists(MESSAGES_LOG_FILE):
        with open(MESSAGES_LOG_FILE, "r") as f:
            linhas = f.readlines()
        log_entries = []
        for linha in linhas:
            try:
                entry = json.loads(linha)
                log_entries.append(entry)
            except Exception as e:
                print("Erro ao parsear log:", e)
        # Converte os logs para uma string formatada (você pode customizar o layout)
        log_sent_content = "\n".join(json.dumps(entry, indent=2, ensure_ascii=False) for entry in log_entries)
    else:
        log_sent_content = "Nenhuma mensagem registrada."
    
    return render_template("index.html", config=config, allowed_contacts=allowed_contacts, message=msg, log_sent_content=log_sent_content)


# Cache simples de mensagens processadas
mensagens_processadas = set()
# Endpoint do webhook do TextMeBot
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    # Verifica se é um evento de mensagem, nao configurar na api 
    if data.get("event") != "message.any":
        return f"Unknown event {data.get('event')}", 400

    payload = data.get("payload", {})
    message_id = payload.get("id")

    
    #avoid processing the same message multiple times
    if message_id in mensagens_processadas:
        return jsonify({"status": "ignorado", "motivo": "mensagem duplicada"}), 200
    mensagens_processadas.add(message_id)

    _data = payload.get('_data', {})

    # main variables
    chat_id = payload.get("from")
    message_id = payload.get("id")
    participant = participant = payload.get("participant") or _data.get("author")
    texto = payload.get("body")

    # alternative variables
    remetente = chat_id.split('@')[0]
    mensagem_recebida = texto
    from_name = _data.get("notifyName", "Desconhecido")

    # 1) detecta grupo e remetente puro
    if chat_id.endswith("@g.us") and participant:
        remetente = participant.split("@")[0]
        is_group   = True
    else:
        remetente = chat_id.split("@")[0]
        is_group   = False

    print( f"Mensagem recebida de {from_name} chat_id={chat_id}")

    # ignore bot messages starting with "🤖:"
    if mensagem_recebida.strip().startswith("🤖:"):
        return jsonify({"status": "ignorado", "motivo": "mensagem do próprio bot"}), 200

    bot_number = data.get("me", {}).get("id", "").split('@')[0]
    
    if remetente == bot_number:
        return jsonify({"status": "ignorado", "motivo": "mensagem própria"}), 200

    # timestamp
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    

    # register log entry even for unauthorized contacts

    log_entry = {
        "from": remetente,
        "from_name": from_name,
        "to": payload.get("to", ""),
        "type": _data.get("type", ""),
        "user_message": mensagem_recebida,
        "assistant_response": "",  # fill with response later
        "timestamp": timestamp
    }
    
    
    
    # check if contact is allowed and enabled
    contact_entry = next((c for c in allowed_contacts if c["contact"] == remetente), None)
    autorizado = contact_entry is not None and contact_entry["enabled"]
    respostas_ativas = config.get("enable_responses", "true") == "true"
    
    if is_group:
        respostas_ativas = respostas_ativas and config.get("enable_group_responses", "true") == "true"

    
    
    if autorizado and respostas_ativas:
        if mensagem_recebida:
            print("authorized contact:", remetente)

            # Mark seen
            send_seen(chat_id=chat_id, message_id=message_id, participant=participant)

            # emulate typing
            typing(chat_id, 3)

            # Process LLM
            resposta = asyncio.run( process_llm(mensagem_recebida, from_name, remetente))


            #answer whatsapp
            whatsapp_result = send_message(chat_id, f"🤖: {resposta}")

            log_entry["assistant_response"] = resposta
            print(log_entry)
        else:
            resposta = "mensagem texto vazia"
            whatsapp_result = {"status": "ok", "detail": resposta}
            log_entry["assistant_response"] = resposta
    else:
        resposta = "Respostas desabilitadas ou remetente não autorizado."
        whatsapp_result = {"status": "ok", "detail": resposta}
        log_entry["assistant_response"] = resposta
    
    # Registra a entrada unificada no log (cada linha é um JSON)
    with open(get_log_filename(remetente), "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    
    return jsonify({
        "status": "ok",
        "resposta": resposta,
        "whatsapp": whatsapp_result
    }), 200

if __name__ == "__main__":
    app.run(host="192.168.0.22", port=5000)
