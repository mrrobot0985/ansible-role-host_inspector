FROM alpine:latest

# Install system dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    openssh-client \
    curl

# Install ansible inside a virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Upgrade pip within the virtual environment
RUN pip install --upgrade pip

# Install ansible from PyPI
RUN pip install ansible

# Create a dedicated directory for Ansible roles and files
RUN mkdir -p /ansible

# Copy the current directory (where the Dockerfile resides) to /ansible
COPY . /ansible

# Copy necessary Ansible configuration files and the playbook
COPY ansible.cfg /etc/ansible/ansible.cfg
COPY playbook.yml /etc/ansible/playbook.yml
COPY tests/inventory /etc/ansible/inventory

# Copy the entrypoint script and make it executable
COPY entrypoint.sh /ansible/entrypoint.sh
RUN chmod +x /ansible/entrypoint.sh

# Set the entrypoint to the custom script
ENTRYPOINT ["/ansible/entrypoint.sh"]
