# glTF to Digital Twin Pipeline

**Automated Digital Twin Creation from glTF 3D Models**

This project automatically converts glTF 3D models into fully functional digital twins with real-time IoT sensor integration. Upload a glTF file and watch as it transforms into a live digital twin with automated asset hierarchy creation in AWS IoT SiteWise and visualization in Grafana.

## What This Does

Transform any glTF 3D model into a digital twin in 5 simple steps:

1. **Deploy Infrastructure** - One-command AWS CDK deployment
2. **Upload glTF File** - Simple script uploads your 3D model
3. **Automatic Processing** - Lambda parses structure and creates IoT assets
4. **Digital Twin Creation** - TwinMaker binds 3D model to IoT data
5. **Live Visualization** - Real-time sensor data in Grafana

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   glTF Upload   │───▶│  Lambda Parser  │───▶│  IoT SiteWise   │
│   (S3 Bucket)   │    │   (CDK Stack)   │    │   (Assets)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   TwinMaker     │◀───│   MQTT Topics   │
                       │   (Workspace)   │    │   (IoT Core)    │
                       └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │    Grafana      │
                       │ (Visualization) │
                       └─────────────────┘
```

## Quick Start

### Prerequisites

- AWS CLI configured with appropriate permissions
- Python 3.11+
- Node.js 18+ (for CDK)
- AWS CDK CLI installed globally: `npm install -g aws-cdk`

### Step 1: Clone and Setup

```bash
git clone <your-repo-url>
cd project_code

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Deploy Infrastructure

```bash
# Deploy the CDK stack
cdk deploy
```

This creates:
- ✅ S3 bucket for glTF uploads
- ✅ Lambda function for automatic processing
- ✅ IoT Core broker and topic rules
- ✅ TwinMaker workspace
- ✅ SiteWise setup
- ✅ All necessary IAM roles and permissions

**Important**: After deployment, CDK will output the S3 bucket name in the terminal. Copy this for the next step.

### Step 3: Upload Your glTF File

```bash
# Upload your 3D model
python upload_gltf.py --bucket <your-bucket-name> --file /path/to/your/model.glb
```

Or use the interactive version:
```bash
python upload_gltf.py
# The script will prompt you for bucket name and file path
```

### Step 4: Watch the Magic Happen

1. **Automatic Trigger**: Lambda function is automatically triggered by the S3 upload
2. **Structure Parsing**: Lambda extracts scene, nodes, mesh names, and sensor locations from your glTF
3. **Asset Creation**: IoT SiteWise assets and hierarchies are created automatically
4. **Topic Mapping**: Each asset property is mapped to its corresponding MQTT topic
5. **Digital Twin Binding**: TwinMaker connects the 3D model to the IoT asset hierarchy

### Step 5: Visualize in Grafana

1. Access your Grafana dashboard
2. View the live TwinMaker 3D scene
3. See real-time sensor data streaming
4. Query historical data from Timestream or S3

## Project Structure

```
project_code/
├── app.py                          # CDK app entry point
├── project_code_stack.py           # Main CDK stack definition
├── requirements.txt                # Python dependencies
├── requirements-dev.txt            # Development dependencies
├── upload_gltf.py                 # glTF upload script
├── lambda/                        # Lambda function code
│   └── gltf_parser.py             # Main Lambda handler
└── tests/                         # Unit tests
    └── unit/
        └── test_project_code_stack.py
```

## Configuration

### Lambda Settings

The Lambda function is configured with:
- **Timeout**: 5 minutes (sufficient for most glTF processing)
- **Memory**: 512 MB (good balance of cost and performance)
- **Log Retention**: 1 week (for debugging while keeping costs low)

### S3 Bucket Settings

- **Versioning**: Enabled for file safety
- **Removal Policy**: DESTROY (for development - change to RETAIN in production)
- **Auto-delete**: Enabled (for development cleanup)

## Development

### Adding New Features

1. **Modify Lambda Logic**: Edit `lambda/gltf_parser.py`
2. **Update Infrastructure**: Modify `project_code_stack.py`
3. **Test Changes**: Run `cdk synth` to validate
4. **Deploy**: Run `cdk deploy`

### Useful CDK Commands

```bash
cdk ls                    # List all stacks
cdk synth                 # Generate CloudFormation template
cdk deploy                # Deploy to AWS
cdk diff                  # Compare with deployed stack
cdk destroy               # Clean up all resources
cdk docs                  # Open CDK documentation
```

### Testing

```bash
# Run unit tests
python -m pytest tests/

# Test CDK synthesis
cdk synth
```

## Security Considerations

### Production Deployment

Before deploying to production:

1. **Change Removal Policy**: Set `removal_policy=RemovalPolicy.RETAIN` in `project_code_stack.py`
2. **Disable Auto-delete**: Set `auto_delete_objects=False`
3. **Review IAM Permissions**: Ensure least-privilege access
4. **Enable Encryption**: Configure S3 bucket encryption
5. **Set Log Retention**: Increase log retention for compliance

### IAM Permissions

The stack creates minimal required permissions:
- Lambda can read/write to the S3 bucket
- Lambda can create/update IoT SiteWise assets
- Lambda can publish to IoT Core topics


## Troubleshooting Common Issues

1. **Upload Fails**: Check S3 bucket permissions and file size limits
2. **Lambda Timeout**: Increase timeout in `project_code_stack.py`
3. **Memory Issues**: Increase memory allocation for large glTF files
4. **SiteWise Errors**: Verify IoT SiteWise service is enabled in your region

### CloudWatch Logs

Lambda execution logs are available in CloudWatch:
- Log Group: `/aws/lambda/<stack-name>-GltfParserLambda`
- Retention: 1 week (configurable)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


