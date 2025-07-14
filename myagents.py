import datetime
import os
import json
from agents import Agent, Runner, gen_trace_id, trace, WebSearchTool
from agents.model_settings import ModelSettings
from agents.mcp import MCPServerStdio

# Diretório de logs persistidos
LOG_FOLDER = "logs"

def load_persisted_history(chat_id: str, max_msgs: int = 5):
    """
    Lê as últimas max_msgs interações do arquivo logs/messages_{chat_id}.log
    Retorna lista de tuplas (role, message).
    """
    path = os.path.join(LOG_FOLDER, f"messages_{chat_id}.log")
    if not os.path.exists(path):
        return []
    history = []
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()[-max_msgs:]
    for line in lines:
        try:
            entry = json.loads(line)
            u = entry.get("user_message", "").strip()
            a = entry.get("assistant_response", "").strip()
            from_name = entry.get("from_name", "Usuário")
            timestamp = entry.get("timestamp", "")
            msg_type = entry.get("type", "chat")
            if u:
                history.append(("User", u, from_name, msg_type, timestamp))
            if a:
                history.append(("Assistant", a, "Arthur", "chat", timestamp))

        except json.JSONDecodeError:
            continue
    return history

# Histórico de conversas por chat (memória volátil)
conversation_history = {}

# Parâmetros do subprocesso MCP
server_params = {
    "command": "python",
    "args": ["server.py"],
    "env": os.environ.copy(),
}

async def process_llm(mensagem: str, nome_remetente: str, remetente: str):
    # 1) Carrega histórico persistido em disco
    persisted = load_persisted_history(remetente, max_msgs=5)
    # Inicializa memória em RAM com histórico persistido, se primeira vez
    if remetente not in conversation_history:
        conversation_history[remetente] = persisted.copy()

    async with MCPServerStdio(params=server_params) as mcp_server:
        # Atualiza o histórico da conversa para esse chat

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conversation_history[remetente].append(
            ("User", mensagem, nome_remetente, "chat", now)
        )

        #conversation_history[remetente].append(("User", mensagem))


        # Define as instruções usando as últimas 3 interações em memória
        #historical = "\n".join(f"{role}: {msg}" for role, msg in conversation_history[remetente][-3:])

        historical = "\n".join(
            f"{role} ({name}, {ts}, {msg_type}): {msg}"
            for role, msg, name, msg_type, ts in conversation_history[remetente][-3:]
        )
        
        SYSTEM_PROMPT = (   
            
            "Você é Arthur, engenheiro objetivo e direto, conciso. Nunca pergunte nada, apenas responda de forma resumida se te fizerem uma pergunta. "
            "Responda sempre como se fosse o próprio Arthur, usando frases curtas, sem emojis, sem formalidades e sem oferecer ajuda extra. "
            "Nunca mencione que é IA, robô ou automação. "
            "Você está conectado ao WhatsApp e pode responder como Arthur para cnversas com contatos individuais ou grupos. "
            "Sempre utilize automaticamente qualquer ferramenta disponível para obter informações ou executar ações que vão além do seu conhecimento fixo, sem pedir permissão ao usuário. "
            "Ferramentas disponíveis:\n"
            "- Google Drive: listar, buscar, obter link de download, criar pastas, enviar e deletar arquivos.\n"
            "- Gmail: buscar, ler e enviar e-mails.\n"
            "- Google Calendar: listar, criar e obter detalhes de eventos.\n"
            "- Clima: previsão e condições atuais de qualquer cidade.\n"
            "- WhatsApp: enviar mensagens para qualquer número autorizado.\n"
            "- WebSearchTool: pesquisar informações ou definições na web.\n"
            "Se a resposta exigir dados atualizados, operações em arquivos, eventos, e-mails, clima ou pesquisas, use a ferramenta apropriada. "
            "Se não precisar de ferramenta, responda com seu próprio conhecimento. "
            "Você pode receber mensagens de texto, transcrições de áudio ou descrições de imagens (já processadas por um descritor). "
            "Trate descrições de imagens como mensagens normais, como se voce viu a imagem fazendo comentários sobre ela se perguntado apenas."
            "Nunca pergunte nada ao usuário, apenas responda diretamente. "
            "Considere sempre o histórico recente da conversa apresentado, incluindo o nome do remetente, o tipo da mensagem e o timestamp. "
            "Use o histórico para entender o contexto, mas responda exclusivamente à última mensagem recebida "
            "Se necessário, utilize o timestamp para responder de forma adequada ao contexto temporal."
            )

        instructions = (
            
            f"{SYSTEM_PROMPT}\n\n"
            f"{historical}\n\n"
            f"Agora responda apenas à última mensagem que chegou de {nome_remetente}:"
        )


        print(instructions)
        # Instancia o agente com MCP e ferramentas
        agent = Agent(
            name="Assistant",
            instructions=instructions,
            model="gpt-4.1-mini",
            tools=[WebSearchTool()],
            mcp_servers=[mcp_server],
            model_settings=ModelSettings(tool_choice="auto"),
        )

        # Processa a query com o agente (usando trace para log, se desejar)
        with trace("Agent interaction", trace_id=gen_trace_id()):
            result = await Runner.run(agent, mensagem)
        response_text = result.final_output

        # Atualiza memória em RAM com a resposta
        #conversation_history[remetente].append(("Assistant", response_text))
        
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conversation_history[remetente].append(
            ("Assistant", response_text, "Arthur", "chat", now)
        )


        
        #print(conversation_history[remetente])

        # Grava interação no log persistido para futuras sessões
        os.makedirs(LOG_FOLDER, exist_ok=True)
        log_file = os.path.join(LOG_FOLDER, f"messages_{remetente}.log")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "user_message": mensagem,
                "assistant_response": response_text
            }, ensure_ascii=False) + "\n")

        return response_text
