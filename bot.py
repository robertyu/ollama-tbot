import os
import sys
import json
import logging
import asyncio
from logging.handlers import RotatingFileHandler
from telethon import TelegramClient, events
from ollama_access import OllamaClient
from functools import wraps

# Load configuration
CONFIG_FILE = 'config/config.json'

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

config = load_config()
# Set up logging
MAIN_LOG_FILE = config.get('log_path', 'logs/bot.log')
logger = logging.getLogger(__name__)
handler = RotatingFileHandler(MAIN_LOG_FILE, maxBytes=15*1024*1024, backupCount=1)
handler.setFormatter(logging.Formatter('"%(asctime)s", %(message)s', "%Y-%m-%d %H:%M:%S"))
logger.addHandler(handler)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)
HISTORY_LOG_FILE = config.get('log_path', 'logs/bot.log').replace('bot.', 'history.')
h_logger = logging.getLogger(__name__)
h_handler = RotatingFileHandler(MAIN_LOG_FILE, maxBytes=15*1024*1024, backupCount=1)
h_handler.setFormatter(logging.Formatter('"%(asctime)s", %(message)s', "%Y-%m-%d %H:%M:%S"))
h_logger.addHandler(h_handler)
h_logger.setLevel(logging.DEBUG)

# Initialize Telegram client
bot = TelegramClient('bot', api_id=config['api_id'], api_hash=config['api_hash'])
bot_info = None
# Initialize Ollama client
ollama_client = OllamaClient(logger=logger, config=config)

# In-memory user data
ADMIN_USER_IDS = config.get('admin_user_ids', [])

# decorator for permission
def require_permission(func):
    @wraps(func)
    async def wrapper(event, *args, **kwargs):
        sender = await event.get_sender()
        logger.debug(f'sender: {sender}')
        user_id = sender.id
        if user_id in ADMIN_USER_IDS:
            return await func(event, *args, **kwargs) 
        else:
            await event.respond("yo yo, no permission!")
    
    return wrapper


@require_permission
@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    global logger
    chat_id = event.chat_id
    help_str = f'Your chat ID: {chat_id}\nUse /list_ollama_servers to display available servers.\nUse /add_ollama_server to add the Ollama server.\nUse /delete_ollama_server to remote the Ollama server.'
    help_str += '\nUse /set_default_server <server_url> to set a default Ollama server for this chat.'
    help_str += '\nUse /get_models <server_url> to get models from the Ollama server.'
    help_str += '\nUse set_model <model_name> to set a model for this chat.'
    await event.respond(help_str)
    logger.debug(f'/start command received from {chat_id}')


@require_permission
@bot.on(events.NewMessage(pattern='/list_ollama_servers'))
async def list_ollama_servers(event):
    global logger
    servers = config.get('ollama_servers', [])
    if not servers:
        await event.respond('No Ollama servers configured.')
        return
    server_info = '\n'.join([f'{i+1}. {server["url"]} - {server["default_model"]} [TOKEN: {server["header_token"]}]' for i, server in enumerate(servers)])
    await event.respond(f'Available Ollama servers:\n{server_info}')
    logger.debug(f'List of Ollama servers requested by {event.chat_id}')


@require_permission
@bot.on(events.NewMessage(pattern='/add_ollama_server'))
async def set_ollama_server(event):
    global logger
    args = event.message.text.split()
    if len(args) != 2:
        await event.respond('Usage: /add_ollama_server {url, default_model,header_token}')
        return
    try:
        server_data = json.loads(args[1])
        if not isinstance(server_data, dict):
            await event.respond('Invalid JSON format for server data.')
            return
        if 'url' not in server_data or 'default_model' not in server_data or 'header_token' not in server_data:
            await event.respond('Invalid JSON format for server data.')
            return
        config['ollama_servers'].append(server_data)
        save_config(config)
        await event.respond(f'Ollama server added successfully.')
        logger.debug(f'Ollama server added: {server_data}')
    except json.JSONDecodeError:
        await event.respond('Invalid JSON format for server data.')
        return


@require_permission
@bot.on(events.NewMessage(pattern='/delete_ollama_server'))
async def delete_ollama_server(event):
    global logger
    args = event.message.text.split()
    if len(args) != 2:
        await event.respond('Usage: /delete_ollama_server <server_url>')
        return
    try:
        server_url = args[1]
        logger.debug(f'delete_ollama_servers server_url: server_url: {server_url}')
        if server_url not in [server['url'] for server in config['ollama_servers']]:
            await event.respond('Server URL not found.')
            return
        config['ollama_servers'] = [server for server in config['ollama_servers'] if server['url'] != server_url]
        save_config(config)
        await event.respond(f'Ollama server {server_url} removed successfully.')
        logger.debug(f'Ollama server removed: {server_url}')
    except Exception as e:
        await event.respond(f'Error deleting Ollama server: {e}')
        logger.error(f'Error deleting Ollama server: {e}')


