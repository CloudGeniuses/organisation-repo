import json
import requests
import os
import base64
from nacl.public import PublicKey, SealedBox
from nacl.encoding import Base64Encoder

# GitHub API base URL
GITHUB_API_URL = "https://api.github.com"
ORG_NAME = os.getenv("ORGNAME")
GITHUB_TOKEN = os.getenv("GH_TOKEN")

# Retrieve other environment variables corresponding to secrets
# AZURE_SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID")
# AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
# AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
# RG_URL = os.getenv("RG_URL")
# RG_PASSWORD = os.getenv("RG_PASSWORD")
# RG_USERNAME = os.getenv("RG_USERNAME")

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

def create_repo(repo_name):
    """Create a new GitHub repository in the organization."""
    url = f"{GITHUB_API_URL}/orgs/{ORG_NAME}/repos"
    payload = {
        "name": repo_name,
        "private": True
    }
    response = requests.post(url, headers=HEADERS, json=payload)
    response.raise_for_status()
    print(f"Repository '{repo_name}' created successfully.")

def add_collaborator(repo_name, user):
    """Add a user as a collaborator to the repository."""
    url = f"{GITHUB_API_URL}/repos/{ORG_NAME}/{repo_name}/collaborators/{user}"
    payload = {
        "permission": "push"
    }
    response = requests.put(url, headers=HEADERS, json=payload)
    response.raise_for_status()
    print(f"User '{user}' added as collaborator to '{repo_name}'.")

def read_pipeline_file(pipeline_type):
    """Read the content of the existing pipeline file."""
    file_path = f"{pipeline_type}.yml"
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return file.read()
    else:
        raise FileNotFoundError(f"The file for pipeline type '{pipeline_type}' does not exist.")

def create_pipeline(repo_name, pipeline_type):
    """Create a pipeline for the given repository."""
    if pipeline_type is None:
        raise ValueError("Pipeline type is not defined.")
    
    content = read_pipeline_file(pipeline_type)
    encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')

    url = f"{GITHUB_API_URL}/repos/{ORG_NAME}/{repo_name}/contents/.github/workflows/{pipeline_type}.yml"
    
    payload = {
        "message": f"Add {pipeline_type} pipeline",
        "content": encoded_content,
        "branch": "main"
    }
    
    response = requests.put(url, headers=HEADERS, json=payload)
    response.raise_for_status()
    print(f"Pipeline for '{repo_name}' created successfully.")

def get_public_key(repo_name):
    url = f"{GITHUB_API_URL}/repos/{ORG_NAME}/{repo_name}/actions/secrets/public-key"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()

def set_repo_secrets(repo_name, secrets):
    """Set secrets in the repository."""
    public_key_info = get_public_key(repo_name)
    public_key = public_key_info["key"]
    
    for secret_name, secret_value in secrets.items():
        url = f"{GITHUB_API_URL}/repos/{ORG_NAME}/{repo_name}/actions/secrets/{secret_name}"
        payload = {
            "encrypted_value": encrypt(public_key, secret_value),
            "key_id": public_key_info["key_id"]
        }
        
        response = requests.put(url, headers=HEADERS, json=payload)
        response.raise_for_status()
        print(f"Secret '{secret_name}' added to '{repo_name}'.")

def encrypt(public_key: str, secret_value: str) -> str:
    """Encrypt a Unicode string using the public key."""
    while len(public_key) % 4 != 0:
        public_key += '='
    public_key = PublicKey(public_key.encode("utf-8"), encoder=Base64Encoder())
    sealed_box = SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")

def main():
    with open('repos.json') as json_file:
        repos_data = json.load(json_file)

    for repo in repos_data:
        if repo["status"] == "need-to-create":
            try:
                create_repo(repo["repo-name"])
                for user in repo["repo-users"]:
                    add_collaborator(repo["repo-name"], user)
                create_pipeline(repo["repo-name"], repo.get("pipeline-type"))

                secrets = {
                    "SECRET_KEY": "example_secret_value",
                    # "AZURE_SUBSCRIPTION_ID": AZURE_SUBSCRIPTION_ID,
                    # "AZURE_TENANT_ID": AZURE_TENANT_ID,
                    # "AZURE_CLIENT_ID": AZURE_CLIENT_ID,
                    # "RG_URL": RG_URL,
                    # "RG_PASSWORD": RG_PASSWORD,
                    # "RG_USERNAME": RG_USERNAME,
                    "GH_TOKEN": GITHUB_TOKEN    
                }
                set_repo_secrets(repo["repo-name"], secrets)
                repo["status"] = "created"

            except requests.exceptions.RequestException as e:
                print(f"Error creating repo or adding collaborators: {e}")

    with open('repos.json', 'w') as json_file:
        json.dump(repos_data, json_file, indent=2)

if __name__ == "__main__":
    main()
