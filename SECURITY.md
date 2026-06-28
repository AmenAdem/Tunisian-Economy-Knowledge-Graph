# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it by:

1. **DO NOT** open a public GitHub issue
2. Email the maintainers directly (see contact information in README)
3. Include detailed information about the vulnerability
4. Allow reasonable time for a fix before public disclosure

## Supported Versions

This is an MVP project. Security updates are provided on a best-effort basis.

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |

## Security Best Practices

### For Development

1. **Never commit secrets**:
   - Use `.env` files (which are gitignored)
   - Never commit API keys, passwords, or tokens
   - Use `.env.example` templates with placeholder values

2. **API Keys**:
   - Get OpenRouter API key from: https://openrouter.ai/keys
   - Store in `.env` file, never in code
   - Rotate keys regularly
   - Use different keys for dev/staging/prod

3. **Database Credentials**:
   - Change default Neo4j password (`changeme`)
   - Use strong passwords in production
   - Never commit actual passwords to git

4. **Environment Files**:
   - `.env` - Your local secrets (gitignored)
   - `.env.example` - Template with placeholders (committed)
   - `.env.docker.example` - Docker template (committed)

### For Production

1. **Authentication**: This MVP has NO authentication. Add proper auth before production use.

2. **Environment Variables**: Use secure environment variable management:
   - AWS Secrets Manager
   - HashiCorp Vault
   - Kubernetes Secrets
   - Docker Secrets

3. **Network Security**:
   - Use HTTPS/TLS for all external connections
   - Restrict Neo4j port access (7687)
   - Use firewalls and network policies

4. **Neo4j Security**:
   - Use strong passwords
   - Enable SSL/TLS for Bolt connections
   - Restrict network access
   - Regular backups
   - Enable audit logging

5. **API Security**:
   - Implement authentication (OAuth2, JWT)
   - Add rate limiting
   - Use CORS properly
   - Validate all inputs
   - Sanitize outputs

6. **Docker Security**:
   - Don't run containers as root
   - Use specific image versions (not `latest`)
   - Scan images for vulnerabilities
   - Use Docker secrets for sensitive data
   - Limit resource usage

### Common Vulnerabilities to Avoid

1. **SQL/Cypher Injection**: Always parameterize queries
2. **XSS**: Sanitize user inputs in frontend
3. **Exposed Secrets**: Use environment variables, never hardcode
4. **Insecure Dependencies**: Regular `pip audit` and `npm audit`
5. **SSRF**: Validate and restrict scraper URLs
6. **Path Traversal**: Validate file paths in uploads
7. **Denial of Service**: Implement rate limiting

## Security Checklist for Contributors

Before submitting a PR:

- [ ] No secrets committed (API keys, passwords, tokens)
- [ ] No hardcoded credentials in code
- [ ] Environment variables used for sensitive config
- [ ] Input validation implemented
- [ ] Dependencies are up to date
- [ ] No known vulnerable dependencies
- [ ] SQL/Cypher queries are parameterized
- [ ] User input is sanitized
- [ ] Error messages don't leak sensitive info

## Automated Security Checks

We recommend running these tools:

```bash
# Python security audit
pip install safety
safety check

# Check for secrets in git history
pip install detect-secrets
detect-secrets scan

# Dependency vulnerabilities
pip audit

# Frontend security
cd frontend
npm audit
```

## Known Limitations (MVP)

This is an MVP with known security limitations:

1. **No Authentication**: API endpoints are open
2. **No Rate Limiting**: Vulnerable to abuse
3. **No Input Validation**: Limited validation on user inputs
4. **Default Credentials**: Uses weak defaults for development
5. **No Encryption**: Data transmitted in plain text (in dev)
6. **No Audit Logging**: No security event logging
7. **Open CORS**: Frontend accepts all origins in dev mode

**DO NOT use this in production without addressing these issues.**

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP API Security](https://owasp.org/www-project-api-security/)
- [Neo4j Security Guide](https://neo4j.com/docs/operations-manual/current/security/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)

## Contact

For security issues, please contact the maintainers privately before public disclosure.
