FROM python:3.6-alpine as base
FROM base as builder

# Get Dependencies
COPY ./requirements.txt /
RUN pip install --install-option="--prefix=/install" -r /requirements.txt

# Set python path to include dependencies and src code
ENV PYTHONPATH=/src:/install/lib/python3.6/site-packages:$PYTHONPATH

COPY ddf_exporter.py /src/ddf_exporter.py
COPY test/test_ddf_exporter.py /src/test_ddf_exporter.py
RUN dos2unix /src/*
RUN chmod 755 /src/*.py
RUN python -m unittest /src/test_ddf_exporter.py

# Build the production image
FROM base

COPY --from=builder /install /usr/local
COPY --from=builder /src/ddf_exporter.py /app/
RUN ln -s /app/ddf_exporter.py /usr/local/bin/ddf-exporter
RUN chmod 755 /usr/local/bin/ddf-exporter

ENTRYPOINT ["ddf-exporter"]

