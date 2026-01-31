import json
import os

import requests

# Получаем токен из config.json
config_path = os.path.expanduser("~/.railway/config.json")
with open(config_path) as f:
    config = json.load(f)
    token = config["token"]

PROJECT_ID = "acf22966-f165-4e4d-a9ba-ce2efef63129"
API_URL = "https://backboard.railway.app/graphql/v2"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Получаем список сервисов
query = """
query project($id: String!) {
  project(id: $id) {
    services {
      edges {
        node {
          id
          name
        }
      }
    }
  }
}
"""

response = requests.post(API_URL, json={"query": query, "variables": {"id": PROJECT_ID}}, headers=headers)
print("Сервисы:")
print(json.dumps(response.json(), indent=2))

# Найдем training-bot
data = response.json()
if "data" in data and data["data"] and "project" in data["data"]:
    services = data["data"]["project"]["services"]["edges"]
    for service in services:
        if service["node"]["name"] == "training-bot":
            service_id = service["node"]["id"]
            print(f"\nНашел training-bot: {service_id}")

            # Удаляем
            delete_mutation = """
            mutation serviceDelete($id: String!) {
              serviceDelete(id: $id)
            }
            """

            del_response = requests.post(API_URL, json={"query": delete_mutation, "variables": {"id": service_id}}, headers=headers)
            print(f"Удаление: {del_response.json()}")
