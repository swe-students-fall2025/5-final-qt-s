# Roommate Management System
[![API CI/CD](https://github.com/swe-students-fall2025/5-final-qt-s/actions/workflows/api.yml/badge.svg?branch=main)](https://github.com/swe-students-fall2025/5-final-qt-s/actions/workflows/api.yml)
[![Service CI/CD](https://github.com/swe-students-fall2025/5-final-qt-s/actions/workflows/service.yml/badge.svg?branch=main)](https://github.com/swe-students-fall2025/5-final-qt-s/actions/workflows/service.yml)

## Live Deployment

**API Service:** http://159.65.178.253:8000

The application is automatically deployed to Digital Ocean via GitHub Actions CI/CD pipeline when changes are pushed to the `main` branch.

## Introduction

The Roommate Management System is a comprehensive web application designed to help roommates and shared living groups manage their household responsibilities efficiently. The platform provides tools for tracking chores, managing rent and bills, monitoring household supplies, and coordinating schedules through an integrated calendar view.

The system is built with a microservices architecture, consisting of a main API service that handles user interactions and a separate service layer for business logic and recommendations. All data is stored in a MongoDB database, ensuring scalable and flexible data management.

## Features

- **User Authentication**: Secure user registration and login system with JWT token-based authentication for multi-device access
- **Group Management**: Create and manage roommate groups with easy member addition and removal
- **Chore Tracking**: 
  - Assign chores to roommates with due dates
  - Support for recurring chores with automatic rotation
  - Track completion status and identify overdue tasks
- **Rent & Bills Management**: 
  - Track rent due dates and amounts
  - Monitor individual rent shares per roommate
  - Receive notifications for upcoming and overdue payments
- **Supplies Monitoring**: 
  - Track household supplies with purchase history
  - Automatic low-stock alerts based on usage patterns
  - Configurable average days between purchases
- **Calendar Integration**: Unified calendar view showing rent due dates, chores, and supply needs
- **Dashboard**: Real-time overview of rent status, supplies, and upcoming chores

## Architecture

The application consists of three main subsystems:

1. **API Service** (`api/`): Flask web application serving the frontend and REST API endpoints
   - Docker Hub: [khushboo1908/api-service](https://hub.docker.com/r/khushboo1908/api-service)
   - Port: 8000

2. **Service Layer** (`service/`): Flask microservice providing business logic and recommendation services
   - Docker Hub: [khushboo1908/service-layer](https://hub.docker.com/r/khushboo1908/service-layer)
   - Port: 8100

3. **MongoDB Database**: Document database storing all application data
   - Port: 27017

## Class Members

- [Khushboo Agrawal](https://github.com/KhushbooAgrawal190803)
- [Reece Huey](https://github.com/Coffee859)
- [Majo Salgado](https://github.com/mariajsalgadoq)
- [Alissa Hsu](https://github.com/alissahsu22)

## Setup and Installation

### Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose
- Git

### Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/swe-students-fall2025/5-final-qt-s.git
   cd 5-final-qt-s
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   ```

3. **Activate the virtual environment:**
   - On Windows (PowerShell):
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Set up environment variables:**
   
   Create a `.env` file in the project root directory (see `.env.example` for reference):
   ```env
   MONGO_URL=mongodb://localhost:27017
   MONGO_DB_NAME=main_db
   JWT_SECRET=your-secret-key-change-in-production
   PORT=8000
   ```
   **Important:** Replace `JWT_SECRET` with a strong, randomly generated secret key for production use.

6. **Run the application:**
   ```bash
   # Start MongoDB and services with Docker Compose
   docker-compose up
   ```

   The application will be available at:
   - API Service: http://localhost:8000
   - Service Layer: http://localhost:8100
   - MongoDB: localhost:27017

### Database Seeding

To populate the database with sample data:

1. **Ensure MongoDB is running:**
   ```bash
   docker-compose up mongo
   ```
2. **Run the seed script:**
   ```bash
   # With virtual environment activated
   python mongo/seed.py
   ```
   Or using Docker:
   ```bash
   docker-compose exec mongo python /app/mongo/seed.py
   ```
   The seed script will populate the database with sample groups, roommates, supplies, rent records, and chores.

## Environment Variables

Create a `.env` file in the project root directory. See `.env.example` for a template:

```bash
cp .env.example .env
```

Required environment variables:

| Variable        | Description                         | Default Value                          |
|-----------------|-------------------------------------|----------------------------------------|
| `MONGO_URL`     | MongoDB connection string           | `mongodb://localhost:27017`            |
| `MONGO_DB_NAME` | Name of the MongoDB database        | `main_db`                              |
| `JWT_SECRET`    | Secret key for JWT token generation | `your-secret-key-change-in-production` |
| `PORT`          | Port for the API service            | `8000`                                 |

## Deployment

### CI/CD Pipeline

The project uses GitHub Actions for continuous integration and deployment. Each subsystem has its own workflow:

- **API Workflow** (`.github/workflows/api.yml`): Builds, tests, and deploys the API service
- **Service Workflow** (`.github/workflows/service.yml`): Builds, tests, and deploys the service layer

### Required GitHub Secrets

Configure the following secrets in your GitHub repository settings:

| Secret                      | Description                                  | Required For |
|-----------------------------|----------------------------------------------|--------------|
| `DOCKERHUB_USERNAME`        | Your Docker Hub username                     | Build & Deploy |
| `DOCKERHUB_TOKEN`           | Docker Hub personal access token             | Build & Deploy |
| `DIGITALOCEAN_HOST`         | Digital Ocean droplet IP or hostname          | Deploy only |
| `DIGITALOCEAN_USERNAME`     | SSH username (usually `root`)                | Deploy only |
| `DIGITALOCEAN_SSH_KEY`      | SSH private key for Digital Ocean deployment | Deploy only |
| `MONGO_URL`                 | MongoDB connection string                     | Deploy only |
| `MONGO_DB_NAME`             | Database name                                | Deploy only |
| `JWT_SECRET`                | Secret key for JWT tokens                    | Deploy only |

**Note:** The deployment step is configured with `continue-on-error: true`, so the workflow will still pass even if deployment secrets are not configured. Tests and Docker builds will run regardless.

### Digital Ocean Deployment Setup

The application is deployed to a Digital Ocean droplet with the following configuration:

- **Host**: 159.65.178.253
- **Network**: Containers use host networking mode to access MongoDB running on the same host
- **MongoDB**: Running in a Docker container, accessible via `localhost:27017` from application containers
- **Firewall**: Ports 22 (SSH), 8000 (API), 8100 (Service Layer), and 27017 (MongoDB) are open

#### Deployment Process

1. **Automatic Deployment**: When code is pushed to the `main` branch:
   - GitHub Actions runs tests
   - Docker images are built and pushed to Docker Hub
   - Images are pulled and deployed to the Digital Ocean droplet
   - Containers are restarted with the latest images

2. **Manual Deployment** (if needed):
   ```bash
   # SSH into the droplet
   ssh root@159.65.178.253
   
   # Pull latest images
   docker login -u YOUR_DOCKERHUB_USERNAME -p YOUR_DOCKERHUB_TOKEN
   docker pull khushboo1908/api-service:latest
   docker pull khushboo1908/service-layer:latest
   
   # Restart containers
   docker stop api-service service-layer || true
   docker rm api-service service-layer || true
   docker run -d --name api-service --restart unless-stopped --network host \
     -e MONGO_URL=mongodb://localhost:27017 \
     -e MONGO_DB_NAME=main_db \
     -e JWT_SECRET=YOUR_JWT_SECRET \
     -e PORT=8000 \
     khushboo1908/api-service:latest
   
   docker run -d --name service-layer --restart unless-stopped --network host \
     -e MONGO_URL=mongodb://localhost:27017 \
     -e MONGO_DB_NAME=main_db \
     -e PORT=8100 \
     khushboo1908/service-layer:latest
   ```

#### Setting Up GitHub Secrets

To enable automated deployment, configure the following secrets in your GitHub repository:

1. Go to: `https://github.com/swe-students-fall2025/5-final-qt-s/settings/secrets/actions`
2. Add each secret listed in the table above
3. For `DIGITALOCEAN_SSH_KEY`, paste your entire SSH private key (including `-----BEGIN OPENSSH PRIVATE KEY-----` and `-----END OPENSSH PRIVATE KEY-----` lines)
4. For `JWT_SECRET`, generate a secure random 64-character hex string

