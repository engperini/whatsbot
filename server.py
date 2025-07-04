#mcp server.py
from mcp.server.fastmcp import FastMCP
import httpx
import os
from dotenv import load_dotenv
import json
from collections import defaultdict
import requests

load_dotenv()
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

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
    



# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"

if __name__ == "__main__":

    # Now run FastMCP (blocking)
    mcp.run()


