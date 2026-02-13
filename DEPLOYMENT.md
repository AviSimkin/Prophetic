# Deployment Guide

## Prerequisites

- **Python 3.11** (required)
- Git
- API keys (all have free tiers - see README.md)

## Recommended: Streamlit Community Cloud (FREE)

Streamlit apps are best deployed on **Streamlit Community Cloud** which is free and built specifically for Streamlit applications.

### Steps:

1. **Push code to GitHub** (already done ✅)

2. **Go to Streamlit Cloud**: https://streamlit.io/cloud

3. **Connect your GitHub repo**: 
   - Sign in with GitHub
   - Select `AviSimkin/Prophetic`
   - Select branch: `main`
   - Main file: `app.py`
   - Python version: `3.11`

4. **Set environment variables** (all required):
   ```
   GOOGLE_API_KEY=your_gemini_api_key
   TAVILY_API_KEY=your_tavily_key
   SERPAPI_KEY=your_serpapi_key
   OPEN_WEATHER=your_weatherapi_key
   GEMINI_MODEL=gemini-2.5-flash-lite
   ```

5. **Deploy!** - Streamlit Cloud will:
   - Install from `requirements.txt`
   - Run `app.py`
   - Provide a public URL (e.g., `prophetic.streamlit.app`)

---

## Alternative: Docker + Any Cloud Provider

If you need more control or want to deploy elsewhere (Railway, Render, Fly.io):

### Dockerfile:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Deploy to:
- **Railway**: Connect GitHub, auto-detects Dockerfile
- **Render**: Web Service from repo, Docker environment
- **Fly.io**: `flyctl launch`

---

## Why Not Vercel?

Vercel is optimized for:
- Static sites
- Serverless functions (short-lived)
- API routes

Streamlit requires:
- ✗ WebSocket connections (Vercel has limited support)
- ✗ Long-running Python process (Vercel functions time out)
- ✗ Server-side state management (Vercel is stateless)

**Result**: Streamlit on Vercel requires complex workarounds and doesn't work reliably.

---

## Recommended Path

1. Use **Streamlit Community Cloud** for free hosting
2. If you need custom domain/more resources, use **Railway** or **Render** with Docker
3. Only use Vercel if you convert to a REST API backend + React/Next.js frontend
