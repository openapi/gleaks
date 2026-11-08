# GLeaks

**Know where your data has leaked.**

GLeaks is a native GNOME application that keeps a private record of where your
email addresses have appeared in known data breaches. Everything it finds stays
in one encrypted file that belongs to you. There is no account and no cloud
service, and nothing is sent to a source until you have seen exactly what will be
sent and confirmed it.

GLeaks is independent and is not affiliated with GNOME, Ubuntu or Have I Been Pwned.

## Install

Ubuntu 24.04 or later, and Debian 13 or later:

```sh
curl -fsSL https://github.com/openapi/gleaks/releases/latest/download/install.sh | bash
```

Any distribution: download the `.flatpak` bundle from the
[releases page](https://github.com/openapi/gleaks/releases) and run
`flatpak install --user gleaks-*.flatpak`.

## Getting started

1. Create a profile. Its password encrypts the whole file and cannot be recovered.
2. Add your email addresses.
3. In Preferences, enter your own [Have I Been Pwned API key](https://haveibeenpwned.com/API/Key).
   Checking addresses requires a paid HIBP subscription.
4. Press **Scan**, review what will be sent, and confirm.

Plans that include it can use the private search, which sends only the first six
characters of a hash of each address.

Results only cover what a source knows on the date of the check. An event does
not mean an account is compromised today, and an empty result does not guarantee
that nothing has leaked. Breach data is provided by
[Have I Been Pwned](https://haveibeenpwned.com).

## Development

Needs Python 3.11+, PyGObject, GTK 4, Libadwaita 1.5+, libsecret and `python3-cryptography`.

```sh
make run      # run from the source tree
make test     # tests; the interface tests need a display
make check    # byte-compile and validate the desktop metadata
make deb      # build dist/gleaks_*_all.deb
make flatpak  # build and install the Flatpak
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) for the threat
model, and [IDEA.md](IDEA.md) for the product vision and roadmap.

## License

[MIT](LICENSE)
