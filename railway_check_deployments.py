#!/usr/bin/env python3
"""
Проверка активных deployments в Railway
"""
import json
import os
import requests

config_path = os.path.expanduser("~/.railway/config.json")
with open(config_path) as f:
    config = json.load(f)
    token = config["user"]["token"]

PROJECT_ID = "acf22966-f165-4e4d-a9ba-ce2efef63129"
GRAPHQL_URL = "https://backboard.railway.app/graphql/v2"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

query = """
query project($id: String!) {
  project(id: $id) {
    id
    name
    services {
      edges {
        node {
          id
          name
          deployments {
            edges {
              node {
                id
                status
                createdAt
              }
            }
          }
        }
      }
    }
  }
}
"""

variables = {"id": PROJECT_ID}
response = requests.post(
    GRAPHQL_URL,
    json={"query": query, "variables": variables},
    headers=headers
)

if response.status_code == 200:
    data = response.json()
    if "errors" in data:
        print("Ошибка GraphQL:", data["errors"])
    else:
        project = data["data"]["project"]
        print(f"Проект: {project['name']}\n")

        for edge in project["services"]["edges"]:
            service = edge["node"]
            print(f"Сервис: {service['name']}")
            print(f"  ID: {service['id']}")

            deployments = service["deployments"]["edges"]
            active_count = 0

            for dep_edge in deployments[:5]:  # Последние 5 deployments
                dep = dep_edge["node"]
                status = dep["status"]
                if status in ["SUCCESS", "ACTIVE", "RUNNING"]:
                    active_count += 1
                    print(f"  ✅ АКТИВНЫЙ deployment: {dep['id'][:20]}... | {status} | {dep['createdAt']}")
                elif status in ["BUILDING", "DEPLOYING"]:
                    print(f"  🔄 В процессе: {dep['id'][:20]}... | {status} | {dep['createdAt']}")
                else:
                    print(f"  ⏹️  {status}: {dep['id'][:20]}... | {dep['createdAt']}")

            if active_count > 1:
                print(f"  ⚠️  ПРОБЛЕМА: {active_count} активных deployments одновременно!")

            print()

else:
    print(f"HTTP ошибка {response.status_code}: {response.text}")
