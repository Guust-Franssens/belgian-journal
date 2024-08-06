# Use an official mamba base image
FROM mambaorg/micromamba:1.5.8

# Copy the environment.yml file to a temp location
COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml /tmp/environment.yml

# Create a new environment named "venv" based on the environment.yml file
RUN micromamba create -y -n venv -f /tmp/environment.yml && \
    micromamba clean --all --yes

# Set the working directory in the container
WORKDIR /app

# Set the environment variable for activating the environment
ENV PATH /opt/conda/envs/venv/bin:$PATH

# Copy the application files to the working directory
COPY --chown=$MAMBA_USER:$MAMBA_USER . /app/

# Ensure permissions are correct for /app directory
USER root
RUN chown -R $MAMBA_USER:$MAMBA_USER /app

# Set the default shell to bash
SHELL ["/bin/bash", "--login", "-c"]

# Switch back to non-root
USER $MAMBA_USER
