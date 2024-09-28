```
docker build -t ollama-tbot .
```

```
docker run -d --name otbot --restart always\
  -v /path/logs:/app/logs \
  -v /path/config:/app/config \
  ollama-tbot
```