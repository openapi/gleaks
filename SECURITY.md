# Security

Please report vulnerabilities privately through
[GitHub security advisories](https://github.com/openapi/gleaks/security/advisories/new).

## Threat model

**Protected:** a stolen or copied `.gleaks` file, including backups of it, without
the password. Modification of the file is detected when it is opened.

**How:** the file is AES-256-GCM encrypted with a key derived by scrypt
(N=2^17, r=8, p=1) from the profile password. The database lives only in memory
while the profile is open, so no journal, WAL or temporary file holds it in clear.
Each save atomically replaces the file with new ciphertext.

**API keys** are stored in the desktop keyring through libsecret, never in the
profile, so they do not travel with the file. On another computer you enter the key again.

**Not protected:**

- Malware running in your desktop session, or anyone using your unlocked session.
  While a profile is open, its contents and key are in the application's memory,
  and Python cannot reliably wipe them.
- A weak profile password. There is no recovery if you lose it.
- What a source learns. In direct mode the source receives your full address;
  in private mode it receives a hash prefix and your IP address.

Two copies of one profile edited on different computers do not merge; the last save wins.
