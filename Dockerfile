FROM python:3.12-slim

# Install system libs needed for headless Chromium + Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1 libasound2 \
    libatspi2.0-0 libxshmfence1 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libpango-1.0-0 libcairo2 libcups2 libdbus-1-3 libxext6 libx11-6 \
    fonts-liberation libappindicator3-1 libgdk-pixbuf2.0-0 libnspr4 libx11-xcb1 \
    libxcursor1 libxi6 libxrender1 libxtst6 xdg-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .

EXPOSE 8080

CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
