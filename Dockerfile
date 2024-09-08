FROM python:3.11-slim AS build
COPY requirements.txt requirements.txt
RUN pip install --upgrade pip && pip uninstall -y setuptools && pip install setuptools>=70.0.0
RUN pip install -r requirements.txt

FROM python:3.11-slim
RUN apt-get update && apt-get install -y \
    postgresql-client \
    nano \
    dos2unix \
    procps 
COPY --from=build /usr/local /usr/local
WORKDIR /app
COPY . .
COPY readiness.sh /usr/local/bin/readiness.sh
COPY liveness.sh /usr/local/bin/liveness.sh

RUN apt-get update && apt-get install -y dos2unix && \
    dos2unix /usr/local/bin/readiness.sh /usr/local/bin/liveness.sh && \
    chmod +x /usr/local/bin/readiness.sh /usr/local/bin/liveness.sh && \
    chmod +x app.py

CMD ["python", "app.py"]
