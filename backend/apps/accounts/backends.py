import logging

from django.contrib.auth import get_user_model
from djangosaml2.backends import Saml2Backend

from apps.accounts.models import STATUS_ACTIVE

logger = logging.getLogger(__name__)


class SamlBackend(Saml2Backend):
    """
    Extends djangosaml2's Saml2Backend.

    New users are auto-created on first SSO login:
      - status=active, is_active=True
      - unusable password (SSO is the only login path)
      - no roles assigned (admin must assign roles separately)

    Existing users (pre-provisioned via LDAP import or CLI) are
    authenticated as-is without overwriting their existing data.
    """

    def configure_user(self, user, attributes, attribute_mapping):
        """Called by djangosaml2 only when the user is newly created."""
        user = super().configure_user(user, attributes, attribute_mapping)
        self._ensure_unique_username(user)
        user.status = STATUS_ACTIVE
        user.is_active = True
        user.set_unusable_password()
        user.save()
        logger.info('New SSO user auto-created: %s', user.email)
        return user

    def _ensure_unique_username(self, user):
        """Derive a unique username from the email local-part if not already set."""
        if user.username:
            return
        user_model = get_user_model()
        base = (user.email or 'user').split('@')[0]
        username = base
        n = 1
        while user_model.objects.filter(username=username).exclude(pk=user.pk or 0).exists():
            username = f'{base}{n}'
            n += 1
        user.username = username
