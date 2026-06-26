# topic-pipeline — CPU 기반 이미지. 빌드: docker build -t topic-pipeline .
# 실행 예: docker run --rm -v "$PWD:/work" -w /work topic-pipeline --help
FROM python:3.12-slim

WORKDIR /app
COPY . /app

# torch/bertopic 등 무거운 의존성 포함 (CPU). 빌드 5~15분.
RUN pip install --no-cache-dir -e .

# API 키는 런타임 -e 로 주입 (이미지에 굽지 않음):
#   docker run --rm -e ANTHROPIC_API_KEY=... -v "$PWD:/work" -w /work topic-pipeline
ENTRYPOINT ["topic-pipeline"]
CMD ["--help"]
