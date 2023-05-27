FROM python:3.9-slim

# Install Docker CLI dependencies
RUN apt-get update && apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Install Docker CLI
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian \
    $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
RUN apt-get update && apt-get install -y docker-ce-cli

ENV PYTHONPATH=./nginx-controller-common
COPY nginx-controller-common ./nginx-controller-common
COPY nginx-controller-agent/utils ./nginx-controller-agent/utils
COPY nginx-controller-agent/run.py ./nginx-controller-agent/run.py
COPY nginx-controller-agent/requirements.txt ./nginx-controller-agent/requirements.txt
RUN pip install --no-cache-dir -r ./nginx-controller-agent/requirements.txt

CMD python ./nginx-controller-agent/run.py