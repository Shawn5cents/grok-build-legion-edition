# Contributing to Legion

Bug reports, documentation improvements, and focused pull requests are
welcome. Legion is an independent community fork, so contributions should be
directed to this repository rather than the upstream xAI project.

## Before opening a pull request

1. Open or reference an issue for substantial behavior changes so maintainers
   can confirm the direction before a large implementation.
2. Keep each pull request focused and explain the user impact and validation.
3. Never include API keys, tokens, private endpoints, local configuration, or
   unredacted diagnostic output.
4. Preserve upstream copyright and attribution notices.

For Rust changes, run the checks relevant to your patch. The complete CI set is:

```bash
cargo fmt --all -- --check
cargo check --workspace
cargo test --workspace
```

For Legion's Python control tools, also run:

```bash
python3 -m unittest discover -s tools/tests -v
bash -n install.sh bin/legion tools/switch-subagents.sh
```

All submissions are reviewed through pull requests. Maintainers may ask for
tests, documentation, or a smaller scope before merging.

## Security reports

Do not open a public issue for a vulnerability. Follow [`SECURITY.md`](SECURITY.md)
to submit a private report.

## Licensing

By submitting a contribution, you agree that it may be distributed under the
Apache License, Version 2.0. No separate contributor license agreement is
currently required.
