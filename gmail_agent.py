import os
import json
from agents import Agent, Runner, gen_trace_id, trace, WebSearchTool
from agents.model_settings import ModelSettings
from agents.mcp import MCPServerStdio

# Parâmetros do subprocesso MCP que expõe Gmail
server_params = {
    "command": "python",
    "args": ["server.py"],
    "env": os.environ.copy(),
}

async def relay_gmail_request(user_message: str) -> str:
    """
    Sub-agente dedicado a operações Gmail via MCP.
    Recebe a mensagem do usuário e usa automaticamente a ferramenta Gmail apropriada.
    """
    async with MCPServerStdio(params=server_params) as mcp_server:
        # Prompt ideal para orientar o uso das ferramentas Gmail
        SYSTEM_PROMPT = (
            "Você é Arthur, engenheiro direto.\n"
            "Ferramentas Gmail disponíveis via MCP:\n"
            "- search_gmail(query, max_results): retorna IDs de mensagens que atendem à query.\n"
            "- get_gmail(query): retorna assunto, remetente e corpo da primeira mensagem que corresponde à query.\n"
            "- send_gmail(to, subject, body): envia um e-mail.\n"
            "Use a ferramenta certa conforme a solicitação: \n"
            "• Para buscar e-mails, use search_gmail.\n"
            "• Para ler conteúdo, use get_gmail.\n"
            "• Para enviar ou responder, use send_gmail.\n"
            "Não explique como a ferramenta funciona, só retorne o resultado sem mais perguntas.\n"
        )

        instructions = (
            f"[SYSTEM]\n{SYSTEM_PROMPT}\n"
            f"[USER]\n{user_message}\n"
            "Responda de forma objetiva, chamando a ferramenta apropriada sem comentários extras e sem novas perguntas ao usuário."
        )

        agent = Agent(
            name="ArthurGmailSubagent",
            instructions=instructions,
            model="gpt-4.1-mini",
            tools=[WebSearchTool()],  # WebSearch para fallback
            mcp_servers=[mcp_server],
            model_settings=ModelSettings(tool_choice="auto"),
        )

        with trace("Gmail sub-agent interaction", trace_id=gen_trace_id()):
            result = await Runner.run(agent, user_message)

    return result.final_output


