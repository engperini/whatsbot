# audio_agent.py

import os
import tempfile
from dotenv import load_dotenv
from openai import OpenAI
from agents import function_tool

# carrega sua chave
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def _whisper_transcribe_raw(audio_bytes: bytes) -> str:
    """
    Lógica pura: grava bytes de OGG/OPUS num temp .ogg,
    chama Whisper e retorna o texto.
    """
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp.write(audio_bytes)
        path = tmp.name

    try:
        with open(path, "rb") as f:
            resp = client.audio.transcriptions.create(
                file=f, model="gpt-4o-mini-transcribe", temperature=0.0
            )
        return resp.text.strip()
    finally:
        os.remove(path)

@function_tool
def whisper_transcribe(audio_bytes: bytes) -> str:
    """
    Tool do Agent: apenas delega à função pura.
    """
    return _whisper_transcribe_raw(audio_bytes)

def transcribe_via_agent(path_or_bytes) -> str:
    """
    Entrada compatível com o seu webhook atual:
    - se for str: abre o arquivo e lê bytes;
    - se for bytes: usa direto.
    Chama a lógica pura, não o FunctionTool.
    """
    if isinstance(path_or_bytes, str):
        with open(path_or_bytes, "rb") as f:
            audio_bytes = f.read()
    else:
        audio_bytes = path_or_bytes

    return _whisper_transcribe_raw(audio_bytes)
