FROM python:3.12-slim-bookworm
RUN apt-get update \
    && apt-get install -y --no-install-recommends libraqm0 libfribidi0 libharfbuzz0b libfreetype6 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pillow==12.3.0 numpy==2.5.4 pandas==3.1.1
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
