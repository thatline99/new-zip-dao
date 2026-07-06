FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# 워크스페이스 매니페스트 + 패키지 소스만 복사 (.env·data 는 .dockerignore 로 제외)
COPY pyproject.toml uv.lock ./
COPY packages ./packages

# 락파일 그대로 의존성 설치 (dev 제외)
RUN uv sync --frozen --no-dev

# 공고 데이터는 런타임 볼륨으로 마운트한다 (API 는 $DATA_DIR/raw 를 읽음)
ENV DATA_DIR=/data
EXPOSE 8080

CMD ["uv", "run", "--frozen", "--no-dev", "uvicorn", "zipdao_api.app:app", "--host", "0.0.0.0", "--port", "8080"]
