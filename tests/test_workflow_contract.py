from pathlib import Path


def test_ci_workflow_runs_matrix_and_installed_cli_smoke():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python-version: [\"3.10\", \"3.11\", \"3.12\"]" in workflow
    assert "python -m pytest -q" in workflow
    assert "chatdns --version" in workflow
    assert "chatdns --tree" in workflow
    assert "mkdocs build --strict" in workflow
    assert "python -m build" in workflow


def test_publish_workflow_uses_oidc_with_main_release_guard():
    workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")

    assert "id-token: write" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    assert "Publish to PyPI (OIDC)" in workflow
    assert "workflow_dispatch" in workflow
    assert "Check release commit is on default branch" in workflow
    assert "git fetch --no-tags origin main:refs/remotes/origin/main" in workflow
    assert 'git merge-base --is-ancestor "${GITHUB_SHA}" "origin/main"' in workflow
    assert "git fetch origin main --tags" not in workflow
    assert "git fetch origin master --tags" not in workflow
    assert "environment: pypi" not in workflow
    assert "TWINE_PASSWORD" not in workflow
    assert "PYPI_API_TOKEN" not in workflow
    assert "secrets.PYPI" not in workflow
    assert "https://pypi.org/pypi/ChatDNS/" in workflow


def test_docs_workflows_target_chatarch_pages():
    preview = Path(".github/workflows/preview.yaml").read_text(encoding="utf-8")
    deploy = Path(".github/workflows/deploy.yaml").read_text(encoding="utf-8")

    assert "Preview Docs" in preview
    assert "CHATARCH_PREVIEW_URL" in preview
    assert "mike deploy dev" in preview
    assert "Deploy Docs" in deploy
    assert "mkdocs gh-deploy --force" in deploy
    assert "github.io" not in preview
    assert "github.io" not in deploy
