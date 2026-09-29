# Publishing to PyPI

The repository includes a manual publishing workflow. Uploading source to GitHub does not publish a package.

## Configure the first release

On your PyPI account's Publishing page, add a pending GitHub publisher with these exact values:

| Field | Value |
| :--- | :--- |
| PyPI project name | `aa-planetary-operations` |
| GitHub owner | `jaybone26` |
| Repository name | `aa-planetary-operations` |
| Workflow filename | `publish.yml` |
| Environment name | `pypi` |

In GitHub repository settings, create the environment `pypi`. Configure a required reviewer if you want an approval gate for publication. Trusted publishing uses GitHub's identity; no PyPI API token is needed.

See [PyPI's pending publisher instructions](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

## Publish when ready

1. Complete a real AA server staging check, including SSO and a Celery calculation.
2. Confirm the version in `pyproject.toml` and the README matches the intended release. PyPI versions cannot be overwritten.
3. Open GitHub **Actions → Publish to PyPI → Run workflow**, and select the reviewed branch.
4. The workflow runs lint and tests, builds both distributions, validates metadata, and publishes them.
5. Confirm the package page and installation before submitting the Alliance Auth app directory listing.

After publication, users can install with `python -m pip install aa-planetary-operations` inside their Auth virtual environment.
