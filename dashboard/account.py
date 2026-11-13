"""Staff account pages in the dashboard design."""
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache


@never_cache
@staff_member_required
def password_change(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    for field in form.fields.values():
        field.widget.attrs.update({"class": "form-control"})
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)  # stay signed in
        messages.success(request, "Password changed.")
        return redirect("dashboard:index")
    return render(request, "dashboard/password_change.html", {"form": form})
