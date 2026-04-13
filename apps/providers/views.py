from django.http import JsonResponse
import requests

def get_server_ip(request):
    ip = requests.get("https://api.ipify.org").text
    return JsonResponse({"server_ip": ip})