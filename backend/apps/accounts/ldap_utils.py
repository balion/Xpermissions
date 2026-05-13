import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def get_ldap_connection():
    """Open and return an authenticated ldap3 Connection."""
    import ldap3

    server = ldap3.Server(settings.LDAP_SERVER_URI, get_info=ldap3.ALL)
    conn = ldap3.Connection(
        server,
        user=settings.LDAP_BIND_DN or None,
        password=settings.LDAP_BIND_PASSWORD or None,
        auto_bind=True,
    )
    return conn


def search_ldap_users(query: str) -> list[dict]:
    """
    Search LDAP for users matching `query` against email, first name,
    last name, and username attributes.

    Returns a list of dicts: {email, first_name, last_name, username, dn}.
    Only entries with a non-empty email are included.
    """
    import ldap3

    email_attr = settings.LDAP_ATTR_EMAIL
    fn_attr = settings.LDAP_ATTR_FIRST_NAME
    ln_attr = settings.LDAP_ATTR_LAST_NAME
    un_attr = settings.LDAP_ATTR_USERNAME

    safe_query = ldap3.utils.conv.escape_filter_chars(query)
    search_filter = (
        f'(&(objectClass=person)'
        f'(|({email_attr}=*{safe_query}*)'
        f'({fn_attr}=*{safe_query}*)'
        f'({ln_attr}=*{safe_query}*)'
        f'({un_attr}=*{safe_query}*)))'
    )

    conn = get_ldap_connection()
    try:
        conn.search(
            search_base=settings.LDAP_SEARCH_BASE,
            search_filter=search_filter,
            attributes=[email_attr, fn_attr, ln_attr, un_attr],
            size_limit=200,
        )
        results = []
        for entry in conn.entries:
            email = _str_attr(entry, email_attr).lower()
            if not email:
                continue
            results.append({
                'email': email,
                'first_name': _str_attr(entry, fn_attr),
                'last_name': _str_attr(entry, ln_attr),
                'username': _str_attr(entry, un_attr),
                'dn': entry.entry_dn,
            })
        return results
    finally:
        conn.unbind()


def _str_attr(entry, attr_name: str) -> str:
    try:
        val = getattr(entry, attr_name, None)
        return str(val) if val else ''
    except Exception:
        return ''
