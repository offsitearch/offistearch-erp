"""Feature rings (r2+, outward from the kernel).

Each ring depends only on inner rings (kernel, platform, …) and is enforced by
an import-linter contract. Cross-ring reads go through ring service layers, not
direct model imports.
"""
