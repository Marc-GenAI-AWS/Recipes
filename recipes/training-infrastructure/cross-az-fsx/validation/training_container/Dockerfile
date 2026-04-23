# Dockerfile for FSx Cross-AZ Validation Training Container
# This is a simple validation container to test cross-AZ FSx access

FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    nfs-common \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --no-cache-dir \
    boto3 \
    numpy \
    pandas

# Copy training script
COPY train.py /opt/ml/code/train.py
COPY validate_fsx_access.py /opt/ml/code/validate_fsx_access.py

# Set working directory
WORKDIR /opt/ml/code

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV SAGEMAKER_PROGRAM=train.py

# Entry point
ENTRYPOINT ["python", "train.py"]
