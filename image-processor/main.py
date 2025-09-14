import os
import base64
import datetime
from flask import Flask, request
from google.cloud import storage, vision, firestore

app = Flask(__name__)

# Initialize clients
storage_client = storage.Client()
vision_client = vision.ImageAnnotatorClient()
firestore_client = firestore.Client()

# Configuration from environment variables
BUCKET_NAME = os.environ.get('BUCKET_NAME')

@app.route('/', methods=['POST'])
def receive_message():
    """Receives a Pub/Sub message, analyzes the image, and saves results to Firestore."""
    
    envelope = request.get_json()
    if not envelope or 'message' not in envelope:
        return 'Invalid Pub/Sub message format', 400

    message_data = envelope['message']['data']
    try:
        filename = base64.b64decode(message_data).decode('utf-8')
    except Exception as e:
        print(f"Error decoding message data: {e}")
        return "Error decoding message", 400
    
    print(f"Received message to process file: {filename}")

    if not BUCKET_NAME:
        print("Error: BUCKET_NAME environment variable not set.")
        return "Configuration error", 500

    try:
        # 1. Download image from GCS and call Vision API (same as before)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(filename)
        image_content = blob.download_as_bytes()
        image = vision.Image(content=image_content)
        response = vision_client.label_detection(image=image)
        labels = response.label_annotations

        # 2. Structure the data for Firestore
        # Extract just the descriptions for cleaner storage
        label_descriptions = [label.description for label in labels]

        data_to_save = {
            'filename': filename,
            'labels': label_descriptions,
            'created_at': datetime.datetime.now(datetime.timezone.utc)
        }

        # 3. Save the data to Firestore
        firestore_client.collection('images').add(data_to_save)
        print(f"Successfully saved analysis for {filename} to Firestore.")

    except Exception as e:
        print(f"Error processing image {filename}: {e}")
        return "Error processing image", 500
    
    return 'Message processed successfully.', 204

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8081, debug=True)

