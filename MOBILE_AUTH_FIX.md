# Mobile Authentication Fix

## Problem
Mobile users receiving "username and password is incorrect" error when authenticating in production, while desktop users can login successfully.

## Root Cause
The issue was caused by **missing cookie security settings** for JWT authentication in production. Mobile browsers and native apps are stricter about cookie handling than desktop browsers, especially when:

1. Cookies are not marked as `Secure` (required for HTTPS)
2. SameSite policy is not properly configured for cross-origin requests
3. Cookie credentials are not allowed in CORS settings

## Solution Applied

### 1. Updated Production Settings (`config/settings/production.py`)
Added the following cookie security configurations:

```python
# CORS settings
CORS_ALLOW_CREDENTIALS = True  # Required for cookie-based auth

# JWT Cookie settings for production
JWT_AUTH_SECURE = True          # Send cookies only over HTTPS
JWT_AUTH_HTTPONLY = True        # Protect from XSS attacks
JWT_AUTH_SAMESITE = 'None'      # Allow cross-origin cookie sending

# Session cookie settings
SESSION_COOKIE_SECURE = True    # Send session cookies only over HTTPS
SESSION_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_HTTPONLY = True

# CSRF cookie settings
CSRF_COOKIE_SECURE = True       # Send CSRF cookies only over HTTPS
CSRF_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_HTTPONLY = False    # Must be False for JavaScript access
```

### 2. Environment Variables to Set
In your Render dashboard or production environment, ensure these variables are set:

```bash
# Required for production
CSRF_TRUSTED_ORIGINS=https://your-backend.onrender.com,https://your-frontend-domain.com
ALLOWED_HOSTS=your-backend.onrender.com,localhost,127.0.0.1
```

## Deployment Steps

1. **Update Environment Variables** in your Render dashboard:
   - Go to your service → Environment tab
   - Add/update `CSRF_TRUSTED_ORIGINS` with your actual backend and frontend URLs
   - Add/update `ALLOWED_HOSTS` with your actual backend domain

2. **Redeploy the Application**:
   ```bash
   git add .
   git commit -m "Fix: Add cookie security settings for mobile authentication"
   git push origin main
   ```

3. **Clear Browser/App Cache** on mobile devices after deployment

## Testing

### Test on Mobile
1. Clear app cache/data or use incognito mode
2. Try logging in with valid credentials
3. Check browser DevTools → Network → Response Headers for Set-Cookie headers
4. Verify cookies include `Secure`, `HttpOnly`, and `SameSite=None` attributes

### Expected Cookie Headers
```
Set-Cookie: phonenumber-auth=<token>; Secure; HttpOnly; SameSite=None
Set-Cookie: phonenumber-refresh-token=<token>; Secure; HttpOnly; SameSite=None
```

## Why This Happens on Mobile Only

Mobile browsers and native apps:
- Enforce stricter security policies
- Block cookies without proper `Secure` flag over HTTPS
- Have stricter SameSite cookie policies
- May use different networking stacks than desktop browsers

## Alternative Solution (If Issues Persist)

If you're building a **native mobile app** (React Native, Flutter, etc.), consider using **token-based authentication** instead of cookies:

1. Switch to `TokenAuthentication` instead of `JWTCookieAuthentication`
2. Store tokens in secure storage (AsyncStorage, SecureStore, Keychain)
3. Send tokens in Authorization header: `Authorization: Bearer <token>`

To implement this, update `config/settings/base.py`:
```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # For native apps, use token in header instead
        "rest_framework.authentication.TokenAuthentication",
        # Keep cookie auth for web
        "dj_rest_auth.jwt_auth.JWTCookieAuthentication",
    ),
}
```

## Additional Notes

- **SameSite=None** requires **Secure=True** and **HTTPS**
- All requests must be made over HTTPS in production
- Frontend domain must be included in `CSRF_TRUSTED_ORIGINS`
- For mobile apps making direct API calls, ensure CORS headers allow your app's origin

## Verification

After deploying, verify the fix by:
1. Opening DevTools Network tab on mobile browser
2. Logging in
3. Checking response headers contain proper cookie settings
4. Confirming subsequent authenticated requests include cookies

## Related Files Modified
- `config/settings/production.py` - Added cookie security settings
- `.env.render` - Added environment variable examples
