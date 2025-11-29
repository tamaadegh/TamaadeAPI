FROM python:3.10.2-slim-bullseye

ENV PIP_DISABLE_PIP_VERSION_CHECK 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PORT=8000

WORKDIR /code

COPY ./requirements.txt .

RUN apt-get update -y && \
    apt-get install -y netcat dos2unix && \
    pip install --upgrade pip && \
    pip install -r requirements.txt


# Ensure entrypoint script uses LF on runtime and make it executable
COPY . .

# Install a wrapper outside /code so we are not affected by bind mounts
COPY entrypoint_wrapper.sh /usr/local/bin/entrypoint_wrapper.sh

RUN sed -i 's/\r$//' /code/entrypoint.sh || true && \
    chmod +x /code/entrypoint.sh || true && \
    sed -i 's/\r$//' /usr/local/bin/entrypoint_wrapper.sh || true && \
    chmod +x /usr/local/bin/entrypoint_wrapper.sh || true

ENTRYPOINT ["/usr/local/bin/entrypoint_wrapper.sh"]
EXPOSE 8000
CMD ["sh", "-lc", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --log-level info --access-logfile - --error-logfile -"]
