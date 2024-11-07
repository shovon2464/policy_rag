from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests
import json

# Create your views here.

base_url = "http://192.168.1.118:3001"

def alive_view(request):
    return JsonResponse({"message": "I am alive"})

class RetrieveInfoView(APIView):
    def post(self, request):
        file = request.FILES.get('file')

        # Check if the file is present
        if not file:
            return Response({"error": "File is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Set up the external API endpoint and headers for the file upload
        upload_url = f"{base_url}/api/v1/document/upload"
        headers = {
            "Authorization": "Bearer 2K24C59-8M9MTXA-KP1MSRA-4YKB3E9"
        }

        # Prepare the file to be sent as form-data
        files = {
            "file": (file.name, file.read(), file.content_type)  # Read the file content
        }

        # Send the file to the external API as form data
        try:
            response = requests.post(upload_url, headers=headers, files=files)

            # Check if the external server request was successful
            if response.status_code == 200:
                response_data = response.json()  # Parse JSON response
                if response_data.get("success") and response_data.get("documents"):
                    # Extract the location field
                    location = response_data["documents"][0].get("location")

                    # Initial embedding update request
                    update_url = f"{base_url}/api/v1/workspace/policy_search/update-embeddings"
                    update_payload = {
                        "adds": [location],
                        "deletes": []
                    }

                    # Send the initial embeddings update request
                    update_response = requests.post(update_url, headers=headers, json=update_payload)

                    # Check if the embeddings update was successful
                    if update_response.status_code == 200:
                        # Prepare payload for deleting the embedding
                        delete_payload = {
                            "adds": [],
                            "deletes": [location]
                        }

                        # Send the delete request for the embedding
                        delete_response = requests.post(update_url, headers=headers, json=delete_payload)

                        if delete_response.status_code != 200:
                            return Response({
                                "error": "Failed to delete embedding",
                                "details": delete_response.text
                            }, status=delete_response.status_code)

                        # After successful deletion of embedding, proceed with creating a new thread
                        thread_url = f"{base_url}/api/v1/workspace/policy_search/thread/new"
                        thread_payload = {
                            "userId": 1
                        }

                        # Send request to create a new thread
                        thread_response = requests.post(thread_url, headers=headers, json=thread_payload)

                        # Check if the thread creation was successful
                        if thread_response.status_code == 200:
                            thread_data = thread_response.json()  # Parse JSON response
                            thread_slug = thread_data["thread"].get("slug")

                            # Prepare the prompt message for the chat
                            prompt = "\nThe text given in the document is a scanned document of insurance but the scanning is not perfect, that's why the texts are scattered. I need your intelligence to extract the following keywords "
                            prompt += "Please find the following keywords PolicyNumber, BrokerID, StartDate, EndDate."
                            prompt += " Please double-check the policy numbers, as it is the most important part. Accuracy is very important."
                            prompt += " Ensure there are no dots, spaces, or hyphens in broker id."
                            prompt += " The example of date format can be 23 Jan 2024. Follow this date format while extracting any date. If required, reformat but be consistent. Ensure there are no dots, spaces, or hyphens in date. The expiry date or end date is easy to find as it is a range of 1 year from start date, but it might also be explicitly written."
                            prompt += " Please be very careful; don't try to be fast, be accurate. If you cannot find the value, just give None in the value of the key."
                            prompt += " I only want the JSON and nothing else. An example response can be {\n\"PolicyNumber\": \"4V3130329\",\n\"BrokerID\": \"37763\",\n\"StartDate\": \"01 Mar 2024\",\n\"EndDate\": \"01 Mar 2025\"\n}\n"

                            # Send the prompt in the created thread
                            chat_url = f"{base_url}/api/v1/workspace/policy_search/thread/{thread_slug}/chat"
                            chat_payload = {
                                "message": prompt,
                                "mode": "chat",
                                "userId": 1
                            }

                            # Send the chat request
                            chat_response = requests.post(chat_url, headers=headers, json=chat_payload)

                            # Check if chat request was successful
                            if chat_response.status_code == 200:
                                chat_data = chat_response.json()
                                
                                # Check if 'textResponse' contains valid JSON
                                try:
                                    data = json.loads(chat_data.get('textResponse'))
                                    print("Chat Response:", data )  # Print the chat response
                                except json.JSONDecodeError:
                                    return Response({
                                        "error": "The response is not valid JSON.",
                                        "details": chat_data.get('textResponse')
                                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                # After completing the chat interaction, delete the thread
                                delete_thread_url = f"{base_url}/api/v1/workspace/policy_search/thread/{thread_slug}"
                                delete_thread_response = requests.delete(delete_thread_url, headers=headers)

                                # Check if the thread deletion was successful
                                if delete_thread_response.status_code == 200:
                                    return Response({
                                        "chat_response": data
                                    }, status=status.HTTP_200_OK)
                                else:
                                    return Response({
                                        "error": "Failed to delete thread",
                                        "details": delete_thread_response.text
                                    }, status=delete_thread_response.status_code)
                            else:
                                return Response({
                                    "error": "Failed to send chat message in thread",
                                    "details": chat_response.text
                                }, status=chat_response.status_code)
                        else:
                            return Response({
                                "error": "Failed to create new thread",
                                "details": thread_response.text
                            }, status=thread_response.status_code)
                    else:
                        return Response({
                            "error": "Failed to update embeddings",
                            "details": update_response.text
                        }, status=update_response.status_code)
                else:
                    return Response({"error": "Invalid response from external server"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                return Response({
                    "error": "Failed to upload file to external server",
                    "details": response.text
                }, status=response.status_code)

        except requests.RequestException as e:
            # Handle any errors in the request
            return Response({"error": f"Request to external server failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
