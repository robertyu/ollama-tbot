import aiohttp
import asyncio
import traceback


class OllamaClient:
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config

    async def generate_response(self, prompt, suffix=None, images=None):
        """_summary_

        Args:
            model (_type_): (required) the model name
            history (_type_): _description_
            prompt (_type_): the prompt to generate a response for
            suffix (_type_): the text after the model response
            images (_type_, optional): (optional) a list of base64-encoded images (for multimodal models such as llava). Defaults to None.
            options: additional model parameters listed in the documentation for the Modelfile such as temperature.
            stream (bool, optional): (optional) if true the response will be returned as a stream of objects, rather than a single response object. Defaults to False.
        Yields:
            _type_: _description_
        """
        if images:
            if suffix:
                payload = {'model': None,'prompt': prompt, 'suffix': suffix, 'images': images, 'stream': False}
            else:
                payload = {'model': None,'prompt': prompt, 'images': images, 'stream': False}
        else:
            if suffix:
                payload = {'model': None,'prompt': prompt, 'suffix': suffix, 'stream': False}
            else:
                payload = {'model': None,'prompt': prompt, 'stream': False}

        # payload['prompt'] = 'If the question is beyond your knowledge range, or if you do not understand the question, please respond with the equivalent phrase for ‘I don’t know’ in the corresponding language. and then response the normal response ' + payload['prompt']
        # format: the format to return a response in. Currently the only accepted value is json
        # options: additional model parameters listed in the documentation for the Modelfile such as temperature
        # system: system message to (overrides what is defined in the Modelfile)
        # template: the prompt template to use (overrides what is defined in the Modelfile)
        # context: the context parameter returned from a previous request to /generate, this can be used to keep a short conversational memory
        # stream: if false the response will be returned as a single response object, rather than a stream of objects
        # raw: if true no formatting will be applied to the prompt. You may choose to use the raw parameter if you are specifying a full templated prompt in your request to the API
        # keep_alive: controls how long the model will stay loaded into memory following the request (default: 5m)
        self.logger.debug(f'payload: {payload}')
        if 'default_server' in self.config and self.config['default_server'] is not None:
            default_server_url = self.config['default_server']
            for server in self.config.get('ollama_servers'):
                if server['url'] == default_server_url:
                    try:
                        headers = {'Authorization': f'Bearer {server['header_token']}'} if server['header_token'] else {}
                        payload['model'] = server['default_model']
                        url = f"{server['url']}/api/generate"
                        async with aiohttp.ClientSession(headers=headers, trust_env=True) as session:
                            async with session.post(url, json=payload) as resp:
                                self.logger.info(f'Response: {await resp.text()}')
                                if resp.status != 200:
                                    self.logger.error(f'Error generating response from {server}: {await resp.text()}')
                                self.logger.debug(f'access server: {server}')
                                return await resp.json()
                    except Exception as e:
                        self.logger.error(f'Error generating response from {server}: {e}, {traceback.format_exc()}')

        for server in self.config.get('ollama_servers'):
            try:
                headers = {'Authorization': f'Bearer {server['header_token']}'} if server['header_token'] else {}
                payload['model'] = server['default_model']
                url = f"{server['url']}/api/generate"
                async with aiohttp.ClientSession(headers=headers, trust_env=True) as session:
                    async with session.post(url, json=payload) as resp:
                        self.logger.info(f'Response: {await resp.text()}')
                        if resp.status != 200:
                            self.logger.error(f'Error generating response from {server}: {await resp.text()}')
                            continue
                        self.logger.debug(f'access server: {server}')
                        return await resp.json()
            except Exception as e:
                self.logger.error(f'Error generating response from {server}: {e}, {traceback.format_exc()}')
                continue
        return {'error': 'Error generating response from any Ollama server.', 'details': 'No response from any Ollama server.'}

    async def get_models(self, server_url):
        try:
            server = [s for s in self.config.get('ollama_servers') if s['url'] == server_url][0]
            url = f'{server['url']}/api/tags'
            headers = {'Authorization': f'Bearer {server['header_token']}'} if server['header_token'] else {}
            async with aiohttp.ClientSession(headers=headers, trust_env=True) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        self.logger.debug(f'get_models response: {await resp.text()}')
                        return {'error': 'Error communicating with Ollama.', 'details': await resp.text()}
                    models = await resp.json()
                    return models
        except Exception as e:
            self.logger.error(f'Error getting models from {server}: {e}, {traceback.format_exc()}')
            return {'error': 'Error getting models from Ollama.', 'details': e}
        
