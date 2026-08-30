<<<<<<< HEAD
# Cluster profile packaging checklist

## Identity

- [ ] Stable reverse-domain-like plugin ID
- [ ] Stable profile ID
- [ ] Semantic version (normally `0.1.0` for a new provider)
- [ ] Correct `requires_app`

## Provider data

- [ ] Only verified paths and scheduler guidance
- [ ] Public documentation/support URLs
- [ ] No credentials, secrets, private endpoints, or personal accounts

## Storage

- [ ] Storage kinds are meaningful and paths use valid placeholders
- [ ] Unknown policies remain `null` or omitted
- [ ] No invented quota command or usage value

## Packaging

- [ ] `manifest.json`, `cluster-profile.json`, and `README.md` are present
- [ ] Every file is declared with the correct role, size, and SHA-256
- [ ] No undeclared files exist
- [ ] Version directory is new and immutable

## Validation

- [ ] `python scripts/validate_registry.py`
- [ ] `python -m pytest`
- [ ] `ruff check scripts tests`

## Pull request

- [ ] Public sources are linked in the PR or package documentation
- [ ] No old published version was modified
- [ ] Registry entry and manifest agree
=======
- [ ] no credentials, hosts, accounts, or measured data
- [ ] only verified public paths and documentation
- [ ] quota disabled unless a reviewed backend exists
- [ ] generate the package; do not overwrite a version directory
- [ ] validate registry, hashes, schemas, tests, and Ruff
- [ ] add registry entry explicitly and review immutable versions
>>>>>>> origin/main
