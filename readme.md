# WhatsBot - Guia de Instalação e Uso

Este projeto integra um agente conversacional (Arthur) ao WhatsApp via WAHA, com suporte a múltiplas ferramentas (Google Drive, Gmail, Calendar, clima, web search, etc). O bot responde automaticamente, usando contexto e histórico, e pode ser facilmente customizado.

---

## 1. Pré-requisitos

- **Raspberry Pi ou Linux**
- **Python 3.11+**
- **Docker**
- **Git**

---

## 2. Clonando o Repositório

```bash
git clone https://github.com/seu-usuario/seu-repo.git
cd seu-repo
```

---

## 3. Configurando o Ambiente Virtual

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Instalando o Docker

```bash
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io
```

---

## 5. Baixando e Rodando o WAHA

```bash
docker pull devlikeapro/waha:arm
docker tag devlikeapro/waha:arm devlikeapro/waha
docker run -it -p 3000:3000/tcp devlikeapro/waha
```

---

## 6. Configurando o Webhook no WAHA

No painel do WAHA, configure o webhook para apontar para seu servidor:

```
http://<SEU_IP>:3000/webhook
```

**Eventos recomendados:**
- `messages`
- `messages.any`

> **Nota:** O app Python atualmente filtra apenas o evento `messages`.

---

## 7. Inicializando o Bot

Ative o ambiente virtual:

```bash
source venv/bin/activate
```

Execute o servidor Flask:

```bash
python app.py
```

---

## 8. Estrutura e Funções dos Arquivos

### `app.py` (servidor principal)
- **`send_message(chat_id, text)`**: Envia mensagem para um chat.
- **`send_seen(chat_id, message_id, participant)`**: Marca mensagem como lida.
- **`typing(chat_id, seconds)`**: Simula digitação.
- **`load_allowed_contacts()` / `save_allowed_contacts(contacts)`**: Gerencia contatos autorizados.
- **`load_config()` / `save_config(config)`**: Gerencia configurações globais.
- **`get_log_filename(contact)`**: Gera caminho do log para um contato.
- **`reconstruir_historico(contact)`**: Lê últimas interações do log.
- **`responder_whatsapp(mensagem, nome_remetente)`**: Gera resposta usando o agente.
- **`index()`**: Interface de configuração.
- **`webhook()`**: Recebe eventos do WAHA e aciona o bot.

### `myagents.py` (agente Arthur e integração MCP)
- **`load_persisted_history(chat_id, max_msgs)`**: Lê histórico do log, incluindo nome, tipo e timestamp.
- **`process_llm(mensagem, nome_remetente, remetente)`**: Monta contexto, chama o agente MCP e retorna resposta.
- **Gerencia histórico em RAM para contexto conversacional.
- **Monta o prompt do agente com instruções detalhadas e histórico recente.

### `server.py` (ferramentas MCP)
- Implementa integração com:
  - **Google Drive**: listar, buscar, obter link, criar pastas, enviar e deletar arquivos.
  - **Gmail**: buscar, ler e enviar e-mails.
  - **Google Calendar**: listar, criar e obter eventos.
  - **Clima**: previsão e condições atuais.
  - **WhatsApp**: enviar mensagens.
  - **WebSearchTool**: busca na web.
- Cada ferramenta é exposta como função MCP, usada automaticamente pelo agente conforme o contexto.

### `logs/`
- Armazena logs de conversas em JSON, incluindo nome do remetente, tipo, timestamp, mensagem e resposta.

---

## 9. Observações

- O bot responde como Arthur, de forma direta e sem formalidades.
- O histórico recente é usado para contexto, mas a resposta é sempre para a última mensagem recebida.
- O projeto é modular: você pode adicionar novas ferramentas MCP facilmente.
- Todas as configurações e contatos são salvos em arquivos simples para fácil edição.

---

## 10. Dicas

- Para rodar em produção, utilize um serviço como `systemd` ou `supervisor` para manter o bot ativo.
- Certifique-se de liberar a porta 3000 no firewall para receber webhooks do WAHA.
- Consulte os logs em `logs/` para depuração e histórico de conversas.

---

## 11. Créditos

Projeto desenvolvido para integração avançada de WhatsApp com agentes MCP e múltiplas ferramentas