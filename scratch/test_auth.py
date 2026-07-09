import requests

url_signup = "http://127.0.0.1:8000/signup"
url_signin = "http://127.0.0.1:8000/signin"

# 1. Test short password
print("Testing short password registration...")
try:
    res = requests.post(url_signup, json={"username": "test_short@guesin.ai", "password": "abc!"})
    print("Status:", res.status_code)
    print("Response:", res.json())
except Exception as e:
    print("Error:", e)

# 2. Test no symbol password
print("\nTesting password with no symbols...")
try:
    res = requests.post(url_signup, json={"username": "test_nosym@guesin.ai", "password": "password123"})
    print("Status:", res.status_code)
    print("Response:", res.json())
except Exception as e:
    print("Error:", e)

# 3. Test valid registration
print("\nTesting valid registration...")
try:
    res = requests.post(url_signup, json={"username": "test_user@guesin.ai", "password": "password123!"})
    print("Status:", res.status_code)
    print("Response:", res.json())
except Exception as e:
    print("Error:", e)

# 4. Test login with wrong credentials
print("\nTesting login with wrong credentials...")
try:
    res = requests.post(url_signin, json={"username": "test_user@guesin.ai", "password": "wrongpassword!"})
    print("Status:", res.status_code)
    print("Response:", res.json())
except Exception as e:
    print("Error:", e)

# 5. Test login with correct credentials
print("\nTesting login with correct credentials...")
try:
    res = requests.post(url_signin, json={"username": "test_user@guesin.ai", "password": "password123!"})
    print("Status:", res.status_code)
    print("Response:", res.json())
except Exception as e:
    print("Error:", e)

# 6. Test default operator login
print("\nTesting default operator login...")
try:
    res = requests.post(url_signin, json={"username": "operator@guesin.ai", "password": "password123!"})
    print("Status:", res.status_code)
    print("Response:", res.json())
except Exception as e:
    print("Error:", e)
