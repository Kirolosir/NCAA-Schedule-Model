FROM node:24-bookworm-slim AS frontend
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY npi_model/ ./npi_model/
COPY tests/data/ncaa_2022_historical_division.json ./tests/data/ncaa_2022_historical_division.json
COPY tests/data/ncaa_2023_historical_division.json ./tests/data/ncaa_2023_historical_division.json
COPY tests/data/ncaa_2024_10_27_division.json ./tests/data/ncaa_2024_10_27_division.json
COPY tests/data/ncaa_2025_11_09_division.json ./tests/data/ncaa_2025_11_09_division.json
COPY tests/data/historical_probability_models.json ./tests/data/historical_probability_models.json
COPY gunicorn.conf.py ./
COPY --from=frontend /build/web/dist/client/ ./web/dist/client/
USER 10001:10001
EXPOSE 10000
CMD ["gunicorn", "--config", "gunicorn.conf.py", "npi_model.hosted_app:create_app()"]
