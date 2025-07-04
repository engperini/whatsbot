import os
from agents import Agent, Runner, gen_trace_id, trace, WebSearchTool
from agents.model_settings import ModelSettings
from agents.mcp import MCPServerStdio

# Histórico de conversas por chat (ex.: { chat_id: [("User", msg), ("Assistant", msg), ...] })
conversation_history = {}

server_params = {
    "command": "python",
    #"args": ["/home/pi/mcp/src/server/server.py"],
    "args": ["server.py"],
    "env": os.environ.copy(),
}

async def process_llm(mensagem: str, nome_remetente: str, remetente: str):


    async with MCPServerStdio(params=server_params) as mcp_server:
        # Atualiza o histórico da conversa para esse chat
        if remetente not in conversation_history:
            conversation_history[remetente] = []
        conversation_history[remetente].append(("User", mensagem))

        # Define as instruções usando as últimas 3 interações (ou toda a história, se preferir)
        instructions = (
            "Você é o Arthur. Responda sempre como se fosse o próprio Arthur, mantendo estilo objetivo, direto. Não pergunte, apenas responda "
            "você nao deve oferecer ajuda, nao deve bater papo, apenas seja direto. "
            "Use frases curtas, sem emojis ou formalidades. Nunca mencione ser IA ou assistente ou automação. "
            "Para dúvidas desconhecidas, pesquise na internet. Seja direto sem oferecer ajuda. "
            "Use ferramentas quando necessário para dados em tempo real (horários, datas, notícias), sempre resumir as respostas de pesquisas. "
            "Se perguntarem 'quem é?', assuma que é o próprio Arthur respondendo de forma casual.\n"
            + "Histórico:\n"
            + "\n".join(f"{role}: {msg}" for role, msg in conversation_history[remetente][-3:])
        )

        # Instancia o agente
        agent = Agent(
            name="Assistant",
            instructions=instructions,
            model="gpt-4o-mini",
            tools=[WebSearchTool()],
            mcp_servers=[mcp_server],
            model_settings=ModelSettings(tool_choice="auto"),
        )

        # Processa a query com o agente (usando trace para log, se desejar)
        with trace("Agent interaction", trace_id=gen_trace_id()):
            result = await Runner.run(agent, mensagem)
        response_text = result.final_output

        conversation_history[remetente].append(("Assistant", response_text))
        return response_text