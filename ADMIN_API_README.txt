Afghan Top backend updated with admin mobile API endpoints.

Added routes:
- /api/v1/admin/auth/login/
- /api/v1/admin/auth/me/
- /api/v1/admin/dashboard/
- /api/v1/admin/users/
- /api/v1/admin/users/<id>/
- /api/v1/admin/users/<id>/decision/
- /api/v1/admin/users/<id>/credit-adjustment/
- /api/v1/admin/topups/
- /api/v1/admin/settlements/
- /api/v1/admin/notifications/send/

Before deploying:
1. Push this backend to your GitHub repo connected to Render.
2. Redeploy on Render.
3. Create or edit an admin user in Django Admin with:
   - is_active = True
   - is_staff = True
   - role = admin  (recommended)
4. Test this URL after deploy:
   https://your-domain/api/v1/admin/auth/login/
   A GET request should return 405 Method Not Allowed. That means the route exists.

Login request body for Flutter admin app:
{
  "username_or_mobile": "admin",
  "password": "yourpassword"
}
