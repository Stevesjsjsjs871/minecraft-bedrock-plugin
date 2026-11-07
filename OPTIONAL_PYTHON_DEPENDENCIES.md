# Optional Python dependencies

The Skills-only package does not install Python packages automatically. The following optional command-line workflows require the third-party `jsonschema` package:

| Utility | Dependency use | Behavior when unavailable |
|---|---|---|
| `skills/audit-benchmark/scripts/evaluate_benchmark.py` | Draft 2020-12 benchmark-manifest/report validation | Reports the missing dependency; benchmark evaluation is blocked. |
| `skills/automated-validation/scripts/validate_report.py` | Draft 2020-12 audit-report validation | Exits with code 2 and prints the installation hint. |
| `skills/regression-evals/scripts/regression_tests.py` | Validates every generated audit report against the report schema | Cases cannot be accepted as passing without schema validation; the harness reports the missing dependency. |

## Tested environment

- Python: CPython 3.13.5.
- `jsonschema`: 4.26.0 installed in the local development container used for the recorded audit.
- Installation is optional and must be explicit in the environment that runs the utility:

```bash
python -m pip install 'jsonschema==4.26.0'
```

No package installation is performed by the plugin or by Skills. The exact version above records the reproducible local test environment; it is not a claim that every ChatGPT surface includes Python or this dependency. Verify the package version and availability before running dependency-backed commands in another environment.

All other active Skills utilities audited for this release use the Python standard library and/or package-local modules. The historical `server/` tree is excluded from active workflows and was not executed.
