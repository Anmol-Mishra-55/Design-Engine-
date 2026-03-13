# type: ignore
import json
import os
from typing import Optional


# AWS Secrets Manager integration (requires boto3)
def get_aws_secret(secret_name: str, region: str = "us-east-1") -> Optional[dict]:
    """Get secrets from AWS Secrets Manager"""
    try:
        import boto3
        from botocore.exceptions import ClientError

        session = boto3.session.Session()
        client = session.client(service_name="secretsmanager", region_name=region)

        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])
    except ImportError:
        print("boto3 not installed. Install with: pip install boto3")
        return None
    except ClientError as e:
        print(f"AWS Secrets Manager error: {e}")
        return None


# Azure Key Vault integration (requires azure-keyvault-secrets)
def get_azure_secret(vault_url: str, secret_name: str) -> Optional[str]:
    """Get secrets from Azure Key Vault"""
    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=vault_url, credential=credential)

        secret = client.get_secret(secret_name)
        return secret.value
    except ImportError:
        print("Azure SDK not installed. Install with: pip install azure-keyvault-secrets azure-identity")
        return None
    except Exception as e:
        print(f"Azure Key Vault error: {e}")
        return None


def load_secrets_from_manager():
    """Load secrets from cloud secret manager instead of .env"""

    # Check if running in cloud environment
    if os.getenv("USE_SECRET_MANAGER") == "true":
        # AWS Secrets Manager
        if os.getenv("AWS_SECRET_NAME"):
            secrets = get_aws_secret(os.getenv("AWS_SECRET_NAME"))
            if secrets:
                for key, value in secrets.items():
                    os.environ[key] = value
                print("✅ Loaded secrets from AWS Secrets Manager")
                return True

        # Azure Key Vault
        elif os.getenv("AZURE_VAULT_URL"):
            vault_url = os.getenv("AZURE_VAULT_URL")
            secret_names = [
                "DATABASE_URL",
                "MONGODB_URL",
                "JWT_SECRET_KEY",
                "OPENAI_API_KEY",
                "SENTRY_DSN",
                "ENCRYPTION_KEY",
            ]

            for secret_name in secret_names:
                secret_value = get_azure_secret(vault_url, secret_name)
                if secret_value:
                    os.environ[secret_name] = secret_value

            print("✅ Loaded secrets from Azure Key Vault")
            return True

    print("ℹ️ Using .env file for secrets (development mode)")
    return False


# Initialize secret loading
load_secrets_from_manager()
