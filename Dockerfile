FROM python:3.11.9-slim

WORKDIR /app

# setup Azure CLI
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    curl -sL https://aka.ms/InstallAzureCLIDeb | bash && \
    apt-get remove -y curl && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /app/

# Ensure permissions are correct for /app directory
RUN chown -R nobody:nogroup /app && \
    chmod -R 755 /app

# Set the user to 'nobody' for better security
USER nobody