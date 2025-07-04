## Instructions ##

WAHA Whatsapp Server Configuration

First time docker commands

sudo apt-get install ca-certificates curl

sudo install -m 0755 -d /etc/apt/keyrings

sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc

sudo chmod a+r /etc/apt/keyrings/docker.asc

pi@raspberrypi:~ $ echo   "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \

pi@raspberrypi:~ $   $(. /etc/os-release && echo "$VERSION_CODENAME") stable" |   sudo tee /etc/apt/sources.list.d/docker.list > /dev/null


sudo apt-get install ./docker-desktop-amd64.deb
docker pull devlikeapro/waha:arm
docker tag devlikeapro/waha:arm devlikeapro/waha


Start Container
docker run -it -p 3000:3000/tcp devlikeapro/waha

Webhook configuration at WAHA Dashboard
'http://yourserverip:3000/webhook

Eventsconfiguration
'messages'
'messages.any'
Note: the current python app.py filters only 'messages' event

# Webhook App.py Functions

Project App MCP Chatbot Folder
'~/mcp/whatsserver'

Activate the Virtual Env
 source env/bin/activate


Execute:
python app.py

# WhatsServer Functions

This README provides an overview of the functions utilized in the `app.py` file of the WhatsServer project.

## Functions

### 1. `send_message(chat_id, text)`
Sends a message to a specified chat ID.
- **Parameters**:
  - `chat_id`: The ID of the chat.
  - `text`: The message text.
- **Usage**: Sends a POST request to the WhatsServer API.

### 2. `send_seen(chat_id, message_id, participant)`
Marks a message as "seen".
- **Parameters**:
  - `chat_id`: The ID of the chat.
  - `message_id`: The ID of the message.
  - `participant`: The participant ID.
- **Usage**: Sends a POST request to the WhatsServer API.

### 3. `typing(chat_id, seconds)`
Simulates typing in a chat.
- **Parameters**:
  - `chat_id`: The ID of the chat.
  - `seconds`: Duration of typing simulation.
- **Usage**: Sends start and stop typing requests to the WhatsServer API.

### 4. `load_allowed_contacts()`
Loads the list of allowed contacts from a file.
- **Returns**: A list of allowed contacts.
- **Usage**: Reads `allowed_contacts.txt` and parses contact information.

### 5. `save_allowed_contacts(contacts)`
Saves the list of allowed contacts to a file.
- **Parameters**:
  - `contacts`: List of contacts to save.
- **Usage**: Writes contact information to `allowed_contacts.txt`.

### 6. `load_config()`
Loads the global configuration from a file.
- **Returns**: A dictionary containing configuration settings.
- **Usage**: Reads `config.txt` and parses key-value pairs.

### 7. `save_config(config)`
Saves the global configuration to a file.
- **Parameters**:
  - `config`: Dictionary containing configuration settings.
- **Usage**: Writes key-value pairs to `config.txt`.

### 8. `get_log_filename(contact)`
Generates the log filename for a specific contact.
- **Parameters**:
  - `contact`: Contact ID.
- **Returns**: Path to the log file.
- **Usage**: Constructs the log file path using the contact ID.

### 9. `reconstruir_historico(contact)`
Reconstructs the conversation history for a contact.
- **Parameters**:
  - `contact`: Contact ID.
- **Returns**: A list of conversation history.
- **Usage**: Reads the log file and extracts the last 5 interactions.

### 10. `responder_whatsapp(mensagem, nome_remetente)`
Generates a response for a WhatsApp message using OpenAI.
- **Parameters**:
  - `mensagem`: The received message.
  - `nome_remetente`: Name of the sender.
- **Returns**: Generated response text.
- **Usage**: Uses OpenAI API to generate a response based on conversation history.

### 11. `index()`
Handles the main configuration interface.
- **Methods**: `GET`, `POST`
- **Usage**: Updates global settings, manages allowed contacts, and displays logs.

### 12. `webhook()`
Processes incoming webhook events.
- **Methods**: `POST`
- **Usage**: Handles incoming messages, checks authorization, and generates responses.

## Notes
- The project uses Flask for web routing and OpenAI for generating responses.
- Configuration and contact management are file-based.
- Logs are stored in JSON format for easy processing.