# NOTES

Run the container with own keypair ane inventory file from cmd:

```bash
docker run -v ~/.ssh/id_rsa:/root/.ssh/id_rsa:ro -v ~/.ssh/id_rsa.pub:/root/.ssh/id_rsa.pub:ro -v ./inventory/all.yaml:/ansible/inventory.yaml -e INVENTORY_PATH=/etc/ansible/inventory.yaml --network=host  host_inspector_test 
```