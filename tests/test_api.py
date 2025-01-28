import json
from http import HTTPStatus
import pytest
import requests
from faker import Faker

import resource
from app.models.user import User


# Фикстуры
@pytest.fixture(scope="module")
def fill_test_data(app_url):
    with open(resource.path("users.json")) as f:
        test_data_users = json.load(f)
    api_users = []
    for user in test_data_users:
        response = requests.post(f"{app_url}/api/users/create", json=user)
        response.raise_for_status()
        api_users.append(response.json())
    user_ids = [user["id"] for user in api_users]
    yield user_ids
    for user_id in user_ids:
        requests.delete(f"{app_url}/api/users/delete/{user_id}")


@pytest.fixture
def users(app_url):
    response = requests.get(f"{app_url}/api/users/")
    response.raise_for_status()
    return response.json()


@pytest.fixture
def create_user_fixture(app_url):
    fake = Faker()
    new_user = {
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "email": fake.email(),
        "avatar": fake.image_url(),
    }

    # Создаем пользователя
    response = requests.post(f"{app_url}/api/users/create", json=new_user)
    response.raise_for_status()
    created_user = response.json()

    yield created_user

    # Удаляем пользователя после теста
    response = requests.delete(f"{app_url}/api/users/delete/{created_user['id']}")
    if response.status_code != HTTPStatus.NOT_FOUND:
        response.raise_for_status()


# Вспомогательные функции
def check_keys(data, required_keys):
    for key in required_keys:
        assert key in data, f"Ответ не содержит '{key}' key"


def validate_user(user):
    assert isinstance(user, dict), f"Ожидал словарь, пришел: {type(user)}"
    validated_user = User.model_validate(user)
    # Проверка обязательных полей
    assert 'id' in user
    assert 'email' in user
    assert 'first_name' in user
    assert 'last_name' in user
    assert 'avatar' in user


def check_unique_ids(users_list):
    user_ids = [user["id"] for user in users_list]
    assert len(user_ids) == len(set(user_ids)), "Duplicate user IDs found"


# Тесты
@pytest.mark.usefixtures("fill_test_data")
def test_users(app_url):
    response = requests.get(f"{app_url}/api/users/")
    response.raise_for_status()
    data = response.json()

    # Проверка наличия ключей
    check_keys(data, ['items', 'total', 'page', 'size', 'pages'])

    user_list = data['items']
    expected_items_on_page = min(data['size'], data['total'])
    assert len(
        user_list) == expected_items_on_page, f"Expected {expected_items_on_page} items on page, got {len(user_list)}"

    for user in user_list:
        validate_user(user)


@pytest.mark.usefixtures("fill_test_data")
def test_users_no_duplicates(users):
    user_list = users.get('items', [])
    assert len(user_list) > 0, "No users found in the response"
    check_unique_ids(user_list)


def test_user(app_url, fill_test_data):
    for user_id in (fill_test_data[0], fill_test_data[-1]):
        response = requests.get(f"{app_url}/api/users/{user_id}")
        response.raise_for_status()
        user = response.json()
        validate_user(user)


@pytest.mark.parametrize("user_id", [13])
def test_user_nonexistent_values(app_url, user_id):
    response = requests.get(f"{app_url}/api/users/{user_id}")
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize("user_id", [-1, 0, "fafaf"])
def test_user_invalid_values(app_url, user_id):
    response = requests.get(f"{app_url}/api/users/{user_id}")
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# Тест на создание пользователя
def test_create_user(app_url, create_user_fixture):
    created_user = create_user_fixture
    validate_user(created_user)
    # Проверяем, что пользователь создан
    response = requests.get(f"{app_url}/api/users/{created_user['id']}")
    response.raise_for_status()
    fetched_user = response.json()
    assert fetched_user == created_user


# Тест на удаление пользователя
def test_delete_user(app_url, create_user_fixture):
    created_user = create_user_fixture
    # Удаляем пользователя
    response = requests.delete(f"{app_url}/api/users/delete/{created_user['id']}")
    response.raise_for_status()
    # Проверяем, что пользователь удален
    response = requests.get(f"{app_url}/api/users/{created_user['id']}")
    assert response.status_code == HTTPStatus.NOT_FOUND


# Тест на изменение пользователя
def test_update_user(app_url, create_user_fixture):
    created_user = create_user_fixture
    fake = Faker()
    updated_user = {
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "email": fake.email(),
        "avatar": fake.image_url(),
    }
    response = requests.patch(f"{app_url}/api/users/update/{created_user['id']}", json=updated_user)
    response.raise_for_status()
    patched_user = response.json()
    # Проверяем, что данные пользователя изменились
    response = requests.get(f"{app_url}/api/users/{created_user['id']}")
    response.raise_for_status()
    fetched_user = response.json()
    assert fetched_user == patched_user


# Тест на ошибку 405
def test_method_not_allowed(app_url):
    response = requests.put(f"{app_url}/api/users/create")
    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


# Тест на ошибки 404 и 422 на delete и patch
@pytest.mark.parametrize("user_id", [-1, 0, "invalid_id"])
def test_delete_invalid_user(app_url, user_id):
    response = requests.delete(f"{app_url}/api/users/delete/{user_id}")
    assert response.status_code in (HTTPStatus.NOT_FOUND, HTTPStatus.UNPROCESSABLE_ENTITY)


@pytest.mark.parametrize("user_id", [-1, 0, "invalid_id"])
def test_patch_invalid_user(app_url, user_id):
    response = requests.patch(f"{app_url}/api/users/update/{user_id}", json={})
    assert response.status_code in (HTTPStatus.NOT_FOUND, HTTPStatus.UNPROCESSABLE_ENTITY)


# Тест на ошибку 404 на удаленного пользователя
def test_get_deleted_user(app_url, create_user_fixture):
    created_user = create_user_fixture
    # Удаляем пользователя
    response = requests.delete(f"{app_url}/api/users/delete/{created_user['id']}")
    response.raise_for_status()
    # Проверяем, что пользователь удален
    response = requests.get(f"{app_url}/api/users/{created_user['id']}")
    assert response.status_code == HTTPStatus.NOT_FOUND


# Тест на валидность тестовых данных (email, url)
def test_validity_of_test_data(app_url, create_user_fixture):
    created_user = create_user_fixture
    validate_user(created_user)
