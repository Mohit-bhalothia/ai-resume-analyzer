# Docker Deployment

## Push to Docker Hub (mohitbhalothia007)

```bash
# 1. Log in to Docker Hub (enter your password when prompted)
docker login

# 2. Build the image with your Docker Hub username
docker build -t mohitbhalothia007/ai-resume-analyzer:latest .

# 3. Push to Docker Hub
docker push mohitbhalothia007/ai-resume-analyzer:latest
```

Image will be available at: **https://hub.docker.com/r/mohitbhalothia007/ai-resume-analyzer**

Anyone can run it with:
```bash
docker run -p 8000:8000 mohitbhalothia007/ai-resume-analyzer
```

---

## Quick start (local)

```bash
# Build and run with docker-compose
docker-compose up --build

# Or build and run with Docker directly
docker build -t ai-resume-analyzer .
docker run -p 8000:8000 ai-resume-analyzer
```

The app will be available at **http://localhost:8000**

- Dashboard: http://localhost:8000/dashboard
- API docs: http://localhost:8000/docs

## Production tips

1. **Environment variables**: Create a `.env` file or pass env vars for production:
   ```bash
   docker run -p 8000:8000 -e JWT_SECRET_KEY=your-secret ai-resume-analyzer
   ```

2. **Custom port**: Change the port mapping:
   ```bash
   docker run -p 8080:8000 ai-resume-analyzer
   ```

3. **First run**: The first request may take a few seconds while the model loads.
