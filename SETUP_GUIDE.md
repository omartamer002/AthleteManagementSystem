# Backend & Frontend Setup Guide

## Prerequisites

- Python 3.8+
- Node.js 14+ and npm (for frontend if using npm-based build)
- macOS/Linux/Windows

---

## Backend Setup (Django)

### 1. Install Python Dependencies

```bash
cd /Users/omartamer/Downloads/dasher-1.0.0/backend

# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install django djangorestframework django-cors-headers python-dotenv google-auth
```

### 2. Apply Migrations

```bash
python3 manage.py migrate
```

### 3. Create Superuser (Admin Account)

```bash
python3 manage.py createsuperuser
# Follow the prompts to create admin user
```

### 4. Start Django Development Server

```bash
python3 manage.py runserver 0.0.0.0:8000
```

**Expected Output**:
```
Starting development server at http://0.0.0.0:8000/
Quit the server with CONTROL-C.
```

**Access Points**:
- API: http://localhost:8000/api/
- Admin: http://localhost:8000/admin/

---

## Frontend Setup

### Option 1: Using Gulp (Current Project Structure)

```bash
cd /Users/omartamer/Downloads/dasher-1.0.0

# Install Node dependencies
npm install

# Start development server
npm start
# OR
gulp
```

**Access**: Frontend will be available at http://localhost:3000 (or configured port)

### Option 2: Direct HTML Access

Simply open the HTML files directly in a browser:
```bash
# macOS
open src/pages/authentication/sign-in.html

# Or navigate using file:// protocol in browser
file:///Users/omartamer/Downloads/dasher-1.0.0/src/pages/authentication/sign-in.html
```

---

## Verification Steps

### 1. Test Backend

```bash
# Test API endpoint
curl http://localhost:8000/api/athletes/

# Should return: [] or a list of athletes

# Test authentication endpoint
curl -X POST http://localhost:8000/api/auth/signup/ \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","password":"test123","confirm_password":"test123"}'
```

### 2. Test Frontend Authentication

1. Open sign-up page: `http://localhost:3000/src/pages/authentication/sign-up.html`
2. Create test account
3. Sign in with the created account
4. Verify user data in browser DevTools (Application → Local Storage)

---

## Directory Structure

```
/Users/omartamer/Downloads/dasher-1.0.0/
├── backend/
│   ├── manage.py
│   ├── db.sqlite3          # SQLite database
│   ├── ams_core/          # Django project settings
│   │   ├── settings.py    # Database, apps, middleware config
│   │   ├── urls.py        # URL routing
│   │   └── wsgi.py        # WSGI application
│   └── athletes/          # Django app
│       ├── auth_views.py  # Authentication endpoints
│       ├── views.py       # API views
│       ├── models.py      # Database models
│       ├── urls.py        # App URL routing
│       └── serializers.py # DRF serializers
│
├── src/
│   ├── index.html
│   ├── pages/
│   │   └── authentication/
│   │       ├── sign-in.html        # Updated ✓
│   │       ├── sign-up.html        # Updated ✓
│   │       ├── forget-password.html # Updated ✓
│   │       └── reset-password.html  # Updated ✓
│   └── assets/
│       ├── css/
│       ├── js/
│       └── images/
│
├── package.json           # Node dependencies
├── gulpfile.js           # Gulp build configuration
├── API_REFERENCE.md      # API documentation
└── AUTHENTICATION_TESTING_GUIDE.md
```

---

## Environment Variables (Optional)

Create `.env` file in `/backend/` for additional configuration:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1
```

Then load in `settings.py`:
```python
import os
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
```

---

## Troubleshooting

### Issue: "command not found: python"
**Solution**: Use `python3` instead
```bash
python3 manage.py runserver 0.0.0.0:8000
```

### Issue: Port 8000 already in use
**Solution**: Use a different port
```bash
python3 manage.py runserver 0.0.0.0:8001
# Then update API_BASE in frontend JavaScript files
```

### Issue: "ModuleNotFoundError: No module named 'django'"
**Solution**: Install dependencies
```bash
pip install -r requirements.txt  # If requirements.txt exists
# OR manually install:
pip install django djangorestframework django-cors-headers
```

### Issue: Frontend can't connect to backend
**Check**:
1. Backend server is running: `curl http://localhost:8000/`
2. CORS is enabled in settings.py
3. API_BASE URL in frontend JavaScript matches backend URL
4. No firewall blocking localhost:8000

### Issue: Database error
**Solution**: Reset database
```bash
rm backend/db.sqlite3
python3 manage.py migrate
python3 manage.py createsuperuser
```

---

## Database Commands

```bash
# Create new migration (after model changes)
python3 manage.py makemigrations

# Apply migrations
python3 manage.py migrate

# View existing migrations
python3 manage.py showmigrations

# Create superuser
python3 manage.py createsuperuser

# Open Django shell
python3 manage.py shell
```

---

## Useful Links

- Django Admin: http://localhost:8000/admin/
- API Root: http://localhost:8000/api/
- Sign In: http://localhost:3000/src/pages/authentication/sign-in.html
- Sign Up: http://localhost:3000/src/pages/authentication/sign-up.html

---

## Next Steps

1. ✓ Backend setup complete
2. ✓ Frontend authentication integrated
3. [ ] Test all authentication flows (see AUTHENTICATION_TESTING_GUIDE.md)
4. [ ] Add session management/token-based auth
5. [ ] Improve error handling (use toast notifications)
6. [ ] Add route protection (check auth before accessing pages)
7. [ ] Implement logout functionality
8. [ ] Test with real frontend build

---

## Support

- Django Docs: https://docs.djangoproject.com/
- DRF Docs: https://www.django-rest-framework.org/
- JavaScript Fetch: https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API
