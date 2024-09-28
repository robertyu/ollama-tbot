```
docker build -t telegram-ollama-bot .
```

```
docker run -d \
  -v /path/to/logs:/app/logs \
  -v /path/to/config.json:/app/config.json \
  telegram-ollama-bot
```