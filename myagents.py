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
            u = entry.get("user_message","").strip()
            a = entry.get("assistant_response","").strip()
            if u:
                history.append(("User", u))
            if a:
                history.append(("Assistant", a))
        except json.JSONDecodeError:
            continue
    return history

# Histórico de conversas por chat (memória volátil)
conversation_history = {}

# Parâmetros do subprocesso MCP
server_params = {
    "command": "python",
    # "args": ["/home/pi/mcp/src/server/server.py"],
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
        conversation_history[remetente].append(("User", mensagem))

        # # Define as instruções usando as últimas 3 interações em memória
        # instructions = (
        #     "Você é o Arthur. Responda sempre como se fosse o próprio Arthur, mantendo estilo objetivo, direto. Não pergunte, apenas responda "
        #     "Use frases curtas, sem emojis ou formalidades. Nunca mencione ser IA ou assistente ou automação. "
        #     "Para dúvidas desconhecidas, pesquise na internet. Seja direto sem oferecer ajuda. "
        #     "Use ferramentas quando necessário para dados em tempo real (horários, datas, notícias), sempre resumir as respostas de pesquisas. "
        #     "Se perguntarem 'quem é?', assuma que é o próprio Arthur respondendo de forma casual.\n"
        #     + "Histórico:\n"
        #     + "\n".join(f"{role}: {msg}" for role, msg in conversation_history[remetente][-3:])
        # )

        # Define as instruções usando as últimas 3 interações em memória
        historical = "\n".join(f"{role}: {msg}" for role, msg in conversation_history[remetente][-3:])

        SYSTEM_PROMPT = (   "Você é o Arthur: um engenheiro objetivo e direto. Responda sempre como se fosse o próprio Arthur, "
            "em frases curtas, sem emojis, sem formalidades e sem oferecer ajuda extra. "
            "Nunca mencione que é IA ou automação. "
            "Use automaticamente qualquer ferramenta disponível sempre que precisar de dados ou operações que vão além do conhecimento fixo. "
            "Se for algo mutável ou em tempo real (datas, horários, clima, notícias), chame a ferramenta apropriada; "
            "se for pesquisa ou definição, use o WebSearchTool; "
            "se não precisar de ferramenta, responda com seu próprio conhecimento. ")

        instructions = (
            
            f"{SYSTEM_PROMPT}\n\n"
            f"{historical}\n\n"
            "Agora responda apenas à última mensagem de forma curta e direta:"
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
        conversation_history[remetente].append(("Assistant", response_text))
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
