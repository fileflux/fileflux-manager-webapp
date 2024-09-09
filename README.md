# FileFlux Manager Web Application

## Overview
This is a main Python Flask-based web application designed receive, process and save files from the end users. The application is designed to be deployed in a Kubernetes cluster and uses a CockroachDB Cluster as the backend database for storing information and uses ZFS pools across various Kubernetes worker nodes to store the end-user files. Note that this is the manager application that interacts with the FileFlux Worker Web Application. While the manager receives files from end users and interacts with the CockroachDB Cluster to store some information and forwards user requests to the worker application, the actual processing of files is done by the worker application, using the ZFS pools on various worker nodes in conjunction with the CockroachDB Cluster and it will not work as a standalone application.

## Features
- Allows users to create accounts, create and delete buckets for storing files, upload, access and delete files in their buckets, subject to proper authentication and authorization, leveraging various different methods such as PUT, GET, DELETE, HEAD, POST etc.
- Creates CockroachDB schema for storing user details, bucket details, file details, etc.
- Interacts with CockroachDB Cluster to save various information like user details, bucket details, file details, location on the worker nodes etc.
- Interacts with FileFlux Worker to perform various actions via various Kubernetes services.
- Includes custom readiness and liveness probes for Kubernetes to ensure high availability.
- GitHub Actions CI/CD workflow to build a multi-platform container image and push it to DockerHub.
- Integrated security scanning of the container image using Trivy.

## Prerequisites
To run this application locally or in a container, you need:
- Python 3.11+
- Flask
- CockroachDB Cluster (for database interactions)
- Docker (for containerization)
- Prometheus client library (for metrics)

Install the dependencies locally by running:
```bash
pip install -r requirements.txt
```

## Repository Structure

```plaintext
fileflux-manager-webapp/             
├── Dockerfile              
├── README.md               
├── app.py                  
├── db.py                  
├── liveness.sh             
├── readiness.sh            
├── requirements.txt     
└── schema.py   
```

### What Each File Does
- **docker.yaml**: Contains the GitHub Actions workflow for building and pushing the multi-platform container image to DockerHub and scanning it for vulnerabilities using Trivy.

- **app.py**: The core of the web application. It exposes various endpoints that accepts POST/PUT/GET/DELETE/HEAD requests and forwards them to the FileFlux Worker for processing. It also interacts with the CockroachDB Cluster to store and retrieve information.
  
- **db.py**: Handles database connections, using CockroachDB as the backend database for storing node information.

- **liveness.sh**: A script used for Kubernetes' liveness probe, checking whether the app is running and responsive.

- **readiness.sh**: A script for Kubernetes' readiness probe, ensuring the app is ready to serve requests.

- **requirements.txt**: Specifies the Python dependencies required to run the web application (Flask, PostgreSQL connector, etc.), to be installed while building the container image.

- **Dockerfile**: Configuration for building the web app Docker image. It sets up the necessary Python environment, installs dependencies, and configures health checks.

- **schema.py**: Creates the CockroachDB schema for storing node details, user details, bucket details, file details, etc.

## Building a Docker Image

To build the Docker image for this web app:

1. Clone the repository:
   ```bash
   git clone https://github.com/fileflux/manager-webapp.git
   cd manager-webapp
   ```

2. Build the Docker image:
   ```bash
   docker build -t manager-webapp .
   ```

## Probes

This web app includes Kubernetes health probes:

- **Liveness Probe**: Ensures that the container is still running. If this probe fails, Kubernetes will restart the container.
  ```bash
  ./liveness.sh
  ```

- **Readiness Probe**: Ensures that the app is ready to serve traffic. If this probe fails, Kubernetes will stop sending requests to the container.
  ```bash
  ./readiness.sh
  ```

Both scripts are designed to return appropriate status codes to Kubernetes based on the application’s health.

## GitHub Workflow (including Trivy)

A GitHub Actions workflow is included to automate the build process. The workflow builds a multi-platform container image using Docker for AMD64 and ARM based systems and pushes the image to DockerHub. This workflow also integrates `Trivy`, a vulnerability scanning tool to scan the aforementioned container image, to ensure that it is secure.

This workflow:
1. Checks the code and accesses DockerHub.
2. Builds and pushes multi-platform Docker images for AMD64 and ARM to DockerHub using the Dockerfile in the repository.
3. Runs a security scan on the Docker image using `Trivy`.
4. Logs out from DockerHub.

## Usage

Once the app is running, users can interact with it using the following endpoints:
- /create_user: POST request to create a new user. Example usage: curl -X POST https://s3.lokesh.cloud/create_user -H "Content-Type: application/json" -d '{"username": "test", "password": "test"}'

- /create_bucket/bucket_name: POST request to create a new bucket for an authenticated user. Example usage: curl -X POST https://s3.lokesh.cloud/create_bucket/lokesh_bucket -u test:test

- /delete_bucket/bucket_name: DELETE request to delete a bucket for an authenticated user. Example usage: curl -X DELETE https://s3.lokesh.cloud/delete_bucket/lokesh_bucket -u test:test

- /upload_file/bucket_name/file_name: POST request to upload a file to a bucket for an authenticated user. Example usage: curl -X PUT -F "file=@/local/location/to/file.txt" https://s3.lokesh.cloud/upload/lokesh_bucket/file.txt -u test:test

- /bucket_name/file_name: GET request to download a file from a bucket for an authenticated user. Example usage: curl -X GET https://s3.lokesh.cloud/lokesh_bucket/file.txt -u test:test

- /bucket_name/file_name: HEAD request to validate a file from a bucket for an authenticated user. Example usage: curl -X GET https://s3.lokesh.cloud/lokesh_bucket/file.txt -u test:test

- /bucket_name/file_name: DELETE request to delete a file from a bucket for an authenticated user. Example usage: curl -X DELETE https://s3.lokesh.cloud/lokesh_bucket/file.txt -u test:test

## Additional Notes
- Ensure that the CockroachDB cluster is set up and running before starting the web application. You can modify the database connection in `db.py` to match your configuration.
- The liveness and readiness probes are useful when deploying the app in a Kubernetes environment to ensure high availability.
