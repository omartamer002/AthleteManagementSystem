# Authentication Testing Guide

## Overview
The authentication system is fully integrated between the frontend and Django backend. This guide will help you test all authentication flows.

## Prerequisites
1. Django server running on `http://localhost:8000`
2. Frontend accessible at `http://localhost:3000` (or your configured port)
3. Both servers are on the same network or localhost

## Testing Flows

### 1. Sign Up Flow

**URL**: `http://localhost:3000/src/pages/authentication/sign-up.html`

**Test Steps**:
1. Enter a unique username (e.g., `testuser123`)
2. Enter a valid email (e.g., `testuser@example.com`)
3. Enter password (min 8 characters recommended)
4. Confirm password (must match)
5. Check "Terms of Use & Privacy Policy"
6. Click "Sign Up"

**Expected Results**:
- Success message appears
- User is redirected to Sign In page
- User can now sign in with the registered credentials

**Test Edge Cases**:
- Duplicate username → Error: "Username already exists"
- Duplicate email → Error: "Email already exists"
- Mismatched passwords → Error: "password and confirm_password do not match"
- Weak password → Error: "Password validation failed" (with specific requirements)

---

### 2. Sign In Flow

**URL**: `http://localhost:3000/src/pages/authentication/sign-in.html`

**Test Steps**:
1. Enter email or username in the "Email" field
2. Enter password
3. Optionally check "Remember me"
4. Click "Sign In"

**Expected Results**:
- Success message appears
- User data is stored in browser's localStorage
- User is redirected to home page (`../../index.html`)

**Test Edge Cases**:
- Invalid email → Error: "Invalid credentials"
- Correct email, wrong password → Error: "Invalid credentials"
- Empty fields → Error: "identifier and password are required"

**localStorage Check** (Open browser DevTools → Application → Local Storage):
```javascript
// The following data should be stored:
auth_user: {
  "id": 2,
  "username": "testuser",
  "email": "testuser@example.com"
}
```

---

### 3. Forgot Password Flow

**URL**: `http://localhost:3000/src/pages/authentication/forget-password.html`

**Test Steps**:
1. Enter the email address associated with your account
2. Click "Reset Password"

**Expected Results**:
- Success message appears with "reset instructions were generated"
- User is automatically redirected to reset-password page with uid and token in URL
- URL format: `reset-password.html?uid=...&token=...`

**Test Cases**:
- Valid email that exists → Shows success message with redirect
- Non-existent email → Shows same message (doesn't leak account existence)
- Empty email field → Error: "email is required"

---

### 4. Reset Password Flow

**URL**: `http://localhost:3000/src/pages/authentication/reset-password.html?uid=Mg&token=...`

**Prerequisites**:
- Must have the correct `uid` and `token` from the Forgot Password flow
- URL parameters are automatically handled by the frontend

**Test Steps**:
1. Enter new password (minimum 8 characters)
2. Confirm new password (must match)
3. Click "Reset Password"

**Expected Results**:
- Success message: "Password reset successful"
- User is redirected to Sign In page
- User can now sign in with the new password

**Test Cases**:
- Passwords don't match → Error: "new_password and confirm_password do not match"
- Password too short → Error: "Password validation failed" with requirements
- Invalid/expired token → Error: "Invalid or expired token"
- Missing uid or token in URL → Alert: "Invalid reset link"

---

### 5. Password Toggle Feature

**Available on**: Sign In, Sign Up, Reset Password pages

**Test Steps**:
1. Click the eye icon in the password field
2. Verify password becomes visible
3. Click eye icon again to hide

**Expected Results**:
- Password visibility toggles properly
- Input type changes between `password` and `text`

---

## API Testing (Using curl)

### Sign Up
```bash
curl -X POST http://localhost:8000/api/auth/signup/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "newuser@example.com",
    "password": "password123",
    "confirm_password": "password123"
  }'
```

### Sign In
```bash
curl -X POST http://localhost:8000/api/auth/signin/ \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "newuser@example.com",
    "password": "password123"
  }'
```

### Forgot Password
```bash
curl -X POST http://localhost:8000/api/auth/forgot-password/ \
  -H "Content-Type: application/json" \
  -d '{"email": "newuser@example.com"}'
```

### Reset Password
```bash
curl -X POST http://localhost:8000/api/auth/reset-password/ \
  -H "Content-Type: application/json" \
  -d '{
    "uid": "VALUE_FROM_FORGOT_PASSWORD",
    "token": "VALUE_FROM_FORGOT_PASSWORD",
    "new_password": "newpassword123",
    "confirm_password": "newpassword123"
  }'
```

---

## Common Issues & Troubleshooting

### Issue: "Failed to fetch from API"
**Cause**: Django server not running or wrong port
**Solution**: 
- Verify Django is running: `http://localhost:8000/api/auth/signup/` should return a 405 Method Not Allowed error
- Check that the API_BASE URL in frontend matches your Django server address

### Issue: CORS Errors
**Cause**: Cross-Origin Resource Sharing blocked
**Solution**: 
- CORS is already configured in Django settings (`CORS_ALLOW_ALL_ORIGINS = True`)
- Ensure your frontend is running on a different port than the backend

### Issue: "Invalid credentials" when email is correct
**Cause**: Password might have been changed or user doesn't exist
**Solution**:
- Verify the email exists in the database
- Use the Forgot Password flow to reset password
- Check Django admin to verify user exists: `http://localhost:8000/admin/`

### Issue: Reset link shows "Invalid reset link"
**Cause**: Missing or corrupted uid/token in URL
**Solution**:
- Go through Forgot Password flow again to get new uid and token
- Ensure the URL wasn't truncated or modified

---

## Testing Checklist

- [ ] Sign Up: Valid credentials create new user
- [ ] Sign Up: Duplicate username shows error
- [ ] Sign Up: Duplicate email shows error
- [ ] Sign Up: Mismatched passwords show error
- [ ] Sign In: Valid credentials log in user
- [ ] Sign In: Invalid credentials show error
- [ ] Sign In: User data stored in localStorage
- [ ] Forgot Password: Email field is required
- [ ] Forgot Password: Valid email generates reset link
- [ ] Reset Password: Valid credentials reset password
- [ ] Reset Password: Mismatched passwords show error
- [ ] Reset Password: Invalid token shows error
- [ ] Password visibility toggle works
- [ ] All pages load without console errors
- [ ] Redirect after sign in goes to home page
- [ ] Can sign in with new password after reset

---

## Database

**Location**: `/backend/db.sqlite3`

To view users via Django admin:
1. Create superuser if not exists: `python3 manage.py createsuperuser`
2. Go to `http://localhost:8000/admin/`
3. Login with superuser credentials
4. Navigate to "Users" section

---

## Frontend Files Updated

1. **sign-up.html** - Added form ID and JavaScript handler
2. **sign-in.html** - Already had JavaScript handler
3. **forget-password.html** - Added form ID and JavaScript handler
4. **reset-password.html** - Added form ID and URL parameter parsing

All files include proper error handling and user feedback through alerts and redirects.

---

## Next Steps

1. Test all flows using this guide
2. Consider adding:
   - Better error messages (toasts/notifications instead of alerts)
   - Loading states during API calls
   - Session management for protecting routes
   - Remember me functionality (setting auth token)
   - Social sign-in implementation
