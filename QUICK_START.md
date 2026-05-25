# Quick Start: 5-Minute Setup

## Start Backend (Terminal 1)

```bash
cd /Users/omartamer/Downloads/dasher-1.0.0/backend
python3 manage.py runserver 0.0.0.0:8000
```

**Expected**: "Starting development server at http://0.0.0.0:8000/"

## Start Frontend (Terminal 2)

```bash
cd /Users/omartamer/Downloads/dasher-1.0.0
npm install  # Only first time
npm start
```

**Expected**: Frontend starts on http://localhost:3000

## Test It Now

### Sign Up
1. Open: http://localhost:3000/src/pages/authentication/sign-up.html
2. Enter:
   - Username: `testuser`
   - Email: `test@example.com`
   - Password: `Test123456`
   - Confirm: `Test123456`
3. Click "Sign Up"
4. Should redirect to Sign In page

### Sign In
1. Open: http://localhost:3000/src/pages/authentication/sign-in.html
2. Enter:
   - Email: `test@example.com`
   - Password: `Test123456`
3. Click "Sign In"
4. Should redirect to home page and store user in localStorage

### Check LocalStorage
1. Open Browser DevTools: F12
2. Go to: Application → Local Storage → Your domain
3. Should see `auth_user` with your user data

### Forgot Password
1. Open: http://localhost:3000/src/pages/authentication/forget-password.html
2. Enter: `test@example.com`
3. Click "Reset Password"
4. Should redirect to reset page with URL params
5. Set new password and confirm
6. Click "Reset Password"
7. Should redirect to Sign In page
8. Sign in with new password

---

## API Health Check

```bash
# Test API is responding
curl http://localhost:8000/api/athletes/

# Test sign up endpoint
curl -X POST http://localhost:8000/api/auth/signup/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "quicktest",
    "email": "quick@test.com",
    "password": "QuickTest123",
    "confirm_password": "QuickTest123"
  }'
```

---

## Common Issues

| Issue | Solution |
|-------|----------|
| `python: command not found` | Use `python3` instead |
| Port 8000 in use | `python3 manage.py runserver 0.0.0.0:8001` |
| Module not found | `pip install django djangorestframework django-cors-headers` |
| CORS errors | CORS already enabled - check port configuration |
| API not responding | Verify Django running with `curl http://localhost:8000/` |

---

## Next: Read Full Documentation

- **Testing Guide**: See `AUTHENTICATION_TESTING_GUIDE.md`
- **API Reference**: See `API_REFERENCE.md`
- **Setup Details**: See `SETUP_GUIDE.md`
- **Summary**: See `AUTHENTICATION_SUMMARY.md`

---

## What's Been Integrated

✓ Sign Up with validation  
✓ Sign In with localStorage  
✓ Forgot Password with token generation  
✓ Reset Password with token validation  
✓ Error handling & user feedback  
✓ CORS enabled  
✓ All APIs tested & working  

---

**Ready to go!** 🚀
