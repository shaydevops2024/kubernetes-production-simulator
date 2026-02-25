FROM python:3.11-slim

USER root

# Java is required to run Spark; procps provides ps (used by spark-submit)
RUN apt-get update && apt-get install -y \
    default-jdk-headless \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV PYSPARK_PYTHON=python3

# Install Python dependencies (pyspark brings spark-submit)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Download extra JARs for Kafka + PostgreSQL connectors
RUN mkdir -p /opt/spark-jars && \
    curl -fsSL -o /opt/spark-jars/spark-sql-kafka-0-10_2.12-3.5.1.jar \
    https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.1/spark-sql-kafka-0-10_2.12-3.5.1.jar && \
    curl -fsSL -o /opt/spark-jars/kafka-clients-3.4.0.jar \
    https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.4.0/kafka-clients-3.4.0.jar && \
    curl -fsSL -o /opt/spark-jars/postgresql-42.7.3.jar \
    https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.3/postgresql-42.7.3.jar && \
    curl -fsSL -o /opt/spark-jars/spark-token-provider-kafka-0-10_2.12-3.5.1.jar \
    https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.1/spark-token-provider-kafka-0-10_2.12-3.5.1.jar && \
    curl -fsSL -o /opt/spark-jars/commons-pool2-2.11.1.jar \
    https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar

COPY . /app/

WORKDIR /app

# spark-submit is installed by pyspark at /usr/local/bin/spark-submit
CMD ["spark-submit", \
     "--master", "local[*]", \
     "--jars", "/opt/spark-jars/spark-sql-kafka-0-10_2.12-3.5.1.jar,/opt/spark-jars/kafka-clients-3.4.0.jar,/opt/spark-jars/postgresql-42.7.3.jar,/opt/spark-jars/spark-token-provider-kafka-0-10_2.12-3.5.1.jar,/opt/spark-jars/commons-pool2-2.11.1.jar", \
     "--conf", "spark.sql.shuffle.partitions=4", \
     "main.py"]
