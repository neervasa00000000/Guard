FROM guard-e1-review4 AS python_runtime

# Trixie supplies LibreOffice 25.2 and Poppler 25.03. It can run the
# review4 Python interpreter and wheels built on the older Debian base.
FROM debian:trixie-slim
COPY --from=python_runtime /usr/local /usr/local
RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-writer poppler-utils \
       fontconfig libfribidi0 libraqm0 libharfbuzz0b libfreetype6 libexpat1 libssl3t64 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN ldconfig && python -m pip install --no-cache-dir pymupdf==2.1
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
