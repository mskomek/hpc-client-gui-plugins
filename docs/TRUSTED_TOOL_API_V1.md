# Trusted Tool API v1

This is a maintainer contract for explicitly approved executable tools. It is
not an upload-and-run extension API.

The application owns the allowlist and checks tool identity, publisher, API
version, exact package structure, compatibility, and registry/manifest/file
hashes. The current approved tool is `org.hpcclient.ansyslint`.

A tool may read user-selected local input, parse bundled rule data, and return
findings. It must not access SSH credentials, keyrings, updater secrets,
provider-registry mutation, arbitrary network, or arbitrary subprocesses.
