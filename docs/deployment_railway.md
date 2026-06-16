# 🚂 Deploying Your RAG Assistant to Railway

This guide outlines how to deploy your RAG Assistant to **Railway**. 

Because Railway's free/hobby tier limits resources, we provide two deployment options:
1. **Monolithic Deployment (Recommended)**: Serves both the Frontend and Backend from a **single unified container**. Highly recommended for free tiers as it uses exactly **one service** and removes all CORS configurations.
2. **Split Deployment**: Runs the Frontend (Nginx) and Backend (FastAPI) as separate services.

---

## 🛠️ Prerequisites
- A [Railway account](https://railway.app)
- A GitHub repository containing your codebase
- A Gemini API key from [Google AI Studio](https://aistudio.google.com)

---

## 🚀 Option 1: Monolithic Deployment (Single Service — Recommended)

This option compiles the React app and copies it into the FastAPI container. FastAPI handles both the API requests (under `/api`) and serves the React dashboard (under `/`).

### 1. Create the Railway Service
1. Go to your [Railway Dashboard](https://railway.app/dashboard) and click **New Project** -> **Deploy from GitHub repo**.
2. Select your repository.
3. Click **Configure Service** before deploying:
   - **Service Name**: Rename it to `rag-assistant`.
   - **Root Directory**: Leave this empty `/` (it will use the root `Dockerfile`).
4. Add the following **Environment Variables** in the variables tab:
   - `GEMINI_API_KEY`: `your-gemini-api-key`
   - `PRIMARY_LLM`: `gemini`
   - `PORT`: `8000` *(Railway injects this dynamically, but setting a default is safe)*
5. Click **Deploy**.

### 2. Enable Persistent Storage (Important for ChromaDB)
Because ChromaDB stores vector indices on disk (`/app/data`), deploying to a standard ephemeral container means your uploaded documents will disappear whenever the container restarts.
To persist your data:
1. In your `rag-assistant` service, go to **Settings** -> **Volumes** -> **Add Volume**.
2. Mount the volume at `/app/data`.
This keeps all uploaded files, SQLite session history, and BM25 indices safe between deployments and restarts!

### 3. Generate Public Domain
1. Go to the service's **Settings** tab.
2. Under **Networking**, click **Generate Domain**.
3. Open this domain in your browser. You will see the React dashboard load, and it will communicate with the API relative to this same domain.

---

## 📦 Option 2: Split Service Deployment (Advanced)

If you prefer to separate concerns and run the services independently, follow these steps:

### 1. Deploy the Backend Service (FastAPI)
1. In your project, click **New** -> **GitHub Repo** and select your repository.
2. Configure the service:
   - **Service Name**: `rag-backend`
   - **Root Directory**: Set to `/backend` (it will use `/backend/Dockerfile`).
3. Add **Environment Variables**:
   - `GEMINI_API_KEY`: `your-gemini-api-key`
   - `CORS_ORIGINS`: `["*"]` *(or your frontend URL once generated)*
   - `PORT`: `8000`
   - `PRIMARY_LLM`: `gemini`
4. Attach a **Volume** mounted at `/app/data` to persist vector data.
5. In **Settings** -> **Networking**, click **Generate Domain** and copy it.

### 2. Deploy the Frontend Service (React + Vite)
1. In the same project, click **New** -> **GitHub Repo** and select the same repository.
2. Configure the service:
   - **Service Name**: `rag-frontend`
   - **Root Directory**: Set to `/frontend` (it will use `/frontend/Dockerfile` with Nginx).
3. Add **Environment Variables**:
   - `VITE_API_URL`: Set this to the backend domain you generated in Step 1 (e.g. `https://rag-backend-production.up.railway.app`).
4. Click **Deploy** and **Generate Domain** under the frontend service settings.
