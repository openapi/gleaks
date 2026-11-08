# Contributing

Run `make test` and `make check` before opening a pull request.

The code is layered so the logic can be tested without a desktop:

- `gleaks/core`: domain, encrypted storage and scan engine. It must not import GTK.
- `gleaks/providers`: connectors. One module per source, none known to the engine.
- `gleaks/ui`: GTK 4 and Libadwaita.

Rules that matter here:

- An error must never look like "no exposures". Connectors raise `ProviderError`.
- Identifiers, API keys and response bodies never reach logs.
- Provider responses are untrusted. Rows and toasts are built with markup off (see `ui/common.py`).
- Nothing is sent to a source without passing through the consent dialog.
- Schema changes are new entries appended to `MIGRATIONS`; never edit a released one.

New connectors must fill in every field of `ProviderInfo`, since the consent dialog
shows them to the user. Third-party plugins are not supported yet.

To test against the real HIBP API without a subscription, use the documented test
key `00000000000000000000000000000000` with an address such as
`multiple-breaches@hibp-integration-tests.com`.
