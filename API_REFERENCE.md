# API Quick Reference

## Base URL
```
http://localhost:8000/api
```

## Authentication Endpoints

### 1. Sign Up
- **Endpoint**: `POST /auth/signup/`
- **Request Body**:
  ```json
  {
    "username": "string (required, unique)",
    "email": "string (required, unique, valid email)",
    "password": "string (required, min 8 chars)",
    "confirm_password": "string (required, must match password)"
  }
  ```
- **Response** (201 Created):
  ```json
  {
    "message": "Signup successful.",
    "user": {
      "id": number,
      "username": "string",
      "email": "string"
    }
  }
  ```
- **Error Cases**:
  - `400`: Missing required fields
  - `400`: Username/email already exists
  - `400`: Passwords don't match
  - `400`: Password validation failed

---

### 2. Sign In
- **Endpoint**: `POST /auth/signin/`
- **Request Body**:
  ```json
  {
    "identifier": "string (email or username)",
    "password": "string"
  }
  ```
- **Alternative (identifier by field)**:
  ```json
  {
    "email": "string",
    "password": "string"
  }
  ```
  OR
  ```json
  {
    "username": "string",
    "password": "string"
  }
  ```
- **Response** (200 OK):
  ```json
  {
    "message": "Sign in successful.",
    "user": {
      "id": number,
      "username": "string",
      "email": "string"
    }
  }
  ```
- **Error Cases**:
  - `400`: Missing identifier/email/username and password
  - `401`: Invalid credentials

---

### 3. Forgot Password
- **Endpoint**: `POST /auth/forgot-password/`
- **Request Body**:
  ```json
  {
    "email": "string (required)"
  }
  ```
- **Response** (200 OK):
  ```json
  {
    "message": "If this email exists, reset instructions were generated.",
    "reset": {
      "uid": "string (base64 encoded user id)",
      "token": "string (password reset token)"
    }
  }
  ```
- **Note**: Returns same message regardless of email existence (security best practice)
- **Error Cases**:
  - `400`: Email is required

---

### 4. Reset Password
- **Endpoint**: `POST /auth/reset-password/`
- **Request Body**:
  ```json
  {
    "uid": "string (from forgot password)",
    "token": "string (from forgot password)",
    "new_password": "string (required, min 8 chars)",
    "confirm_password": "string (required, must match new_password)"
  }
  ```
- **Response** (200 OK):
  ```json
  {
    "message": "Password reset successful."
  }
  ```
- **Error Cases**:
  - `400`: Missing uid, token, or new_password
  - `400`: Passwords don't match
  - `400`: Invalid reset link
  - `400`: Invalid or expired token
  - `400`: Password validation failed

---

### 5. Social Sign Up (Google/Facebook)
- **Endpoint**: `POST /auth/social/signup/`
- **Request Body**:
  ```json
  {
    "provider": "google" or "facebook",
    "token": "string (or id_token or access_token)"
  }
  ```
- **Response** (201 Created or 200 OK):
  ```json
  {
    "message": "Social sign up successful.",
    "created": true/false,
    "user": {
      "id": number,
      "username": "string",
      "email": "string"
    },
    "provider": "string"
  }
  ```
- **Error Cases**:
  - `400`: Missing provider or token
  - `400`: Invalid token
  - `400`: Email missing from social account

---

### 6. Social Sign In (Google/Facebook)
- **Endpoint**: `POST /auth/social/signin/`
- **Request Body**:
  ```json
  {
    "provider": "google" or "facebook",
    "token": "string (or id_token or access_token)"
  }
  ```
- **Response** (200 OK):
  ```json
  {
    "message": "Social sign in successful.",
    "user": {
      "id": number,
      "username": "string",
      "email": "string"
    },
    "provider": "string"
  }
  ```
- **Error Cases**:
  - `400`: Missing provider or token
  - `400`: Invalid token
  - `404`: No account found (use social signup first)

---

## Athletes API Endpoint

### Get All Athletes
- **Endpoint**: `GET /athletes/`
- **Response** (200 OK):
  ```json
  [
    {
      "id": number,
      "name": "string",
      "age": number,
      "gender": "string",
      "height": number,
      "weight": number,
      "body_type": "string",
      "swimming_records": [],
      "basketball_records": [],
      "fitness_profile": {}
    }
  ]
  ```

---

## Common HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK - Request succeeded |
| 201 | Created - Resource created successfully |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Invalid credentials |
| 404 | Not Found - Resource doesn't exist |
| 500 | Server Error - Backend error |

---

## CORS Configuration

- **Type**: Enabled for all origins
- **Methods**: GET, POST, PUT, DELETE, PATCH, OPTIONS
- **Headers**: Content-Type, application/json

---

## Frontend Implementation Notes

1. **LocalStorage**: User data is stored in `auth_user` key after successful login
2. **API Base**: Frontend uses `http://localhost:8000/api/auth`
3. **Error Handling**: All errors are displayed via `alert()` (can be improved with toast notifications)
4. **Redirects**: Users are redirected based on authentication state
5. **Password Reset**: Uses URL parameters (`uid`, `token`) to maintain context

---

## Testing Examples

### cURL Sign Up
```bash
curl -X POST http://localhost:8000/api/auth/signup/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "email": "john@example.com",
    "password": "SecurePass123",
    "confirm_password": "SecurePass123"
  }'
```

### cURL Sign In
```bash
curl -X POST http://localhost:8000/api/auth/signin/ \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "john@example.com",
    "password": "SecurePass123"
  }'
```

### JavaScript Fetch
```javascript
const response = await fetch('http://localhost:8000/api/auth/signin/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    identifier: 'john@example.com',
    password: 'SecurePass123'
  })
});

const data = await response.json();
console.log(data);
```