@require_permission
@bot.on(events.NewMessage(pattern='/set_default_server'))
async def set_default_server(event):
    global logger
    args = event.message.raw_text.split()
    if len(args) != 2:
        await event.respond('Usage: /set_default_server <server_url>')
        return
    try:
        server_url = args[1]
        logger.debug(f'set_default_server server_url: server_url: {server_url}')
        if server_url not in [server['url'] for server in config['ollama_servers']]:
            await event.respond('Server URL not found.')
            return
        for server in config['ollama_servers']:
            if server['url'] == server_url:
                models = await ollama_client.get_models(server_url)
                if 'error' in models:
                    logger.error(f'Error getting models: {models["error"]} from {server_url}')
                    await event.respond(f'The server {server_url} could not access right now')
                    return
                config['default_server'] = server_url
                save_config(config)
                logger.info(f'Default server set to: {server_url}')
                await event.respond(f'Default server set to: {server_url}')
                break
    except Exception as e:
        logger.error(f'Error setting default server: {e}')
        await event.respond('An error occurred while setting the default server.')


@bot.on(events.NewMessage(pattern='/get_models'))
async def get_models(event):
    global logger
    args = event.message.text.split()
    if len(args) != 2:
        await event.respond('Usage: /get_models <server_url>')
        return
    try:
        server_url = args[1]
        if server_url not in [server['url'] for server in config['ollama_servers']]:
            await event.respond('Server URL not found.')
            return
        models = await ollama_client.get_models(server_url)
        if 'error' in models:
            logger.error(f'Error getting models: {models["error"]}')
            await event.respond(f'Error getting models: {models["error"]}, details: {models["details"]}')
            return
        logger.debug(f'Models: {models} requested by {event.chat_id}')
        await event.respond(f'Models: {'\n'.join([model['name'] + '-' + model['model'] for model in models['models']])}')
    except Exception as e:
        logger.error(f'Error getting models: {e}')
        await event.respond(f'Error getting models: {e}')


@bot.on(events.NewMessage(pattern='/set_model'))
async def set_model(event):
    global logger
    args = event.message.text.split()
    if len(args) != 3:
        await event.respond('Usage: /set_model <server_url> <model_name>')
        return
    try:
        server_url = args[1]
        model_name = args[2]
        if server_url not in [server['url'] for server in config['ollama_servers']]:
            await event.respond('Server URL not found.')
            return
        server = [server for server in config['ollama_servers'] if server['url'] == server_url][0]
        models = await ollama_client.get_models(server_url)
        if 'error' in models:
            logger.error(f'Error getting models: {models["error"]}')
            await event.respond(f'Error getting models: {models["error"]}, details: {models["details"]}')
            return
        logger.debug(f'Models: {models} requested by {event.chat_id}')
        if model_name not in [model['name'] for model in models['models']]:
            logger.error(f'Model {model_name} not found.')
            await event.respond(f'Model {model_name} not found.')
            return
        server['default_model'] = model_name
        config['ollama_servers'] = [server for server in config['ollama_servers'] if server['url'] != server_url]
        config['ollama_servers'].append(server)
        save_config(config)
        await event.respond(f'Model set to {model_name} for {server_url}')
        logger.debug(f'Model set to {model_name} for {server_url}')
    except Exception as e:
        logger.error(f'Error setting model: {e}')
        await event.respond(f'Error setting model: {e}')


@bot.on(events.NewMessage)
async def handle_message(event):
    global logger
    global h_logger
    global bot_info
    chat_id = str(event.chat_id)
    sender = await event.get_sender()
    message = event.message.message
    print(f"Message from {sender.username}: {message}")
    if message.startswith('/'):
        logger.debug(f'Ignoring command {message} from {chat_id}')
        return  # Ignore other commands

    h_logger.debug(f'NewMessage event.is_group: {event.is_group}, id: {chat_id}, sender: {sender}, event.mentioned: {event.mentioned}')
    if not bot_info:
        bot_info = await bot.get_me()
    # async for response in ollama_client.generate_response(model, default_prompt):
    #     logger.debug(f'response: {response}, type: {type(response)}')
    #     await event.respond(response)
    if event.mentioned and event.is_group:  # Only respond to mentions in private chats
        print(f'bot_info.username: {bot_info.username}')
        input_msg = message.replace(f'@{bot_info.username}', '')
        response = await ollama_client.generate_response(input_msg)
        if 'error' in response:
            logger.error(f'Error generating response: {response["error"]}, details: {response["details"]}')
            await event.respond(response['error'])
        await event.reply(response['response'])
    else:
        response = await ollama_client.generate_response(message)
        if 'error' in response:
            logger.error(f'Error generating response: {response["error"]}, details: {response["details"]}')
            await event.respond(response['error'])
        await event.reply(response['response'])


def main():
    bot.start(bot_token=config['bot_token'])
    logger.info('Bot started')
    asyncio.get_event_loop().run_forever()

if __name__ == '__main__':
    main()
