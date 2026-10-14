# Local ROKO profiles

This extension targets the Roko-Network historical Bittensor 6.9.3 fork on
`master`. The current parent repository, RaoFoundation/bittensor, is archived
and has moved its SDK under `bittensor/core`; it no longer contains this fork's
`bittensor/cli.py` or `bittensor/commands` layout. This delivery does not claim
compatibility with that newer SDK or the separate current CLI.

Create, list, and inspect local profiles with `btcli profile create`,
`btcli profile list`, and `btcli profile show --profile.name NAME`.
Creation stores only network/endpoint, wallet names/path, subnet ID, and profile
name. It does not connect to a chain, load wallet keys, or save credentials.
`--netuid` accepts a nonnegative integer. `--profile.path` accepts a directory
with or without a trailing slash. Names must be a single safe filename.

Noninteractive creation preserves existing profiles unless
`--profile.overwrite` is explicitly set. Writes use a private temporary file
and atomic replacement; a failed replacement preserves the existing profile.
Symlink profiles and path traversal names are refused.

Run `python3 tests/unit_tests/test_profile.py` with PyYAML, Rich, and Munch 2.5.0
installed, plus Setuptools 80.9.0 for Munch's historical `pkg_resources` import.
These offline tests load the actual historical configuration class
and use isolated profile directories. They cover persistence, listing/showing,
endpoint selection, CLI argument registration, failed writes, and refusal
cases. They do not qualify the whole historical SDK or contact a live network.
