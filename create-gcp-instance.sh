#!/bin/bash
# Based on my Cloud Computing homework WS23
# This script creates three Ubuntu VMs with different configurations for benchmarking.
# It assumes the correct default project is set in the shell.

#VM parameters
IMAGE="ubuntu-2204-jammy-v20231030"
IMAGE_PROJECT="ubuntu-os-cloud"
MACHINE_TYPE="n1-standard-4"
BOOT_DISK_SIZE="100GB"
TAG="cc"
REGION="europe-west1"
ZONE="europe-west1-b"

# Setting default region/zone
gcloud config set compute/region $REGION
echo Set compute region to $REGION
gcloud config set compute/zone $ZONE
echo Set compute zone to $ZONE

# Generate ssh-key pair and add to project metadata
# WILL OVERWRITE EXISTING SSH KEYS NAMED id_rsa IN DEFAULT DIRECTORY WITHOUT USER PROMPT
ssh-keygen -q -t rsa -C ubuntu -N '' -f ~/.ssh/id_rsa <<< $'y\n'

# create public key file to upload (formatted username:public_key)
echo -n $(cut ~/.ssh/id_rsa.pub -f 3 -d " ") > project_ssh_file
echo -n ":" >> project_ssh_file
echo -n $(cut ~/.ssh/id_rsa.pub -f 1,2 -d " ") >> project_ssh_file

# push file to cloud metadata
gcloud compute project-info add-metadata --metadata-from-file=ssh-keys=project_ssh_file

# cleanup file
rm project_ssh_file

# Create netwok rules to allow ssh and icmp for cc tagged instances only
# ssh connections
gcloud compute firewall-rules create cc-allow-ssh \
    --action=ALLOW \
    --direction=INGRESS \
    --network=default \
    --priority=1000 \
    --rules=tcp:22 \
    --source-ranges=0.0.0.0/0 \
    --target-tags $TAG
gcloud compute firewall-rules create cc-allow-mqtt \
    --action=ALLOW \
    --direction=INGRESS \
    --network=default \
    --priority=1000 \
    --rules=tcp:1883 \
    --source-ranges=0.0.0.0/0 \
    --target-tags $TAG
gcloud compute firewall-rules create cc-allow-icmp \
    --action=ALLOW \
    --direction=INGRESS \
    --network=default \
    --priority=1000 \
    --rules=icmp \
    --source-ranges=0.0.0.0/0 \
    --target-tags $TAG


INSTANCE_NAME="n1"
# Create the VM with parameters by iterating over MACHINE_TYPES
  gcloud compute instances create ${INSTANCE_NAME} \
      --machine-type=${MACHINE_TYPE} \
      --image=$IMAGE \
      --image-project=$IMAGE_PROJECT \
      --tags=$TAG \
      --boot-disk-size=$BOOT_DISK_SIZE \
      --enable-nested-virtualization

# Get VM IP and ssh into it
PUBLIC_IP=$(gcloud compute instances describe ${INSTANCE_NAME} \
  --format="value(networkInterfaces[0].accessConfigs[0].natIP)")

# wait for VM to be ready
ssh-keyscan $PUBLIC_IP >> ~/.ssh/known_hosts
while test $? -gt 0
do
  sleep 5
  echo SSH not ready...
  ssh-keyscan $PUBLIC_IP >> ~/.ssh/known_hosts
done

ssh -i ~/.ssh/id_rsa ubuntu@${PUBLIC_IP}
while test $? -gt 0
do
  sleep 5
  echo SSH not ready...
  ssh -i ~/.ssh/id_rsa ubuntu@${PUBLIC_IP}
done

# Install necessary packages
sudo apt update -y
sudo apt upgrade -y
sudo apt-get install curl gnupg2 wget git apt-transport-https ca-certificates -y
sudo apt-get install mosquitto
sudo systemctl restart mosquitto