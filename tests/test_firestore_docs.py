import argparse
import json
import os
from google.cloud import firestore
from google.oauth2 import service_account

def get_client(project_id=None, credentials_path=None, database=None):
    """
    Returns a firestore.Client using either the provided credentials file
    or standard Application Default Credentials.
    """
    kwargs = {}
    if credentials_path:
        print(f"Loading service account credentials from: {credentials_path}")
        with open(credentials_path, "r") as f:
            credentials_info = json.load(f)
        credentials = service_account.Credentials.from_service_account_info(credentials_info)
        kwargs["credentials"] = credentials
        # Use the project_id from the service account JSON if not explicitly provided
        if not project_id:
            project_id = credentials_info.get("project_id")
    
    if project_id:
        kwargs["project"] = project_id
    if database:
        kwargs["database"] = database
        
    return firestore.Client(**kwargs)

def main():
    parser = argparse.ArgumentParser(description="Add test documents to Firestore collection.")
    parser.add_argument("--project", help="GCP Project ID")
    parser.add_argument("--credentials", help="Path to GCP Service Account credentials JSON file")
    parser.add_argument("--database", help="Firestore database ID (optional, defaults to '(default)')")
    parser.add_argument("--collection", default="testing", help="Firestore collection name (default: testing)")
    
    args = parser.parse_args()
    
    # 3 test documents as requested (2 provided, 1 added)
    documents = [
        {
            "customer_id": 1001,
            "email": "alice@example.com",
            "first_name": "Alice",
            "last_name": "Johnson",
            "country": "USA",
            "signup_date": "2025-01-12",
            "customer_status": "ACTIVE",
            "marketing_opt_in": True
        },
        {
            "customer_id": 1002,
            "email": "bob@example.com",
            "first_name": "Bob",
            "last_name": "Smith",
            "country": "Canada",
            "signup_date": "2024-11-22",
            "customer_status": "ACTIVE",
            "marketing_opt_in": False
        },
        {
            "customer_id": 1003,
            "email": "charlie@example.com",
            "first_name": "Charlie",
            "last_name": "Brown",
            "country": "UK",
            "signup_date": "2025-02-15",
            "customer_status": "ACTIVE",
            "marketing_opt_in": True
        }
    ]
    
    try:
        client = get_client(args.project, args.credentials, args.database)
        collection_ref = client.collection(args.collection)
        
        print(f"Adding documents to collection '{args.collection}' in project '{client.project}'...")
        
        for doc in documents:
            # Using customer_id as the document ID for clean overwrite/tracking
            doc_id = str(doc["customer_id"])
            doc_ref = collection_ref.document(doc_id)
            doc_ref.set(doc)
            print(f"  Added document ID: {doc_id} -> {doc['first_name']} {doc['last_name']}")
            
        print("Success! All documents added to Firestore.")
    except Exception as e:
        print(f"Error connecting/writing to Firestore: {e}")
        print("\nPlease ensure you have installed google-cloud-firestore and set up authorization:")
        print("  pip install google-cloud-firestore")
        print("And if not passing --credentials, configure Application Default Credentials:")
        print("  gcloud auth application-default login")

if __name__ == "__main__":
    main()
