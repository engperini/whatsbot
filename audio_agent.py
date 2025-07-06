# audio_agent.py

import os
import tempfile
import base64
from dotenv import load_dotenv
from openai import OpenAI
from agents import function_tool

# carrega sua chave
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- transcrição de áudio existente ---

def _whisper_transcribe_raw(audio_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp.write(audio_bytes)
        path = tmp.name
    try:
        with open(path, "rb") as f:
            resp = client.audio.transcriptions.create(
                file=f,
                model="gpt-4o-mini-transcribe",
                temperature=0.0,
                language="pt"
            )
        return resp.text.strip()
    finally:
        os.remove(path)

@function_tool
def whisper_transcribe(audio_bytes: bytes) -> str:
    return _whisper_transcribe_raw(audio_bytes)

def transcribe_via_agent(path_or_bytes) -> str:
    if isinstance(path_or_bytes, str):
        with open(path_or_bytes, "rb") as f:
            audio_bytes = f.read()
    else:
        audio_bytes = path_or_bytes
    return _whisper_transcribe_raw(audio_bytes)


# --- nova ferramenta: enviar imagem para o LLM ---

def analyze_image_via_agent(path_or_bytes) -> str:
    """
    Mantém a assinatura existente:
    - aceita str (caminho) ou bytes.
    Envia ao gpt-4.1-mini usando o array de conteúdo multimodal com image_url.
    """
    # carrega bytes
    if isinstance(path_or_bytes, str):
        with open(path_or_bytes, "rb") as f:
            image_bytes = f.read()
    else:
        image_bytes = path_or_bytes

    # codifica como data URI base64 (tipo ajustável conforme seu mimetype)
    import base64
    b64 = base64.b64encode(image_bytes).decode()
    data_uri = f"data:image/jpeg;base64,{b64}"

    # monta o content multimodal (texto + imagem)
    content = [
        {"type": "text",  "text": "você irá passar a mensagem para um chatbot que espera textos. comente de forma objetiva esta imagem, atue como se estivesse vendo e interagindo, nao revele que voce esta descrevendo a imagem:"},
        {"type": "image_url", "image_url": {"url": data_uri}}
    ]

    # chama o modelo gpt-4.1-mini
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": content}],
    )
    return resp.choices[0].message.content.strip()
