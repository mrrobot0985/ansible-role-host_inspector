#!/bin/sh

# Default values if environment variables are not set
INVENTORY="${INVENTORY:-inventory}"
PLAYBOOK="${PLAYBOOK:-playbook.yml}"

# Function to log messages
log() {
    echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')]: $1"
}

# # Check if inventory file exists
# if[ ! -f "/etc/ansible/$INVENTORY" ]; then
#     log "Inventory file $INVENTORY not found."
#     exit 1
# fi

# # Check if playbook exists
# if[ ! -f "/etc/ansible/$PLAYBOOK" ]; then
#     log "Playbook $PLAYBOOK not found."
#     exit 1
# fi

# Log the execution details
log "Running Ansible Playbook: ${PLAYBOOK} with Inventory: ${INVENTORY}"

# Execute the ansible-playbook command
ansible-playbook -i "/etc/ansible/$INVENTORY" "/etc/ansible/$PLAYBOOK"