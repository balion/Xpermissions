from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView

from apps.accounts.forms import LoginForm


class CustomLoginView(FormView):
    """Local email/password login — for CLI-created accounts only."""
    template_name = 'accounts/login.html'
    form_class = LoginForm
    success_url = reverse_lazy('dashboard:index')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        if user.status == 'locked':
            messages.error(self.request, 'Your account is locked. Contact an administrator.')
            return self.form_invalid(form)
        login(self.request, user)
        return super().form_valid(form)


class CustomLogoutView(LoginRequiredMixin, View):
    def get(self, request):
        backend = request.session.get('_auth_user_backend', '')
        if 'SamlBackend' in backend:
            # Let djangosaml2 handle SAML Single Logout; it will call
            # Django's logout() itself after completing the SLO flow.
            return redirect('/saml2/logout/')
        logout(request)
        return redirect('accounts:login')


class CustomPasswordResetView(PasswordResetView):
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/password_reset_email.html'
    success_url = reverse_lazy('accounts:password_reset_done')


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'
