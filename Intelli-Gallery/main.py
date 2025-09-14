import os
from flask import Flask, request, jsonify
from flask_cors import CORS # Import the CORS library
from google.cloud import storage, pubsub_v1, firestore

# Initialize clients
app = Flask(__name__)
# --- THIS LINE ENABLES CORS ---
# It tells Flask to add the required headers to all responses.
CORS(app) 

storage_client = storage.Client()
publisher = pubsub_v1.PublisherClient()
firestore_client = firestore.Client()

# Configuration
BUCKET_NAME = "intelli-gallery-uploads-gnu2"
PROJECT_ID = "intelli-gallery-project" 
TOPIC_ID = "image-uploaded"

@app.route('/upload', methods=['POST'])
def upload_file():
    """Accepts a file upload, saves it to GCS, and publishes a message."""
    uploaded_file = request.files.get('file')
    if not uploaded_file:
        return 'No file uploaded.', 400

    # 1. Upload to Cloud Storage
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(uploaded_file.filename)
    # Reset file pointer before reading
    uploaded_file.seek(0)
    blob.upload_from_file(uploaded_file)

    # 2. Publish a message to Pub/Sub
    try:
        topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
        message_data = uploaded_file.filename.encode('utf-8')
        future = publisher.publish(topic_path, data=message_data)
        future.result()
    except Exception as e:
        print(f"Error publishing to Pub/Sub: {e}")
        return "File uploaded, but failed to publish notification.", 500

    return f"File {uploaded_file.filename} uploaded and notification sent.", 200

@app.route('/gallery', methods=['GET'])
def get_gallery_data():
    """Queries Firestore and returns a list of image data."""
    try:
        images_ref = firestore_client.collection('images')
        # Order by creation time, descending, to get the newest first
        query = images_ref.order_by('created_at', direction=firestore.Query.DESCENDING)
        docs = query.stream()
        
        gallery_items = []
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            # Convert datetime to a string for JSON serialization
            item['created_at'] = item['created_at'].isoformat()
            gallery_items.append(item)
            
        return jsonify(gallery_items), 200

    except Exception as e:
        print(f"Error getting gallery data: {e}")
        return "Error retrieving gallery data.", 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)

