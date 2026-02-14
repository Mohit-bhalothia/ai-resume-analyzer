# Deploy AI Resume Analyzer to AWS

This guide covers three deployment options on AWS. Choose based on your needs:

| Option | Best for | Complexity | Cost |
|--------|----------|------------|------|
| **App Runner** | Easiest, fully managed | Low | ~\$25–50/month |
| **ECS Fargate** | Production, scalable | Medium | ~\$30–80/month |
| **EC2** | Full control, custom setup | Medium | ~\$15–40/month |

**Prerequisites:** Docker image pushed to Docker Hub (or ECR), AWS account, AWS CLI configured.

---

## Option 1: AWS App Runner (Recommended for quick deploy)

App Runner builds and runs containers from a source repo or image. No cluster management.

### Step 1: Push image to Amazon ECR (or use Docker Hub)

**Using Docker Hub** (simplest – image already public):
- Use: `mohitbhalothia007/ai-resume-analyzer:latest`
- App Runner can pull from Docker Hub

**Using ECR** (private, faster pulls in AWS):
```bash
# Create ECR repository
aws ecr create-repository --repository-name ai-resume-analyzer

# Get login command and authenticate
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
docker tag mohitbhalothia007/ai-resume-analyzer:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/ai-resume-analyzer:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/ai-resume-analyzer:latest
```

### Step 2: Create App Runner service (Console)

1. Open **AWS Console** → **App Runner** → **Create service**
2. **Source:**
   - Repository type: **Container registry**
   - Provider: **Amazon ECR** (or **Other** for Docker Hub)
   - Image URI: your ECR URI or `mohitbhalothia007/ai-resume-analyzer:latest`
3. **Service settings:**
   - Service name: `ai-resume-analyzer`
   - Port: `8000`
   - CPU: 2 vCPU
   - Memory: 4 GB (required for ML model)
4. **Create service**

After creation, App Runner provides a URL like `https://xxxxx.us-east-1.awsapprunner.com`.

### Step 2 (alternative): Create via AWS CLI (using ECR image)

After pushing to ECR:
```bash
aws apprunner create-service \
  --service-name ai-resume-analyzer \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/ai-resume-analyzer:latest",
      "ImageRepositoryType": "ECR"
    },
    "AutoDeploymentsEnabled": false
  }' \
  --instance-configuration '{
    "Cpu": "2 vCPU",
    "Memory": "4 GB"
  }' \
  --health-check-configuration '{
    "Protocol": "HTTP",
    "Path": "/health",
    "Interval": 10,
    "Timeout": 5,
    "HealthyThreshold": 1,
    "UnhealthyThreshold": 5
  }'
```

---

## Option 2: ECS Fargate (Scalable production)

Run your container on Fargate without managing servers.

### Step 1: Push image to ECR

```bash
aws ecr create-repository --repository-name ai-resume-analyzer
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
docker tag mohitbhalothia007/ai-resume-analyzer:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/ai-resume-analyzer:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/ai-resume-analyzer:latest
```

### Step 2: Create ECS cluster and task definition

**Task definition** (`task-definition.json`):

```json
{
  "family": "ai-resume-analyzer",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "containerDefinitions": [
    {
      "name": "app",
      "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/ai-resume-analyzer:latest",
      "portMappings": [{ "containerPort": 8000 }],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/ai-resume-analyzer",
          "awslogs-region": "us-east-1"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

### Step 3: Create log group and register task

```bash
aws logs create-log-group --log-group-name /ecs/ai-resume-analyzer
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

### Step 4: Create cluster, service, and load balancer

Use the AWS Console (ECS → Create cluster → Create service) or CloudFormation/Terraform. For a basic setup:

1. **Create cluster:** ECS → Clusters → Create → Name: `resume-analyzer-cluster`
2. **Create ALB** (Application Load Balancer) in the same VPC
3. **Create ECS service:**
   - Launch type: Fargate
   - Task definition: `ai-resume-analyzer`
   - Desired tasks: 1
   - Load balancer: Add to ALB, target group, port 8000

---

## Option 3: EC2 (Simple VM + Docker)

Full control over the instance and networking.

### Step 1: Launch EC2 instance

- **AMI:** Amazon Linux 2023 or Ubuntu 22.04
- **Instance type:** `t3.medium` or `t3.large` (2–4 GB RAM for ML model)
- **Storage:** 20 GB
- **Security group:** Allow inbound HTTP (80), HTTPS (443), and optionally 8000 for testing

### Step 2: Connect and install Docker

```bash
ssh -i your-key.pem ec2-user@<instance-ip>
```

```bash
# Amazon Linux 2023
sudo yum update -y
sudo yum install docker -y
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user
# Log out and back in for group to take effect
```

```bash
# Ubuntu
sudo apt update
sudo apt install docker.io -y
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ubuntu
```

### Step 3: Run the container

```bash
docker run -d \
  -p 8000:8000 \
  --name resume-analyzer \
  --restart unless-stopped \
  mohitbhalothia007/ai-resume-analyzer:latest
```

### Step 4: (Optional) Add Nginx reverse proxy + HTTPS

```bash
sudo yum install nginx -y   # or: sudo apt install nginx -y
# Configure nginx to proxy / to localhost:8000
# Use Let's Encrypt (certbot) for HTTPS
```

---

## Environment variables (all options)

For production, set:

```bash
ENVIRONMENT=production
JWT_SECRET_KEY=<strong-random-secret>
```

- **App Runner:** Configure in service → Configuration → Environment variables
- **ECS:** Add to task definition `environment` array
- **EC2:** Use `-e` in `docker run` or an env file

---

## Cost estimates (us-east-1)

| Service | Config | Approx. monthly |
|---------|--------|------------------|
| App Runner | 2 vCPU, 4 GB, 24/7 | ~\$50 |
| ECS Fargate | 2 vCPU, 4 GB, 1 task | ~\$60 |
| EC2 t3.medium | On-demand | ~\$30 |
| EC2 t3.large | On-demand | ~\$60 |

Add data transfer and any other AWS services you use.

---

## Quick reference

| Action | Command / Location |
|--------|--------------------|
| ECR login | `aws ecr get-login-password \| docker login ...` |
| Push to ECR | `docker push <ECR_URI>/ai-resume-analyzer:latest` |
| Health check | `GET /health` |
| App port | 8000 |
