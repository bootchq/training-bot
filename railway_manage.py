#!/usr/bin/env python3
"""
Скрипт для управления Railway сервисами через GraphQL API
"""
import json
import os
import requests

# Читаем конфиг Railway
config_path = os.path.expanduser("~/.railway/config.json")
with open(config_path) as f:
    config = json.load(f)
    token = config["user"]["token"]

# Project ID для training-bot
PROJECT_ID = "acf22966-f165-4e4d-a9ba-ce2efef63129"
ENVIRONMENT_ID = "539defa4-5223-4815-80f9-3c148795288e"

# Railway GraphQL API endpoint
GRAPHQL_URL = "https://backboard.railway.app/graphql/v2"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}


def list_services():
    """Получить список всех сервисов в проекте"""
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
              createdAt
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
            return None
        return data["data"]["project"]
    else:
        print(f"HTTP ошибка {response.status_code}: {response.text}")
        return None


def delete_service(service_id, service_name):
    """Удалить сервис по ID"""
    query = """
    mutation serviceDelete($id: String!) {
      serviceDelete(id: $id)
    }
    """

    variables = {"id": service_id}

    print(f"Удаляю сервис '{service_name}' ({service_id})...")
    response = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers=headers
    )

    if response.status_code == 200:
        data = response.json()
        if "errors" in data:
            print(f"  ❌ Ошибка: {data['errors']}")
            return False
        print(f"  ✅ Сервис '{service_name}' удалён")
        return True
    else:
        print(f"  ❌ HTTP ошибка {response.status_code}: {response.text}")
        return False


def main():
    print("📋 Получаю список сервисов в проекте training-bot...\n")

    project = list_services()
    if not project:
        print("❌ Не удалось получить список сервисов")
        return

    print(f"Проект: {project['name']}")
    print(f"Project ID: {project['id']}\n")

    services = project["services"]["edges"]
    print(f"Найдено сервисов: {len(services)}\n")

    # Список сервисов для удаления (старые)
    TO_DELETE = ["training-bot", "bot-trainer-volume"]

    for edge in services:
        service = edge["node"]
        service_id = service["id"]
        service_name = service["name"]
        created_at = service["createdAt"]

        status = "❌ УДАЛИТЬ" if service_name in TO_DELETE else "✅ ОСТАВИТЬ"
        print(f"{status}: {service_name}")
        print(f"    ID: {service_id}")
        print(f"    Создан: {created_at}\n")

    # Удаляем старые сервисы
    print("\n🗑️  Начинаю удаление старых сервисов...\n")

    for edge in services:
        service = edge["node"]
        service_id = service["id"]
        service_name = service["name"]

        if service_name in TO_DELETE:
            delete_service(service_id, service_name)

    print("\n✅ Готово!")


if __name__ == "__main__":
    main()
