#mcp server.py
from mcp.server.fastmcp import FastMCP
import httpx
import os
from dotenv import load_dotenv
import json
from collections import defaultdict
import requests


# Google API imports
import asyncio
import base64
from typing import List, Dict, Literal
from dotenv import load_dotenv
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


load_dotenv()
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# Google API credentials
GMAIL_CREDENTIALS = os.getenv('GMAIL_CREDENTIALS_JSON', 'credentials.json')
GMAIL_TOKEN = os.getenv('GMAIL_TOKEN_JSON', 'token.json')
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
]

#create server
mcp = FastMCP("mcp_server_pi")

@mcp.tool()
async def fetch_weather(city: str) -> str:
    """Fetch current weather for a city"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.openweathermap.org/data/2.5/weather?q={city}&APPID={OPENWEATHER_API_KEY}&units=metric")
        result = response.text
        weather_data = json.loads(result)
        current_weather = (
            f"Agora em {city.capitalize()}: {weather_data['main']['temp']}°C, "
            f"{weather_data['weather'][0]['description'].capitalize()}, "
            f"umidade de {weather_data['main']['humidity']}% e vento de {weather_data['wind']['speed']} m/s."
        )
        
        return current_weather


@mcp.tool()
async def fetch_forecast(city: str, days: int) -> str:
    """Fetch current weather for a city"""
    async with httpx.AsyncClient() as client:
        # Calcula o cnt necessário (8 previsões a cada dia, com intervalos de 3h)
        cnt = days * 8
        
        response = await client.get(f"https://api.openweathermap.org/data/2.5/forecast?q={city}&cnt={cnt}&APPID={OPENWEATHER_API_KEY}&units=metric")
        result = response.text

        forecast_data = json.loads(result)
        forecast_list = forecast_data.get('list', [])
        
        if forecast_list:
            # Agrupa as previsões por data (YYYY-MM-DD)
            daily_temps = defaultdict(list)
            for forecast in forecast_list:
                dt_txt = forecast.get('dt_txt', '')
                date = dt_txt.split(" ")[0] if dt_txt else "Data desconhecida"
                temp_min = forecast['main']['temp_min']
                temp_max = forecast['main']['temp_max']
                daily_temps[date].append((temp_min, temp_max))
            
            daily_summary = []
            # Ordena as datas e calcula, para cada dia, o mínimo e máximo
            for date in sorted(daily_temps.keys()):
                temps = daily_temps[date]
                day_min = min(t[0] for t in temps)
                day_max = max(t[1] for t in temps)
                daily_summary.append(f"{date}: Mín {day_min}°C, Máx {day_max}°C")
                
            forecast_summary = (
                f"Previsão para {city.capitalize()} para os próximos {days} dia(s): " +
                "; ".join(daily_summary) + "."
            )
            #print(forecast_summary)
        else:
            print("Não foi possível obter a previsão do tempo.")
            
        return forecast_summary
    
@mcp.tool()
async def sendwhats(msg: str, num: str) -> str:
    url = "http://localhost:3000/api/sendText"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    data = {
        "chatId": f"{num}@c.us",
        "text": msg,
        "session": "default"
    }

    response = requests.post(url, json=data, headers=headers)
    print(response.json())
    
    return response.json()
    

# ---------------------------- Gmail Service ----------------------------
class GmailService:
    def __init__(self):
        self.creds = None
        if os.path.exists(GMAIL_TOKEN):
            self.creds = Credentials.from_authorized_user_file(GMAIL_TOKEN, SCOPES)
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CREDENTIALS, SCOPES)
                self.creds = flow.run_local_server(port=0)
            with open(GMAIL_TOKEN, 'w') as token:
                token.write(self.creds.to_json())
        self.service = build('gmail', 'v1', credentials=self.creds)

    def list_messages(self, query: str, max_results: int = 10) -> List[dict]:
        res = self.service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
        return res.get('messages', [])

    def get_message(self, msg_id: str, fmt: str = 'full') -> dict:
        return self.service.users().messages().get(userId='me', id=msg_id, format=fmt).execute()

    def send_message(self, to: str, subject: str, body: str) -> dict:
        msg = MIMEText(body)
        msg['to'] = to
        msg['subject'] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        return self.service.users().messages().send(userId='me', body={'raw': raw}).execute()

# Helper para extrair corpo text/plain

def extract_plain_text(payload: dict) -> str:
    parts = payload.get('parts', [])
    for part in parts:
        if part.get('mimeType') == 'text/plain' and part.get('body', {}).get('data'):
            data = base64.urlsafe_b64decode(part['body']['data'])
            return data.decode('utf-8', errors='ignore')
    return ''

# -----------------------------------------------------------------------

# --- Ferramentas Gmail (baseado em google_workspace_mcp) ---

gmail_service = GmailService()

@mcp.tool()
async def search_gmail(query: str, max_results: int = 5) -> str:
    """Busca IDs das mensagens no Gmail que atendem à query"""
    msgs = gmail_service.list_messages(query, max_results)
    if not msgs:
        return f"Nenhuma mensagem encontrada para '{query}'"
    return '\n'.join([m['id'] for m in msgs])

@mcp.tool()
async def get_gmail(query: str) -> str:
    """Retorna assunto, remetente e corpo da primeira mensagem que atende à query"""
    msgs = gmail_service.list_messages(query, 1)
    if not msgs:
        return f"Nenhuma mensagem encontrada para '{query}'"
    msg = gmail_service.get_message(msgs[0]['id'], 'full')
    headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}
    body = extract_plain_text(msg['payload'])
    return (
        f"Subject: {headers.get('Subject')}\n"
        f"From: {headers.get('From')}\n\n"
        f"{body}"
    )

@mcp.tool()
async def send_gmail(to: str, subject: str, body: str) -> str:
    """Envia um e-mail via Gmail"""
    sent = gmail_service.send_message(to, subject, body)
    return f"Email enviado ID: {sent.get('id')}"

# Se quiser adicionar Calendar e Drive, segue mesmo padrão... 

# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"

if __name__ == "__main__":

    # Now run FastMCP (blocking)
    mcp.run()
