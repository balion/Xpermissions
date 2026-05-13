# SAML configuration files

This directory holds files required by the SAML 2.0 Service Provider (SP).

## Files

| File | Description |
|---|---|
| `idp_metadata.xml` | IdP metadata — **replace with the real file from your IdP** |
| `sp_cert.pem` | SP public certificate — generated locally, not committed |
| `sp_key.pem` | SP private key — generated locally, **never commit** |

## Generate SP certificate and key

```bash
cd saml/
openssl req -x509 -newkey rsa:2048 -keyout sp_key.pem -out sp_cert.pem \
  -days 3650 -nodes -subj "/CN=admin-Xpermisions-sp"
```

## SP metadata URL

Once the server is running, the SP metadata is available at:

```
http://localhost:8000/saml2/metadata/
```

Register this URL (or its XML content) with your IdP as the Service Provider.

## Attribute mapping

The default `SAML_ATTRIBUTE_MAPPING` in `settings/base.py` expects these
SAML attributes from the IdP:

| SAML attribute | Maps to |
|---|---|
| `mail` | `email` (login identifier) |
| `givenName` | `first_name` |
| `sn` | `last_name` |
| `cn` | `username` |

Adjust `SAML_ATTRIBUTE_MAPPING` in settings if your IdP uses different names
(e.g. Azure AD uses `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress`).
