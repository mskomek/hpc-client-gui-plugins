# Consumer contract (application ↔ registry)

The registry and application validate each other against immutable release
refs. The registry-side `consumer-contract` job checks this checkout with the
application's real plugin contract suite.

The current v2 consumer pin is application `v1.5.3`. Plugin API v2 engines are
hash-verified and loaded only after explicit user action; registry validation
never imports or executes them.

When advancing the pin, update `APPLICATION_REF` and the v2 compatibility
floor together, then require a green consumer-contract job before merging.
